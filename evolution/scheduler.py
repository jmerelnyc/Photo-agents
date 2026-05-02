"""Cron-style scheduler driven by the runtime's ``--reflect`` mode.

Reads JSON task descriptors from ``./sche_tasks/*.json``, fires any whose
schedule has come due (with cooldown bookkeeping in ``./sche_tasks/done/``),
and once every 12 hours triggers an L4 session-archive sweep.

A single TCP port (45762) acts as a process-wide lock so that only one
scheduler can run at a time. A second invocation will fail at ``bind`` and
the parent runtime will exit immediately.
"""

import logging
import os
import socket as _socket
import sys
import time as _time
from datetime import datetime, timedelta


# Process-wide lock. Reuse the bound socket across module reloads.
try:
    _lock  # type: ignore[name-defined]
except NameError:
    _lock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    _lock.bind(("127.0.0.1", 45762))
    _lock.listen(1)


INTERVAL = 120
ONCE = False

_dir = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(_dir, "../sche_tasks")
DONE = os.path.join(_dir, "../sche_tasks/done")
_LOG = os.path.join(_dir, "../sche_tasks/scheduler.log")

_logger = logging.getLogger("photoagents.scheduler")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    _fh = logging.FileHandler(_LOG, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                        datefmt="%Y-%m-%d %H:%M"))
    _logger.addHandler(_fh)

# Maximum delay window in hours. Tasks more than this many hours past their
# scheduled time are skipped so we do not fire stale work after a long
# downtime.
DEFAULT_MAX_DELAY = 6
_l4_t = 0.0  # last L4 archive sweep timestamp


def _parse_cooldown(repeat: str) -> timedelta:
    """Map a ``repeat`` field to a cooldown that is slightly shorter than the
    nominal period (defends against clock drift)."""
    if repeat == "once":
        return timedelta(days=999_999)
    if repeat in ("daily", "weekday"):
        return timedelta(hours=20)
    if repeat == "weekly":
        return timedelta(days=6)
    if repeat == "monthly":
        return timedelta(days=27)
    if repeat.startswith("every_"):
        try:
            parts = repeat.split("_")
            n = int(parts[1].rstrip("hdm"))
            unit = parts[1][-1]
            if unit == "h":
                return timedelta(hours=n)
            if unit == "m":
                return timedelta(minutes=n)
            if unit == "d":
                return timedelta(days=n)
        except (ValueError, IndexError):
            pass
    _logger.warning("Unknown repeat type: %s, falling back to 20h cooldown", repeat)
    return timedelta(hours=20)


def _last_run(tid: str, done_files):
    """Find the most recent completed-run timestamp for task id ``tid``."""
    latest = None
    for df in done_files:
        if not df.endswith(f"_{tid}.md"):
            continue
        try:
            t = datetime.strptime(df[:15], "%Y-%m-%d_%H%M")
        except ValueError:
            continue
        if latest is None or t > latest:
            latest = t
    return latest


def check():
    import json

    # 12-hour silent L4 archive sweep.
    global _l4_t
    if _time.time() - _l4_t > 43_200:
        _l4_t = _time.time()
        try:
            sys.path.insert(0, os.path.expanduser("~/.photoagents/sessions"))
            from compress_session import batch_process  # type: ignore[import-not-found]
            raw_dir = os.path.join(_dir, "../temp/model_responses")
            r = batch_process(raw_dir, dry_run=False)
            print(f"[L4 cron] {r}")
        except Exception as exc:  # noqa: BLE001
            _logger.error("L4 archive failed: %s", exc)

    if not os.path.isdir(TASKS):
        return None
    now = datetime.now()
    os.makedirs(DONE, exist_ok=True)
    done_files = set(os.listdir(DONE))

    for fname in sorted(os.listdir(TASKS)):
        if not fname.endswith(".json"):
            continue
        tid = fname[:-5]
        try:
            with open(os.path.join(TASKS, fname), encoding="utf-8") as fp:
                task = json.loads(fp.read())
        except Exception as exc:  # noqa: BLE001
            _logger.error("JSON parse error for %s: %s", fname, exc)
            continue
        if not task.get("enabled", False):
            continue

        repeat = task.get("repeat", "daily")
        sched = task.get("schedule", "00:00")
        try:
            h, m = map(int, sched.split(":"))
        except Exception as exc:  # noqa: BLE001
            _logger.error("Invalid schedule format in %s: %r (%s)", fname, sched, exc)
            continue

        # Weekday-only tasks skip Saturday and Sunday.
        if repeat == "weekday" and now.weekday() >= 5:
            continue

        # Not yet due this clock-day.
        if now.hour < h or (now.hour == h and now.minute < m):
            continue

        # Skip stale runs that are more than ``max_delay_hours`` past schedule.
        max_delay = task.get("max_delay_hours", DEFAULT_MAX_DELAY)
        sched_minutes = h * 60 + m
        now_minutes = now.hour * 60 + now.minute
        if (now_minutes - sched_minutes) > max_delay * 60:
            _logger.info(
                "SKIP %s: %dmin past schedule, exceeds max_delay=%dh",
                tid, now_minutes - sched_minutes, max_delay,
            )
            continue

        # Cooldown check (avoid firing twice in one period).
        last = _last_run(tid, done_files)
        cooldown = _parse_cooldown(repeat)
        if last and (now - last) < cooldown:
            continue

        _logger.info(
            "TRIGGER %s (repeat=%s, schedule=%s, last_run=%s)",
            tid, repeat, sched, last,
        )
        ts = now.strftime("%Y-%m-%d_%H%M")
        rpt = os.path.join(DONE, f"{ts}_{tid}.md")
        prompt = task.get("prompt", "")
        return (
            f"[Scheduled task] {tid}\n"
            f"[Report path] {rpt}\n\n"
            f"First read scheduled_task_sop to understand the execution flow, then run:\n\n"
            f"{prompt}\n\n"
            f"When done, write the execution report to {rpt}."
        )

    return None
