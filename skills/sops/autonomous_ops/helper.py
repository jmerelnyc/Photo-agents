"""autonomous_task helpers — the API surface used by the autonomous-action loop.

Location: ``photoagents/skills/sops/autonomous_ops/``.
Usage::

    from photoagents.skills.sops.autonomous_ops import helper as autonomous_task

The four entry points:
  - ``get_todo()``        -> return the contents of TODO.txt
  - ``get_history(n)``    -> return the last ``n`` history lines
  - ``complete_task()``   -> move the report, assign it a number, append history,
                             return the instruction telling the caller to update TODO
  - ``set_todo()``        -> return the absolute path of TODO.txt
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

# Path layout (relative to this module).
_MODULE_DIR = Path(__file__).resolve().parent          # photoagents/skills/sops/autonomous_ops/
_SKILLS_DIR = _MODULE_DIR.parent.parent                # photoagents/skills/
_PACKAGE_DIR = _SKILLS_DIR.parent                      # photoagents/
_AGENT_DIR = _PACKAGE_DIR.parent
_TEMP_DIR = _AGENT_DIR / "temp"
_REPORTS_DIR = _TEMP_DIR / "autonomous_reports"
_HISTORY_FILE = _REPORTS_DIR / "history.txt"
_TODO_FILE = _TEMP_DIR / "TODO.txt"


def _next_report_number() -> int:
    """Scan history.txt and return the next available R<NN> number."""
    if not _HISTORY_FILE.exists():
        return 1
    with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    nums = [int(m) for m in re.findall(r'R(\d+)', content)]
    if not nums:
        return 1
    return max(nums) + 1


def get_todo() -> str:
    """Return the contents of TODO.txt; emit a hint if the file is missing."""
    if not _TODO_FILE.exists():
        return f"[autonomous_task] TODO.txt does not exist, expected path: {_TODO_FILE}"
    with open(_TODO_FILE, "r", encoding="utf-8") as f:
        return f.read()


def get_history(n: int = 20) -> str:
    """Return the first ``n`` lines of history.txt (newest first)."""
    if not _HISTORY_FILE.exists():
        return f"[autonomous_task] history.txt does not exist, expected path: {_HISTORY_FILE}"
    with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[:n])


def set_todo(*args, **kwargs) -> str:
    """Return the absolute path of TODO.txt so the caller can read/write it directly."""
    return f'path: {str(_TODO_FILE)}'


def complete_task(taskname: str, historyline: str, report_path: str) -> str:
    """Atomic completion of a task.

    Steps:
      1. Move ``report_path`` -> ``autonomous_reports/R{XX}_{taskname}.md`` (auto-numbered).
      2. Prepend ``historyline`` to history.txt (single line, validated).
      3. Return a string instructing the agent to update TODO itself.

    Args:
        taskname: short task name used in the report filename (e.g. ``"morning_briefing"``).
        historyline: single-line history entry; the date is added automatically
            (format: ``"area | topic | conclusion"``).
        report_path: path to the report the agent has already written
            (absolute, or relative to cwd).

    Returns:
        Success message + TODO update instruction, or an error message.
    """
    if "\n" in historyline.strip():
        return "[ERROR] historyline must be a single line and cannot contain newlines"

    report = Path(report_path).resolve()
    if not report.exists():
        return f"[ERROR] report file does not exist: {report_path}"

    if not _REPORTS_DIR.exists():
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    rnum = _next_report_number()
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', taskname).strip()
    dest_name = f"R{rnum}_{safe_name}.md"
    dest_path = _REPORTS_DIR / dest_name

    try:
        shutil.move(str(report), str(dest_path))
    except Exception as e:
        return f"[ERROR] failed to move report: {e}"

    # Prepend the history entry.
    # Strip any number/date the agent may have already added so we always rebuild it consistently.
    line = historyline.strip()
    line = re.sub(r'^R\d+\s*\|\s*', '', line)
    line = re.sub(r'^\d{4}-\d{2}-\d{2}\s*\|\s*', '', line)
    today = datetime.now().strftime('%Y-%m-%d')
    line = f"R{rnum} | {today} | {line}"

    try:
        existing = ""
        if _HISTORY_FILE.exists():
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                existing = f.read()
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write(line + "\n" + existing)
    except Exception as e:
        # Roll back: move the report file back to its original location.
        try:
            shutil.move(str(dest_path), str(report))
        except Exception:
            pass
        return f"[ERROR] failed to write history: {e} (report move was rolled back)"

    return (
        f"Done. Report saved as: {dest_name}\n"
        f"History line recorded: {line}\n"
        f"Now mark the corresponding entry in {_TODO_FILE} as [x] R{rnum}, "
        f"then exit. Remaining TODOs will be picked up next run."
    )


if __name__ == "__main__":
    print(f"TEMP_DIR:    {_TEMP_DIR}")
    print(f"REPORTS_DIR: {_REPORTS_DIR}")
    print(f"HISTORY:     {_HISTORY_FILE}")
    print(f"TODO:        {_TODO_FILE}")
    print(f"Next R#:     R{_next_report_number()}")
    print(f"\n--- TODO ---\n{get_todo()[:200]}")
    print(f"\n--- History (5) ---\n{get_history(5)}")
