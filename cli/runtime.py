"""Photo Agents headless runtime.

Boot path::

    ensure_authenticated()                 # API key gate
        -> PhotoAgentsRuntime.__init__()   # load LLM sessions, history, locks
        -> agent.run()                     # consume tasks from the queue forever

The runtime can be driven three ways:

* ``--task IODIR``     one-shot file-IO mode (write input.txt, read output.txt)
* ``--reflect SCRIPT`` watchdog mode (poll a Python ``check()`` function)
* (no flag)            interactive REPL on stdin

Environment variables:

* ``PHOTOAGENTS_API_KEY``  - your Photo Agents license key (required)
* ``PHOTOAGENTS_LANG``     - ``zh`` or ``en`` (default: detected from locale)
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import queue
import random
import re
import sys
import threading
import time
from datetime import datetime

# Resolve the package root so we can find resources/ regardless of cwd.
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_DIR = os.path.dirname(_PKG_DIR)
if _REPO_DIR not in sys.path:
    sys.path.insert(0, _REPO_DIR)

# Set the language env var BEFORE importing handler / router (they read it at
# import time).
os.environ.setdefault(
    "PHOTOAGENTS_LANG",
    "zh" if any(k in (locale.getlocale()[0] or "").lower() for k in ("zh", "chinese")) else "en",
)

# Some bundled launchers swallow stdout/stderr. Re-bind to /dev/null with
# replace-on-encoding so prints never explode on weird codepoints.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
elif hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
elif hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

from photoagents.auth import ensure_authenticated  # noqa: E402
from photoagents.core.handler import (  # noqa: E402
    PhotoAgentsHandler,
    consume_file,
    format_error,
    get_global_memory,
    smart_format,
)
from photoagents.core.loop import run_agent_session  # noqa: E402
from photoagents.llm.router import (  # noqa: E402
    ClaudeSession,
    LLMSession,
    MixinSession,
    NativeClaudeSession,
    NativeOAISession,
    NativeToolClient,
    ToolClient,
    reload_credentials,
)


_RESOURCES = os.path.join(_PKG_DIR, "resources")
_USER_DATA = os.path.expanduser("~/.photoagents")


def _load_tool_schema(suffix: str = "") -> dict:
    """Load and cache the tool schema. PowerShell on Windows, bash elsewhere."""
    path = os.path.join(_RESOURCES, f"tools{suffix}.json")
    raw = open(path, "r", encoding="utf-8").read()
    return json.loads(raw if os.name == "nt" else raw.replace("powershell", "bash"))


TOOLS_SCHEMA = _load_tool_schema()


def _ensure_user_state() -> None:
    """Create ``~/.photoagents/`` and seed first-run files if missing."""
    os.makedirs(_USER_DATA, exist_ok=True)
    lang_suffix = "_en" if os.environ.get("PHOTOAGENTS_LANG", "") == "en" else ""

    mem_txt = os.path.join(_USER_DATA, "global_mem.txt")
    if not os.path.exists(mem_txt):
        with open(mem_txt, "w", encoding="utf-8") as fp:
            fp.write("# [Global Memory - L2]\n")

    mem_insight = os.path.join(_USER_DATA, "global_mem_insight.txt")
    if not os.path.exists(mem_insight):
        template = os.path.join(_RESOURCES, f"global_mem_insight_template{lang_suffix}.txt")
        if os.path.exists(template):
            with open(template, encoding="utf-8") as src:
                payload = src.read()
        else:
            payload = ""
        with open(mem_insight, "w", encoding="utf-8") as fp:
            fp.write(payload)

    cdp_cfg = os.path.join(_RESOURCES, "tmwd_cdp_bridge", "config.js")
    if not os.path.exists(cdp_cfg):
        try:
            os.makedirs(os.path.dirname(cdp_cfg), exist_ok=True)
            token = hex(random.randint(0, 99_999_999))[2:8]
            with open(cdp_cfg, "w", encoding="utf-8") as fp:
                fp.write(f"const TID = '__pha_{token}';")
        except Exception as exc:  # noqa: BLE001
            print(
                f"[WARN] CDP config init failed: {exc} - "
                "advanced web features (TMWebDriver) will be unavailable."
            )


_ensure_user_state()


def _system_prompt() -> str:
    lang_suffix = "_en" if os.environ.get("PHOTOAGENTS_LANG", "") == "en" else ""
    name = f"system_prompt{lang_suffix}.txt"
    path = os.path.join(_RESOURCES, name)
    if not os.path.exists(path):
        path = os.path.join(_RESOURCES, "system_prompt.txt")
    with open(path, "r", encoding="utf-8") as fp:
        prompt = fp.read()
    prompt += f"\nToday: {time.strftime('%Y-%m-%d %a')}\n"
    prompt += get_global_memory()
    return prompt


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------

class PhotoAgentsRuntime:
    """Orchestrates a single agent: queue, history, LLM router, tool handler."""

    def __init__(self):
        # Gate: refuse to start without a valid Photo Agents API key.
        ensure_authenticated()

        os.makedirs(os.path.join(_USER_DATA, "temp"), exist_ok=True)
        self.lock = threading.Lock()
        self.task_dir = None
        self.history: list[str] = []
        self.task_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.stop_sig = False
        self.llm_no = 0
        self.inc_out = False
        self.handler: PhotoAgentsHandler | None = None
        self.verbose = True
        self.load_llm_sessions()

    # ----- LLM session management ------------------------------------------

    def load_llm_sessions(self):
        creds, changed = reload_credentials()
        if not changed and hasattr(self, "llmclients"):
            return
        try:
            oldhistory = self.llmclient.backend.history
        except Exception:
            oldhistory = None

        sessions: list = []
        for k, cfg in creds.items():
            if not any(x in k for x in ("api", "config", "cookie")):
                continue
            try:
                if "native" in k and "claude" in k:
                    sessions.append(NativeToolClient(NativeClaudeSession(cfg=cfg)))
                elif "native" in k and "oai" in k:
                    sessions.append(NativeToolClient(NativeOAISession(cfg=cfg)))
                elif "claude" in k:
                    sessions.append(ToolClient(ClaudeSession(cfg=cfg)))
                elif "oai" in k:
                    sessions.append(ToolClient(LLMSession(cfg=cfg)))
                elif "mixin" in k:
                    sessions.append({"mixin_cfg": cfg})
            except Exception:
                pass

        # Resolve mixin entries against the now-built session list.
        for i, s in enumerate(sessions):
            if isinstance(s, dict) and "mixin_cfg" in s:
                try:
                    mixin = MixinSession(sessions, s["mixin_cfg"])
                    if isinstance(mixin._sessions[0], (NativeClaudeSession, NativeOAISession)):
                        sessions[i] = NativeToolClient(mixin)
                    else:
                        sessions[i] = ToolClient(mixin)
                except Exception as exc:  # noqa: BLE001
                    print(f"\n\n\n[ERROR] Failed to init MixinSession with cfg "
                          f"{s['mixin_cfg']}: {exc}!!!\n\n")

        self.llmclients = sessions
        self.llmclient = self.llmclients[self.llm_no % len(self.llmclients)]
        if oldhistory:
            self.llmclient.backend.history = oldhistory

    def next_llm(self, n: int = -1):
        self.load_llm_sessions()
        self.llm_no = ((self.llm_no + 1) if n < 0 else n) % len(self.llmclients)
        last = self.llmclient
        self.llmclient = self.llmclients[self.llm_no]
        try:
            self.llmclient.backend.history = last.backend.history
        except Exception:
            raise Exception("[ERROR] BAD Mixin config: check your credentials.py")
        self.llmclient.last_tools = ""
        # Some Chinese-tuned models prefer a slightly different schema dialect.
        global TOOLS_SCHEMA
        name = self.get_llm_name(model=True)
        if "glm" in name or "minimax" in name or "kimi" in name:
            TOOLS_SCHEMA = _load_tool_schema("_cn")
        else:
            TOOLS_SCHEMA = _load_tool_schema()

    def list_llms(self):
        self.load_llm_sessions()
        return [(i, self.get_llm_name(b), i == self.llm_no)
                for i, b in enumerate(self.llmclients)]

    def get_llm_name(self, b=None, model: bool = False) -> str:
        b = self.llmclient if b is None else b
        if isinstance(b, dict):
            return "BADCONFIG_MIXIN"
        if model:
            return b.backend.model.lower()
        return f"{type(b.backend).__name__}/{b.backend.name}"

    # ----- Task lifecycle --------------------------------------------------

    def abort(self):
        if not self.is_running:
            return
        print("Abort current task...")
        self.stop_sig = True
        if self.handler is not None:
            self.handler.code_stop_signal.append(1)

    def put_task(self, query: str, source: str = "user", images=None) -> queue.Queue:
        display_queue: queue.Queue = queue.Queue()
        self.task_queue.put({
            "query": query,
            "source": source,
            "images": images or [],
            "output": display_queue,
        })
        return display_queue

    # Slash commands are intentionally cheap to reason about; raw_query is
    # already gnarly enough that adding more layers would be worse.
    def _handle_slash_cmd(self, raw_query: str, display_queue: queue.Queue):
        if not raw_query.startswith("/"):
            return raw_query
        match = re.match(r"/session\.(\w+)=(.*)", raw_query.strip())
        if match:
            k, v = match.group(1), match.group(2)
            vfile = os.path.join(_USER_DATA, "temp", v)
            if os.path.isfile(vfile):
                v = open(vfile, encoding="utf-8").read().strip()
            try:
                v = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                pass
            setattr(self.llmclient.backend, k, v)
            display_queue.put({
                "done": smart_format(f"\u2705 session.{k} = {repr(v)}", max_str_len=500),
                "source": "system",
            })
            return None
        if raw_query.strip() == "/resume":
            return (
                r"Scan the temp/model_responses/ directory for the 10 most recent files "
                r"(excluding this PID), read each file's content, normalize newlines via "
                r"replace('\\n','\n').replace('\\r','\r'), then run "
                r"re.findall(r'<history>\n\[(?:USER|Agent)\].*?</history>', content, re.DOTALL) "
                r"to extract sessions. Take the last match per file as that session's content, "
                r"sort by mtime descending, summarize each in one sentence, and let the user "
                r"pick. Once selected, read that file's tail as the chat baseline."
            )
        return raw_query

    def run(self):
        while True:
            task = self.task_queue.get()
            raw_query = task["query"]
            source = task["source"]
            display_queue = task["output"]
            raw_query = self._handle_slash_cmd(raw_query, display_queue)
            if raw_query is None:
                self.task_queue.task_done()
                continue
            self.is_running = True
            rquery = smart_format(raw_query.replace("\n", " "), max_str_len=200)
            self.history.append(f"[USER]: {rquery}")

            sys_prompt = _system_prompt() + getattr(self.llmclient.backend, "extra_sys_prompt", "")
            handler = PhotoAgentsHandler(self, self.history, os.path.join(_USER_DATA, "temp"))
            if self.handler and "key_info" in self.handler.working:
                # Drop the previous turn's "this is N tasks ago" annotation so we can re-stamp it.
                ki = re.sub(
                    r"\n\[SYSTEM\] This is the working memory.*?\n",
                    "",
                    self.handler.working["key_info"],
                )
                handler.working["key_info"] = ki
                handler.working["passed_sessions"] = ps = (
                    self.handler.working.get("passed_sessions", 0) + 1
                )
                if ps > 0:
                    handler.working["key_info"] += (
                        f"\n[SYSTEM] This is the working memory set {ps} conversations ago. "
                        "If you are now on a new task, update or clear it.\n"
                    )
            self.handler = handler

            # Note: even with a fresh handler, the **full** history lives in
            # the LLM session, so context is preserved across tasks.
            gen = run_agent_session(
                self.llmclient, sys_prompt, raw_query,
                handler, TOOLS_SCHEMA, max_turns=70, verbose=self.verbose,
            )
            full_resp = ""
            try:
                last_pos = 0
                for chunk in gen:
                    if consume_file(self.task_dir, "_stop"):
                        self.abort()
                    if self.stop_sig:
                        break
                    full_resp += chunk
                    if len(full_resp) - last_pos > 50 or "LLM Running" in chunk:
                        display_queue.put({
                            "next": full_resp[last_pos:] if self.inc_out else full_resp,
                            "source": source,
                        })
                        last_pos = len(full_resp)
                if self.inc_out and last_pos < len(full_resp):
                    display_queue.put({"next": full_resp[last_pos:], "source": source})
                if "</summary>" in full_resp:
                    full_resp = full_resp.replace("</summary>", "</summary>\n\n")
                if "</file_content>" in full_resp:
                    full_resp = re.sub(
                        r"<file_content>\s*(.*?)\s*</file_content>",
                        r"\n````\n<file_content>\n\1\n</file_content>\n````",
                        full_resp, flags=re.DOTALL,
                    )
                display_queue.put({"done": full_resp, "source": source})
                self.history = handler.history_info
            except Exception as exc:
                print(f"Backend Error: {format_error(exc)}")
                display_queue.put({
                    "done": full_resp + f"\n```\n{format_error(exc)}\n```",
                    "source": source,
                })
            finally:
                if self.stop_sig:
                    print("User aborted the task.")
                self.is_running = self.stop_sig = False
                self.task_queue.task_done()
                if self.handler is not None:
                    self.handler.code_stop_signal.append(1)


# Backwards-compat alias so older frontends that imported the misspelled name
# keep working.
GeneraticAgent = PhotoAgentsRuntime


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="photoagents", description="Photo Agents runtime")
    parser.add_argument("--task", metavar="IODIR", help="one-shot file-IO mode")
    parser.add_argument("--reflect", metavar="SCRIPT",
                        help="reflect mode: load a watchdog script and run check() on a timer")
    parser.add_argument("--input", help="initial prompt for --task mode")
    parser.add_argument("--llm_no", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--bg", action="store_true",
                        help="popen self, print PID, and exit")
    args = parser.parse_args()

    if args.bg:
        import platform
        import subprocess
        cmd = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:] if a != "--bg"]
        d = os.path.join(_USER_DATA, "temp", args.task or "bg")
        os.makedirs(d, exist_ok=True)
        proc = subprocess.Popen(
            cmd, cwd=_REPO_DIR,
            creationflags=0x08000000 if platform.system() == "Windows" else 0,
            stdout=open(os.path.join(d, "stdout.log"), "w", encoding="utf-8"),
            stderr=open(os.path.join(d, "stderr.log"), "w", encoding="utf-8"),
        )
        print(proc.pid)
        sys.exit(0)

    agent = PhotoAgentsRuntime()
    agent.next_llm(args.llm_no)
    agent.verbose = args.verbose
    threading.Thread(target=agent.run, daemon=True).start()

    if args.task:
        _run_task_mode(agent, args)
    elif args.reflect:
        _run_reflect_mode(agent, args)
    else:
        _run_repl(agent)


def _run_task_mode(agent: PhotoAgentsRuntime, args):
    import glob
    agent.task_dir = d = os.path.join(_USER_DATA, "temp", args.task)
    nround: int | str = ""
    infile = os.path.join(d, "input.txt")
    if args.input:
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "output*.txt")):
            os.remove(old)
        with open(infile, "w", encoding="utf-8") as fp:
            fp.write(args.input)
    with open(infile, encoding="utf-8") as fp:
        raw = fp.read()
    while True:
        dq = agent.put_task(raw, source="task")
        item = dq.get(timeout=120)
        while "done" not in item:
            if "next" in item and random.random() < 0.95:
                with open(f"{d}/output{nround}.txt", "w", encoding="utf-8") as fp:
                    fp.write(item.get("next", ""))
            item = dq.get(timeout=120)
        with open(f"{d}/output{nround}.txt", "w", encoding="utf-8") as fp:
            fp.write(item["done"] + "\n\n[ROUND END]\n")
        consume_file(d, "_stop")
        for _ in range(300):  # wait for reply.txt, 10-minute window
            time.sleep(2)
            raw = consume_file(d, "reply.txt")
            if raw:
                break
        else:
            break
        nround = nround + 1 if isinstance(nround, int) else 1


def _run_reflect_mode(agent: PhotoAgentsRuntime, args):
    import importlib.util
    spec = importlib.util.spec_from_file_location("reflect_script", args.reflect)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    last_mtime = os.path.getmtime(args.reflect)
    print(f"[Reflect] loaded {args.reflect}")
    while True:
        if os.path.getmtime(args.reflect) != last_mtime:
            try:
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                last_mtime = os.path.getmtime(args.reflect)
                print("[Reflect] reloaded")
            except Exception as exc:  # noqa: BLE001
                print(f"[Reflect] reload error: {exc}")
        time.sleep(getattr(mod, "INTERVAL", 5))
        try:
            task = mod.check()
        except Exception as exc:  # noqa: BLE001
            print(f"[Reflect] check() error: {exc}")
            continue
        if task is None:
            continue
        print(f"[Reflect] triggered: {task[:80]}")
        dq = agent.put_task(task, source="reflect")
        try:
            item = dq.get(timeout=120)
            while "done" not in item:
                item = dq.get(timeout=120)
            result = item["done"]
            print(result)
        except Exception as exc:  # noqa: BLE001
            if getattr(mod, "ONCE", False):
                raise
            print(f"[Reflect] drain error: {exc}")
            result = f"[ERROR] {exc}"
        log_dir = os.path.join(_USER_DATA, "temp", "reflect_logs")
        os.makedirs(log_dir, exist_ok=True)
        script_name = os.path.splitext(os.path.basename(args.reflect))[0]
        with open(
            os.path.join(log_dir, f"{script_name}_{datetime.now():%Y-%m-%d}.log"),
            "a", encoding="utf-8",
        ) as fp:
            fp.write(f"[{datetime.now():%m-%d %H:%M}]\n{result}\n\n")
        on_done = getattr(mod, "on_done", None)
        if on_done:
            try:
                on_done(result)
            except Exception as exc:  # noqa: BLE001
                print(f"[Reflect] on_done error: {exc}")
        if getattr(mod, "ONCE", False):
            print("[Reflect] ONCE=True, exiting.")
            break


def _run_repl(agent: PhotoAgentsRuntime):
    try:
        import readline  # noqa: F401
    except Exception:
        pass
    agent.inc_out = True
    while True:
        q = input("> ").strip()
        if not q:
            continue
        try:
            dq = agent.put_task(q, source="user")
            while True:
                item = dq.get()
                if "next" in item:
                    print(item["next"], end="", flush=True)
                if "done" in item:
                    print()
                    break
        except KeyboardInterrupt:
            agent.abort()
            print("\n[Interrupted]")


if __name__ == "__main__":
    main()
