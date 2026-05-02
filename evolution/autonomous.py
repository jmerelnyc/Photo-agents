"""Idle-time autonomous trigger.

When the user has been idle for ``INTERVAL`` seconds, the runtime asks the
agent to read its autonomous-operations SOP and execute background work.
"""

INTERVAL = 1800  # 30 minutes
ONCE = False


def check():
    return (
        "[AUTO] User has been idle for over 30 minutes. As an autonomous "
        "agent, read the autonomous-operations SOP and execute background "
        "tasks."
    )
