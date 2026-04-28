"""Agent runner loop.

This is the small inner driver that owns the LLM message list, asks the model
for the next move, dispatches the resulting tool calls to a handler, and
threads the tool outputs back into the conversation. Everything substantive
lives in the handler — :class:`photoagents.core.handler.PhotoAgentsHandler` —
or in the LLM session classes from :mod:`photoagents.llm.router`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class StepOutcome:
    """Result of a single tool dispatch.

    ``data`` is the structured payload that gets serialized and fed back to
    the model as the tool result. ``next_prompt`` is appended to the next
    user turn; an empty / falsy value means "current task is done".
    """
    data: Any
    next_prompt: Optional[str] = None
    should_exit: bool = False


def try_call_generator(func, *args, **kwargs):
    """Invoke ``func``; if it returns a generator, exhaust it via ``yield from``."""
    ret = func(*args, **kwargs)
    if hasattr(ret, "__iter__") and not isinstance(ret, (str, bytes, dict, list)):
        ret = yield from ret
    return ret


def exhaust(gen):
    """Drive a generator to completion and return its ``StopIteration.value``."""
    try:
        while True:
            next(gen)
    except StopIteration as exc:
        return exc.value


def json_default(obj):
    return list(obj) if isinstance(obj, set) else str(obj)


def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy()
        data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace("\\n", "\n")


# ---------------------------------------------------------------------------
# Handler base
# ---------------------------------------------------------------------------

class BaseHandler:
    """Subclass and add ``do_<tool_name>`` methods to handle each tool."""

    def tool_before_callback(self, tool_name, args, response):
        pass

    def tool_after_callback(self, tool_name, args, response, ret):
        pass

    def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
        return next_prompt

    def dispatch(self, tool_name, args, response, index=0):
        method_name = f"do_{tool_name}"
        if hasattr(self, method_name):
            args["_index"] = index
            _ = yield from try_call_generator(self.tool_before_callback, tool_name, args, response)
            ret = yield from try_call_generator(getattr(self, method_name), args, response)
            _ = yield from try_call_generator(self.tool_after_callback, tool_name, args, response, ret)
            return ret
        if tool_name == "bad_json":
            return StepOutcome(None, next_prompt=args.get("msg", "bad_json"), should_exit=False)
        yield f"Unknown tool: {tool_name}\n"
        return StepOutcome(None, next_prompt=f"Unknown tool {tool_name}", should_exit=False)


# ---------------------------------------------------------------------------
# The main loop
# ---------------------------------------------------------------------------

def run_agent_session(client, system_prompt, user_input, handler, tools_schema,
                     max_turns=40, verbose=True, initial_user_content=None):
    """Drive the LLM-tool loop until the task ends or ``max_turns`` is hit.

    Yields display chunks as they are produced so the calling frontend can
    stream them. The ``return`` value is the final ``exit_reason`` dict.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": initial_user_content if initial_user_content is not None else user_input},
    ]
    turn = 0
    handler.max_turns = max_turns

    while turn < handler.max_turns:
        turn += 1
        md = "**" if verbose else ""
        yield f"{md}LLM Running (Turn {turn}) ...{md}\n\n"
        # Periodically flush the cached tool descriptions so the prompt does not
        # grow without bound on long sessions.
        if turn % 10 == 0:
            client.last_tools = ""
        response_gen = client.chat(messages=messages, tools=tools_schema)
        if verbose:
            response = yield from response_gen
            yield "\n\n"
        else:
            response = exhaust(response_gen)
            cleaned = _clean_content(response.content)
            if cleaned:
                yield cleaned + "\n"

        if not response.tool_calls:
            tool_calls = [{"tool_name": "no_tool", "args": {}}]
        else:
            tool_calls = [
                {"tool_name": tc.function.name,
                 "args": json.loads(tc.function.arguments),
                 "id": tc.id}
                for tc in response.tool_calls
            ]

        tool_results = []
        next_prompts = set()
        exit_reason = {}
        for ii, tc in enumerate(tool_calls):
            tool_name, args, tid = tc["tool_name"], tc["args"], tc.get("id", "")
            if tool_name != "no_tool":
                if verbose:
                    yield f"\U0001f6e0\ufe0f Tool: `{tool_name}`  \U0001f4e5 args:\n````text\n{get_pretty_json(args)}\n````\n"
                else:
                    yield f"\U0001f6e0\ufe0f {tool_name}({_compact_tool_args(tool_name, args)})\n\n\n"
            handler.current_turn = turn
            gen = handler.dispatch(tool_name, args, response, index=ii)
            try:
                first = next(gen)
                def proxy(_first=first, _gen=gen):
                    yield _first
                    return (yield from _gen)
                if verbose:
                    yield "`````\n"
                outcome = (yield from proxy()) if verbose else exhaust(proxy())
                if verbose:
                    yield "`````\n"
            except StopIteration as exc:
                outcome = exc.value

            if outcome.should_exit:
                exit_reason = {"result": "EXITED", "data": outcome.data}
                break
            if not outcome.next_prompt:
                exit_reason = {"result": "CURRENT_TASK_DONE", "data": outcome.data}
                break
            if outcome.next_prompt.startswith("Unknown tool"):
                client.last_tools = ""
            if outcome.data is not None and tool_name != "no_tool":
                if type(outcome.data) in (dict, list):
                    datastr = json.dumps(outcome.data, ensure_ascii=False, default=json_default)
                else:
                    datastr = str(outcome.data)
                tool_results.append({"tool_use_id": tid, "content": datastr})
            next_prompts.add(outcome.next_prompt)

        if len(next_prompts) == 0 or exit_reason:
            if len(handler._done_hooks) == 0 or exit_reason.get("result", "") == "EXITED":
                break
            next_prompts.add(handler._done_hooks.pop(0))
        next_prompt = handler.turn_end_callback(response, tool_calls, tool_results, turn,
                                                "\n".join(next_prompts), exit_reason)
        # The full conversation history is owned by the LLM session itself,
        # so each iteration we only ship the *new* user message.
        messages = [{"role": "user", "content": next_prompt, "tool_results": tool_results}]
    if exit_reason:
        handler.turn_end_callback(response, tool_calls, tool_results, turn, "", exit_reason)
    return exit_reason or {"result": "MAX_TURNS_EXCEEDED"}


# Backwards-compat alias for any external code that still imports the old name.
agent_runner_loop = run_agent_session


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _clean_content(text):
    if not text:
        return ""

    def _shrink_code(match):
        lines = match.group(0).split("\n")
        lang = lines[0].replace("```", "").strip()
        body = [l for l in lines[1:-1] if l.strip()]
        if len(body) <= 6:
            return match.group(0)
        preview = "\n".join(body[:5])
        return f"```{lang}\n{preview}\n  ... ({len(body)} lines)\n```"

    text = re.sub(r"```[\s\S]*?```", _shrink_code, text)
    for pat in [
        r"<file_content>[\s\S]*?</file_content>",
        r"<tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>",
        r"(\r?\n){3,}",
    ]:
        text = re.sub(pat, "\n\n" if "\\n" in pat else "", text)
    return text.strip()


def _compact_tool_args(name, args):
    a = {k: v for k, v in args.items() if k != "_index"}
    for k in ("path",):
        if k in a:
            a[k] = os.path.basename(a[k])
    if name == "update_working_checkpoint":
        s = a.get("key_info", "")
        return (s[:60] + "...") if len(s) > 60 else s
    if name == "ask_user":
        q = str(a.get("question", ""))
        cs = a.get("candidates") or []
        if cs:
            q += "\ncandidates:\n" + "\n".join(f"- {c}" for c in cs)
        return q
    s = json.dumps(a, ensure_ascii=False)
    return (s[:120] + "...") if len(s) > 120 else s
