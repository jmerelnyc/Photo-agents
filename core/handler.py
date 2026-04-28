"""The Photo Agents tool dispatcher.

:class:`PhotoAgentsHandler` subclasses :class:`photoagents.core.loop.BaseHandler`
and implements one ``do_<tool_name>`` method per tool exposed in
``photoagents/resources/tools.json``. The runtime instantiates a fresh
handler per task; long-lived state (LLM history, queue, locks) lives on the
parent :class:`PhotoAgentsRuntime`.
"""

from __future__ import annotations

import collections
import difflib
import importlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from photoagents.core.loop import BaseHandler, StepOutcome, json_default
from photoagents.web import dom as simphtml


_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USER_DATA = os.path.expanduser("~/.photoagents")
_RESOURCES = os.path.join(_PKG_DIR, "resources")
_SKILLS = os.path.join(_PKG_DIR, "skills")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def smart_format(data, max_str_len: int = 100, omit_str: str = " ... "):
    """Return ``data`` truncated head+tail style if it exceeds ``max_str_len``."""
    if not isinstance(data, str):
        data = str(data)
    if len(data) < max_str_len + len(omit_str) * 2:
        return data
    return f"{data[:max_str_len // 2]}{omit_str}{data[-max_str_len // 2:]}"


def consume_file(dr, file):
    """Read-then-delete a file. Returns its content or ``None`` if absent."""
    if dr and os.path.exists(os.path.join(dr, file)):
        with open(os.path.join(dr, file), encoding="utf-8", errors="replace") as fp:
            content = fp.read()
        os.remove(os.path.join(dr, file))
        return content
    return None


def format_error(exc):
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb = traceback.extract_tb(exc_tb)
    if tb:
        f = tb[-1]
        fname = os.path.basename(f.filename)
        return f"{exc_type.__name__}: {exc} @ {fname}:{f.lineno}, {f.name} -> `{f.line}`"
    return f"{exc_type.__name__}: {exc}"


def get_global_memory():
    """Render the global memory L1/L2 block that gets injected each turn."""
    prompt = "\n"
    try:
        suffix = "_en" if os.environ.get("PHOTOAGENTS_LANG", "") == "en" else ""
        with open(os.path.join(_USER_DATA, "global_mem_insight.txt"),
                  "r", encoding="utf-8", errors="replace") as fp:
            insight = fp.read()
        struct_path = os.path.join(_RESOURCES, f"insight_fixed_structure{suffix}.txt")
        if not os.path.exists(struct_path):
            struct_path = os.path.join(_RESOURCES, "insight_fixed_structure.txt")
        with open(struct_path, "r", encoding="utf-8") as fp:
            structure = fp.read()
        prompt += f"cwd = {os.path.join(_USER_DATA, 'temp')} (./)\n"
        prompt += "\n[Memory] (photoagents/skills)\n"
        prompt += structure + "\n~/.photoagents/global_mem_insight.txt:\n"
        prompt += insight + "\n"
    except FileNotFoundError:
        pass
    return prompt


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

def code_run(code, code_type: str = "python", timeout: int = 60,
             cwd=None, code_cwd=None, stop_signal: list | None = None):
    """Sandboxed code executor.

    * ``python`` -> writes to a temp ``.ai.py`` file and runs via the same
      interpreter, prepended with ``resources/code_run_header.py``.
    * ``powershell`` / ``bash`` -> single-line shell command via the
      platform-appropriate shell.
    """
    stop_signal = stop_signal if stop_signal is not None else []
    preview = ((code[:60].replace("\n", " ") + "...") if len(code) > 60
               else code.strip())
    yield f"[Action] Running {code_type} in {os.path.basename(cwd) if cwd else '.'}: {preview}\n"
    cwd = cwd or os.path.join(_USER_DATA, "temp")
    tmp_path = None

    if code_type in ("python", "py"):
        tmp_file = tempfile.NamedTemporaryFile(suffix=".ai.py", delete=False,
                                                mode="w", encoding="utf-8",
                                                dir=code_cwd)
        cr_header = os.path.join(_RESOURCES, "code_run_header.py")
        if os.path.exists(cr_header):
            tmp_file.write(open(cr_header, encoding="utf-8").read())
        tmp_file.write(code)
        tmp_path = tmp_file.name
        tmp_file.close()
        cmd = [sys.executable, "-X", "utf8", "-u", tmp_path]
    elif code_type in ("powershell", "bash", "sh", "shell", "ps1", "pwsh"):
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", code]
        else:
            cmd = ["bash", "-c", code]
    else:
        return {"status": "error", "msg": f"Unsupported code type: {code_type}"}

    print("code run output:")
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    full_stdout: list[str] = []

    def stream_reader(proc, logs):
        try:
            for line_bytes in iter(proc.stdout.readline, b""):
                try:
                    line = line_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    line = line_bytes.decode("gbk", errors="ignore")
                logs.append(line)
                try:
                    print(line, end="")
                except Exception:
                    pass
        except Exception:
            pass

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, cwd=cwd, startupinfo=startupinfo,
        )
        start_t = time.time()
        t = threading.Thread(target=stream_reader, args=(process, full_stdout), daemon=True)
        t.start()

        while t.is_alive():
            istimeout = time.time() - start_t > timeout
            if istimeout or len(stop_signal) > 0:
                process.kill()
                print("[Debug] Process killed due to timeout or stop signal.")
                if istimeout:
                    full_stdout.append("\n[Timeout Error] Forcibly terminated after timeout.")
                else:
                    full_stdout.append("\n[Stopped] Forcibly terminated by user request.")
                break
            time.sleep(1)

        t.join(timeout=1)
        exit_code = process.poll()
        stdout_str = "".join(full_stdout)
        status = "success" if exit_code == 0 else "error"
        status_icon = "[OK]" if exit_code == 0 else "[ERR]"
        if exit_code is None:
            status_icon = "[..]"
        snippet = smart_format(stdout_str, max_str_len=600,
                               omit_str="\n\n[omitted long output]\n\n")
        yield f"[Status] {status_icon} Exit Code: {exit_code}\n[Stdout]\n{snippet}\n"
        if process.stdout:
            threading.Thread(target=process.stdout.close, daemon=True).start()
        return {
            "status": status,
            "stdout": smart_format(stdout_str, max_str_len=10_000,
                                    omit_str="\n\n[omitted long output]\n\n"),
            "exit_code": exit_code,
        }
    except Exception as exc:
        if "process" in locals():
            try:
                process.kill()  # type: ignore[name-defined]
            except Exception:
                pass
        return {"status": "error", "msg": str(exc)}
    finally:
        if code_type == "python" and tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def ask_user(question, candidates=None):
    """Tool: pause the loop and surface a question to the human."""
    return {
        "status": "INTERRUPT",
        "intent": "HUMAN_INTERVENTION",
        "data": {"question": question, "candidates": candidates or []},
    }


# ---------------------------------------------------------------------------
# Browser glue
# ---------------------------------------------------------------------------

driver = None


def first_init_driver():
    global driver
    from photoagents.web.driver import TMWebDriver
    driver = TMWebDriver()
    sess = []
    for _ in range(20):
        time.sleep(1)
        sess = driver.get_all_sessions()
        if len(sess) > 0:
            break
    if len(sess) == 0:
        return
    if len(sess) == 1:
        time.sleep(3)


def web_scan(tabs_only: bool = False, switch_tab_id=None, text_only: bool = False):
    """Snapshot the current tab. Filters out floating / hidden chrome.
    ``tabs_only=True`` returns just the tab list (cheap)."""
    global driver
    try:
        if driver is None:
            first_init_driver()
        if len(driver.get_all_sessions()) == 0:
            return {"status": "error",
                    "msg": "No browser tab available. Check L3 memory for diagnostics."}
        tabs = []
        for sess in driver.get_all_sessions():
            sess.pop("connected_at", None)
            sess.pop("type", None)
            url = sess.get("url", "")
            sess["url"] = url[:50] + ("..." if len(url) > 50 else "")
            tabs.append(sess)
        if switch_tab_id:
            driver.default_session_id = switch_tab_id
        result = {
            "status": "success",
            "metadata": {
                "tabs_count": len(tabs),
                "tabs": tabs,
                "active_tab": driver.default_session_id,
            },
        }
        if not tabs_only:
            importlib.reload(simphtml)
            result["content"] = simphtml.get_html(driver, cutlist=True,
                                                  maxchars=35_000, text_only=text_only)
            if text_only:
                result["content"] = smart_format(result["content"], max_str_len=10_000,
                                                  omit_str="\n\n[omitted long content]\n\n")
        return result
    except Exception as exc:
        return {"status": "error", "msg": format_error(exc)}


def web_execute_js(script, switch_tab_id=None, no_monitor: bool = False):
    """Run arbitrary JS in the current tab and capture the return value plus
    any page-state changes."""
    global driver
    try:
        if driver is None:
            first_init_driver()
        if len(driver.get_all_sessions()) == 0:
            return {"status": "error",
                    "msg": "No browser tab available. Check L3 memory for diagnostics."}
        if switch_tab_id:
            driver.default_session_id = switch_tab_id
        return simphtml.execute_js_rich(script, driver, no_monitor=no_monitor)
    except Exception as exc:
        return {"status": "error", "msg": format_error(exc)}


# ---------------------------------------------------------------------------
# File I/O tools
# ---------------------------------------------------------------------------

def expand_file_refs(text, base_dir=None):
    """Expand ``{{file:path:start:end}}`` references in ``text`` to actual
    file content. Raises ``ValueError`` if the file is missing or the line
    range is invalid."""
    pattern = r"\{\{file:(.+?):(\d+):(\d+)\}\}"

    def replacer(match):
        path, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        path = os.path.abspath(os.path.join(base_dir or ".", path))
        if not os.path.isfile(path):
            raise ValueError(f"Referenced file does not exist: {path}")
        with open(path, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        if start < 1 or end > len(lines) or start > end:
            raise ValueError(f"Line range out of bounds: {path} has {len(lines)} lines, "
                             f"requested {start}-{end}")
        return "".join(lines[start - 1:end])

    return re.sub(pattern, replacer, text)


def file_patch(path: str, old_content: str, new_content: str):
    """Replace the unique occurrence of ``old_content`` in ``path``."""
    path = str(Path(path).resolve())
    try:
        if not os.path.exists(path):
            return {"status": "error", "msg": "File does not exist"}
        with open(path, "r", encoding="utf-8") as fp:
            full_text = fp.read()
        if not old_content:
            return {"status": "error", "msg": "old_content is empty; check the arguments."}
        count = full_text.count(old_content)
        if count == 0:
            return {"status": "error",
                    "msg": "No matching old text block found. Suggestion: re-read the file with "
                           "file_read to verify current content, then patch in smaller segments. "
                           "After repeated failures, ask the user; do NOT silently overwrite."}
        if count > 1:
            return {"status": "error",
                    "msg": f"Found {count} matches; cannot disambiguate. Provide a longer / more "
                           "specific old text block (include surrounding context lines) or split "
                           "the change into smaller patches."}
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(full_text.replace(old_content, new_content))
        return {"status": "success", "msg": "Local file edit succeeded."}
    except Exception as exc:
        return {"status": "error", "msg": str(exc)}


_read_dirs: set[str] = set()


def _scan_files(base, depth: int = 2):
    try:
        for e in os.scandir(base):
            if e.is_file():
                yield (e.name, e.path)
            elif depth > 0 and e.is_dir(follow_symlinks=False):
                yield from _scan_files(e.path, depth - 1)
    except (PermissionError, OSError):
        pass


def file_read(path, start: int = 1, keyword=None, count: int = 200,
              show_linenos: bool = True):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            stream = ((i, l.rstrip("\r\n")) for i, l in enumerate(fp, 1))
            stream = itertools.dropwhile(lambda x: x[0] < start, stream)
            if keyword:
                before = collections.deque(maxlen=count // 3)
                res = None
                for i, l in stream:
                    if keyword.lower() in l.lower():
                        res = list(before) + [(i, l)] + list(itertools.islice(
                            stream, count - len(before) - 1))
                        break
                    before.append((i, l))
                if res is None:
                    return (f"Keyword '{keyword}' not found after line {start}. "
                            f"Falling back to content from line {start}:\n\n"
                            + file_read(path, start, None, count, show_linenos))
            else:
                res = list(itertools.islice(stream, count))
            realcnt = len(res)
            l_max = min(max(100, 256_000 // max(realcnt, 1)), 8_000)
            tag = " ... [TRUNCATED]"
            remaining = sum(1 for _ in itertools.islice(stream, 5_000))
            total_lines = (res[0][0] - 1 if res else start - 1) + realcnt + remaining
            tl_str = f"{total_lines}+" if remaining >= 5_000 else str(total_lines)
            partial = total_lines > realcnt
            total_tag = (f"[FILE] {tl_str} lines"
                         + (f" | PARTIAL showing {realcnt}; assess need for more"
                            if partial else "") + "\n")
            res = [(i, l if len(l) <= l_max else l[:l_max] + tag) for i, l in res]
            result = "\n".join(f"{i}|{l}" if show_linenos else l for i, l in res)
            if show_linenos:
                result = total_tag + result
            elif partial:
                result += f"\n\n[FILE PARTIAL: showing {realcnt}/{tl_str} lines; assess need for more]"
            _read_dirs.add(os.path.dirname(os.path.abspath(path)))
            return result
    except FileNotFoundError:
        msg = f"Error: File not found: {path}"
        try:
            tgt = os.path.basename(path)
            scan = os.path.dirname(os.path.dirname(os.path.abspath(path)))
            roots = [scan] + [d for d in _read_dirs if not d.startswith(scan)]
            cands = list(itertools.islice((c for base in roots for c in _scan_files(base)), 2_000))
            top = sorted([(difflib.SequenceMatcher(None, tgt.lower(), c[0].lower()).ratio(), c)
                          for c in cands[:2_000]], key=lambda x: -x[0])[:5]
            top = [(s, c) for s, c in top if s > 0.3]
            if top:
                msg += "\n\nDid you mean:\n" + "\n".join(f"  {c[1]}  ({s:.0%})" for s, c in top)
        except Exception:
            pass
        return msg
    except Exception as exc:
        return f"Error: {exc}"


def log_skill_access(path):
    """Track how often each skill / SOP file is read for L1 maintenance."""
    if "skills" not in path and "sop" not in path.lower():
        return
    stats_file = os.path.join(_USER_DATA, "skill_access_stats.json")
    try:
        with open(stats_file, "r", encoding="utf-8") as fp:
            stats = json.load(fp)
    except Exception:
        stats = {}
    fname = os.path.basename(path)
    stats[fname] = {"count": stats.get(fname, {}).get("count", 0) + 1,
                    "last": datetime.now().strftime("%Y-%m-%d")}
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    with open(stats_file, "w", encoding="utf-8") as fp:
        json.dump(stats, fp, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class PhotoAgentsHandler(BaseHandler):
    """Tool dispatcher for Photo Agents.

    Each ``do_<tool>`` method is invoked by
    :func:`photoagents.core.loop.run_agent_session` when the LLM emits a
    ``tool_use`` block of that name. Methods are generators: they may
    ``yield`` display chunks during execution and must ``return`` a
    :class:`StepOutcome`.
    """

    def __init__(self, parent, last_history=None, cwd: str = "./temp"):
        self.parent = parent
        self.working: dict = {}
        self.cwd = cwd
        self.current_turn = 0
        self.history_info: list[str] = last_history if last_history else []
        self.code_stop_signal: list = []
        self._done_hooks: list = []

    # ----- helpers ---------------------------------------------------------

    def _get_abs_path(self, path):
        if not path:
            return ""
        return os.path.abspath(os.path.join(self.cwd, path))

    def _extract_code_block(self, response, code_type):
        code_type = {"python": "python|py",
                     "powershell": "powershell|ps1|pwsh",
                     "bash": "bash|sh|shell"}.get(code_type, re.escape(code_type))
        matches = re.findall(rf"```(?:{code_type})\n(.*?)\n```",
                             response.content, re.DOTALL)
        return matches[-1].strip() if matches else None

    def _get_anchor_prompt(self, skip: bool = False):
        if skip:
            return "\n"
        h_str = "\n".join(self.history_info[-40:])
        prompt = f"\n### [WORKING MEMORY]\n<history>\n{h_str}\n</history>"
        prompt += f"\nCurrent turn: {self.current_turn}\n"
        if self.working.get("key_info"):
            prompt += f"\n<key_info>{self.working.get('key_info')}</key_info>"
        if self.working.get("related_sop"):
            prompt += (f"\nIf anything is unclear, re-read "
                       f"{self.working.get('related_sop')}.")
        if getattr(self.parent, "verbose", False):
            try:
                print(prompt)
            except Exception:
                pass
        return prompt

    # ----- plan-mode helpers ----------------------------------------------

    def _in_plan_mode(self):
        return self.working.get("in_plan_mode")

    def _exit_plan_mode(self):
        self.working.pop("in_plan_mode", None)

    def enter_plan_mode(self, plan_path):
        self.working["in_plan_mode"] = plan_path
        self.max_turns = 100
        print(f"[Info] Entered plan mode with plan file: {plan_path}")
        return plan_path

    def _check_plan_completion(self):
        p = self._in_plan_mode() or ""
        if not os.path.isfile(p):
            return None
        try:
            return len(re.findall(r"\[ \]",
                                  open(p, encoding="utf-8", errors="replace").read()))
        except Exception:
            return None

    # ----- tool implementations -------------------------------------------

    def do_code_run(self, args, response):
        """Run a code block. Honors hard length limits — bulk data must be loaded
        from a file rather than embedded in the script."""
        code_type = args.get("type", "python")
        code = args.get("code") or args.get("script")
        if not code:
            code = self._extract_code_block(response, code_type)
            if not code:
                return StepOutcome(
                    "[Error] Code missing. Must use a reply code block or the 'script' arg.",
                    next_prompt="\n",
                )
        timeout = args.get("timeout", 60)
        raw_path = os.path.join(self.cwd, args.get("cwd", "./"))
        cwd = os.path.normpath(os.path.abspath(raw_path))
        code_cwd = os.path.normpath(self.cwd)
        if code_type == "python" and args.get("inline_eval"):
            ns = {"handler": self, "parent": self.parent}
            old_cwd = os.getcwd()
            try:
                os.chdir(cwd)
                try:
                    try:
                        result = repr(eval(code, ns))
                    except SyntaxError:
                        exec(code, ns)
                        result = ns.get("_r", "OK")
                except Exception as exc:
                    result = f"Error: {exc}"
            finally:
                os.chdir(old_cwd)
        else:
            result = yield from code_run(code, code_type, timeout, cwd,
                                          code_cwd=code_cwd,
                                          stop_signal=self.code_stop_signal)
        next_prompt = self._get_anchor_prompt(skip=args.get("_index", 0) > 0)
        return StepOutcome(result, next_prompt=next_prompt)

    def do_ask_user(self, args, response):
        question = args.get("question", "Please provide input:")
        candidates = args.get("candidates", [])
        result = ask_user(question, candidates)
        yield "Waiting for your answer ...\n"
        return StepOutcome(result, next_prompt="", should_exit=True)

    def do_web_scan(self, args, response):
        """Snapshot the current page + tab list; can also switch tabs.

        HTML is simplified, so floating chrome and sidebars may be filtered.
        Use ``web_execute_js`` to inspect filtered content.
        ``tabs_only=true`` skips the HTML body to save tokens."""
        tabs_only = args.get("tabs_only", False)
        switch_tab_id = args.get("switch_tab_id", None)
        text_only = args.get("text_only", False)
        result = web_scan(tabs_only=tabs_only,
                          switch_tab_id=switch_tab_id, text_only=text_only)
        content = result.pop("content", None)
        yield f"[Info] {result}\n"
        if content:
            result = (json.dumps(result, ensure_ascii=False, default=json_default)
                      + f"\n```html\n{content}\n```")
        return StepOutcome(result, next_prompt="\n")

    def do_web_execute_js(self, args, response):
        """Preferred web tool. Execute arbitrary JS for full browser control,
        with optional file-backed return for large payloads."""
        script = args.get("script", "") or self._extract_code_block(response, "javascript")
        if not script:
            return StepOutcome(
                "[Error] Script missing. Use a ```javascript block or the 'script' arg.",
                next_prompt="\n",
            )
        abs_path = self._get_abs_path(script.strip())
        if os.path.isfile(abs_path):
            with open(abs_path, "r", encoding="utf-8") as fp:
                script = fp.read()
        save_to_file = args.get("save_to_file", "")
        switch_tab_id = args.get("switch_tab_id") or args.get("tab_id")
        no_monitor = args.get("no_monitor", False)
        result = web_execute_js(script, switch_tab_id=switch_tab_id, no_monitor=no_monitor)
        if save_to_file and "js_return" in result:
            content = str(result["js_return"] or "")
            abs_path = self._get_abs_path(save_to_file)
            result["js_return"] = smart_format(content, max_str_len=170)
            try:
                with open(abs_path, "w", encoding="utf-8") as fp:
                    fp.write(str(content))
                result["js_return"] += f"\n\n[Saved full content to {abs_path}]"
            except Exception:
                result["js_return"] += f"\n\n[Failed to write file {abs_path}]"
        show = smart_format(json.dumps(result, ensure_ascii=False, indent=2,
                                        default=json_default), max_str_len=300)
        try:
            print("Web Execute JS Result:", show)
        except Exception:
            pass
        yield f"JS execution result:\n{show}\n"
        next_prompt = self._get_anchor_prompt(skip=args.get("_index", 0) > 0)
        result = json.dumps(result, ensure_ascii=False, default=json_default)
        return StepOutcome(smart_format(result, max_str_len=8_000),
                           next_prompt=next_prompt)

    def do_file_patch(self, args, response):
        path = self._get_abs_path(args.get("path", ""))
        yield f"[Action] Patching file: {path}\n"
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")
        try:
            new_content = expand_file_refs(new_content, base_dir=self.cwd)
        except ValueError as exc:
            yield f"[Status] [ERR] Reference expansion failed: {exc}\n"
            return StepOutcome({"status": "error", "msg": str(exc)}, next_prompt="\n")
        result = file_patch(path, old_content, new_content)
        yield f"\n{result}\n"
        return StepOutcome(result,
                           next_prompt=self._get_anchor_prompt(skip=args.get("_index", 0) > 0))

    def do_file_write(self, args, response):
        """Bulk-write a whole file. For surgical edits, prefer ``file_patch``.
        Content must live inside a ``<file_content>`` tag or a fenced code block
        in the assistant reply body."""
        path = self._get_abs_path(args.get("path", ""))
        mode = args.get("mode", "overwrite")  # overwrite/append/prepend
        action_str = {"prepend": "Prepending to", "append": "Appending to"}.get(mode, "Overwriting")
        yield f"[Action] {action_str} file: {os.path.basename(path)}\n"

        def extract_robust_content(text):
            tag = re.search(r"<file_content[^>]*>(.*)</file_content>", text, re.DOTALL)
            if tag:
                return tag.group(1).strip()
            s, e = text.find("```"), text.rfind("```")
            if -1 < s < e:
                return text[text.find("\n", s) + 1: e].strip()
            return None

        blocks = extract_robust_content(response.content)
        if not blocks:
            yield "[Status] [ERR] No <file_content> block found in the reply.\n"
            return StepOutcome({"status": "error",
                                "msg": "No content found. Put content inside "
                                       "<file_content>...</file_content> tags in your reply body "
                                       "before calling file_write."},
                               next_prompt="\n")
        try:
            new_content = expand_file_refs(blocks, base_dir=self.cwd)
            if mode == "prepend":
                old = (open(path, "r", encoding="utf-8").read()
                       if os.path.exists(path) else "")
                open(path, "w", encoding="utf-8").write(new_content + old)
            else:
                with open(path, "a" if mode == "append" else "w", encoding="utf-8") as fp:
                    fp.write(new_content)
            yield f"[Status] [OK] {mode.capitalize()} succeeded ({len(new_content)} bytes)\n"
            return StepOutcome({"status": "success", "writed_bytes": len(new_content)},
                               next_prompt=self._get_anchor_prompt(skip=args.get("_index", 0) > 0))
        except Exception as exc:
            yield f"[Status] [ERR] Write failed: {exc}\n"
            return StepOutcome({"status": "error", "msg": str(exc)}, next_prompt="\n")

    def do_file_read(self, args, response):
        """Read a file from line ``start``. If ``keyword`` is set, return
        context around the first case-insensitive match instead."""
        path = self._get_abs_path(args.get("path", ""))
        yield f"\n[Action] Reading file: {path}\n"
        result = file_read(
            path,
            start=args.get("start", 1),
            keyword=args.get("keyword"),
            count=args.get("count", 200),
            show_linenos=args.get("show_linenos", True),
        )
        if args.get("show_linenos", True) and not result.startswith("Error:"):
            result = ("Since show_linenos is set, each line is prefixed with "
                      "'(line_number|) content'.\n" + result)
        if " ... [TRUNCATED]" in result:
            result += ("\n\n(Some lines were truncated; switch to code_run "
                       "to read the full content if needed.)")
        result = smart_format(result, max_str_len=20_000,
                              omit_str="\n\n[omitted long content]\n\n")
        next_prompt = self._get_anchor_prompt(skip=args.get("_index", 0) > 0)
        log_skill_access(path)
        if "skills" in path or "sop" in path.lower():
            next_prompt += ("\n[SYSTEM TIPS] You are reading a skill or SOP file. "
                            "If you decide to follow this SOP, extract the key points "
                            "(especially toward the end) and update working memory.")
        return StepOutcome(result, next_prompt=next_prompt)

    def do_update_working_checkpoint(self, args, response):
        """Set the per-task checkpoint (key_info / related_sop)."""
        key_info = args.get("key_info", "")
        related_sop = args.get("related_sop", "")
        if "key_info" in args:
            self.working["key_info"] = key_info
        if "related_sop" in args:
            self.working["related_sop"] = related_sop
        self.working["passed_sessions"] = 0
        yield "[Info] Updated key_info and related_sop.\n"
        return StepOutcome({"result": "working key_info updated"},
                           next_prompt=self._get_anchor_prompt(skip=args.get("_index", 0) > 0))

    def do_no_tool(self, args, response):
        """Engine-only synthetic tool: triggered when the model finishes a turn
        without calling any tool. We use it to second-guess "obvious"
        omissions (empty reply, plan-mode false-completion, lone code block
        with no actual instruction)."""
        content = getattr(response, "content", "") or ""
        thinking = getattr(response, "thinking", "") or ""
        if not response or (not content.strip() and not thinking.strip()):
            yield "[Warn] LLM returned an empty response. Retrying...\n"
            return StepOutcome({}, next_prompt="[System] Blank response, regenerate and tooluse")
        if len(content) > 50 and ("[!!! Stream interrupted" in content[-100:]
                                   or "!!!Error:" in content[-100:]):
            return StepOutcome({}, next_prompt="[System] Incomplete response. Regenerate and tooluse.")
        if "max_tokens !!!]" in content[-100:]:
            return StepOutcome({}, next_prompt="[System] max_tokens limit reached. "
                                                 "Use multiple smaller steps to do it.")

        # Plan-mode: refuse premature completion claims that lack a verify pass.
        if self._in_plan_mode() and any(kw in content for kw in
                                          ["task complete", "all done", "finished all",
                                           "task completed", "all completed"]):
            if ("VERDICT" not in content and "[VERIFY]" not in content
                    and "verify subagent" not in content.lower()):
                yield "[Warn] Plan-mode completion claim intercepted.\n"
                return StepOutcome(
                    {},
                    next_prompt=("[Verify intercept] You claimed completion in plan mode but "
                                 "did not run the [VERIFY] step. Per plan_sop §4, launch the "
                                 "verify subagent and obtain a VERDICT before claiming completion."),
                )

        # Detect "one large code block, no actual tool call" — most likely a
        # forgotten code_run / file_write.
        code_block_pattern = r"```[a-zA-Z0-9_]*\n[\s\S]{50,}?```"
        blocks = re.findall(code_block_pattern, content)
        if len(blocks) == 1:
            m = re.search(code_block_pattern, content)
            after_block = content[m.end():]
            if not after_block.strip():
                residual = content.replace(m.group(0), "")
                residual = re.sub(r"<thinking>[\s\S]*?</thinking>", "",
                                  residual, flags=re.IGNORECASE)
                residual = re.sub(r"<summary>[\s\S]*?</summary>", "",
                                  residual, flags=re.IGNORECASE)
                clean_residual = re.sub(r"\s+", "", residual)
                if len(clean_residual) <= 30:
                    yield ("[Info] Detected large code block without tool call and no extra "
                           "natural language. Requesting clarification.\n")
                    return StepOutcome(
                        {},
                        next_prompt=(
                            "[System] Your previous reply was mostly a large code block but you "
                            "did not call any tool this turn.\n"
                            "If this code is meant to run, be written, or analyzed further, "
                            "rewrite the reply and explicitly call the appropriate tool "
                            "(e.g. code_run, file_write, file_patch).\n"
                            "If you are only showing the code to the user, add natural-language "
                            "commentary and clarify whether further action is needed."
                        ),
                    )

        if self._in_plan_mode():
            remaining = self._check_plan_completion()
            if remaining == 0:
                self._exit_plan_mode()
                yield "[Info] Plan complete: 0 [ ] checkboxes remain in plan.md. Exiting plan mode.\n"

        yield "[Info] Final response to user.\n"
        return StepOutcome(response, next_prompt=None)

    def do_start_long_term_update(self, args, response):
        """Agent-initiated checkpoint of long-term memory."""
        prompt = ("### [Distill experience] Since you believe the current task contains "
                  "information worth remembering, extract environment facts, user "
                  "preferences, or important steps from the most recent task that have been "
                  "**fact-verified and remain valid long-term**, then update memory.\n"
                  "This tool only marks the start of the consolidation flow. If memory was "
                  "already updated, or there is nothing worth remembering, ignore this call.\n"
                  "**If there is no verified, future-useful information, ignore this call!**\n"
                  "**Only extract action-verified information**:\n"
                  "- **Environment facts** (paths / credentials / config) -> `file_patch` "
                  "L2, sync L1\n"
                  "- **Complex-task experience** (key pitfalls / preconditions / important "
                  "steps) -> L3, distilled SOP (record only the core points you got burned by "
                  "and had to retry repeatedly)\n"
                  "**Forbidden**: ephemeral variables, raw reasoning chains, unverified info, "
                  "common knowledge, easily reproducible details, or anything you only did "
                  "without verifying.\n"
                  "**Procedure**: strictly follow the L0 memory-management SOP. First "
                  "`file_read` the existing entry -> classify -> minimal update -> skip if no "
                  "new content. Make the smallest possible local change to the memory store.\n"
                  ) + get_global_memory()
        yield "[Info] Start distilling memory for long-term storage.\n"
        path = os.path.join(_SKILLS, "memory_management_sop.md")
        if os.path.exists(path):
            result = ("Auto-loaded L0 content:\n"
                      + file_read(path, show_linenos=False))
        else:
            result = "Memory Management SOP not found. Do not update memory."
        return StepOutcome(result, next_prompt=prompt)

    # ----- per-turn callback ----------------------------------------------

    def turn_end_callback(self, response, tool_calls, tool_results, turn,
                         next_prompt, exit_reason):
        cleaned = re.sub(r"```.*?```|<thinking>.*?</thinking>", "",
                         response.content, flags=re.DOTALL)
        rsumm = re.search(r"<summary>(.*?)</summary>", cleaned, re.DOTALL)
        if rsumm:
            summary = rsumm.group(1).strip()
        else:
            tc = tool_calls[0]  # at least one — no_tool always synthesized
            tool_name, args = tc["tool_name"], tc["args"]
            clean_args = {k: v for k, v in args.items() if not k.startswith("_")}
            summary = f"Called tool {tool_name}, args: {clean_args}"
            if tool_name == "no_tool":
                summary = "Answered the user directly."
            next_prompt += ("\n[DANGER] You omitted <summary>. Per protocol, always emit a "
                             "minimal one-line summary in <summary> on every reply!")
        summary = smart_format(summary, max_str_len=100)
        self.history_info.append(f"[Agent] {summary}")
        if turn % 65 == 0 and "plan" not in str(self.working.get("related_sop")):
            next_prompt += (f"\n\n[DANGER] {turn} turns in a row. You MUST summarize and ask_user. "
                            "Do not keep retrying.")
        elif turn % 7 == 0:
            next_prompt += (f"\n\n[DANGER] {turn} turns in a row. No useless retries. If no real "
                            "progress, switch strategy: 1. probe physical boundaries, 2. ask the "
                            "user. Save context with update_working_checkpoint if needed.")
        elif turn % 10 == 0:
            next_prompt += get_global_memory()

        plan = self._in_plan_mode()
        if plan and turn >= 10 and turn % 5 == 0:
            next_prompt = (f"[Plan Hint] You are in plan mode. file_read({plan}) to confirm the "
                            "current step, and quote it at the top of your reply: "
                            "Current step: ...\n\n" + next_prompt)
        if plan and turn >= 90:
            next_prompt += (f"\n\n[DANGER] Plan mode has run {turn} turns — limit reached. You "
                            "must ask_user with a status report and confirm whether to continue.")

        injkeyinfo = consume_file(self.parent.task_dir, "_keyinfo")
        injprompt = consume_file(self.parent.task_dir, "_intervene")
        if injkeyinfo:
            self.working["key_info"] = self.working.get("key_info", "") + f"\n[MASTER] {injkeyinfo}"
        if injprompt:
            next_prompt += f"\n\n[MASTER] {injprompt}\n"
        for hook in getattr(self.parent, "_turn_end_hooks", {}).values():
            hook(locals())
        return next_prompt
