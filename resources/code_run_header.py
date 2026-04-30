"""Prelude injected at the top of every ``code_run`` script.

* Wires subprocess.run output through a tolerant decoder so non-UTF-8 byte
  streams (Windows GBK, etc.) do not blow up on ``.decode()``.
* Hides Windows console windows for any subprocess we spawn.
* Adds the package's skills/ directory to ``sys.path`` so user scripts can
  import L3 helpers directly.
* Replaces sys.excepthook with a hint that nudges the agent to probe and
  pip-install when an Import/AttributeError fires.
"""

import os
import subprocess
import sys


sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills")
)


_orig_run = subprocess.run


def _decode(b):
    if not b:
        return ""
    if isinstance(b, str):
        return b
    try:
        return b.decode()
    except Exception:
        return b.decode("gbk", "replace")


def _run(*a, **k):
    text = k.pop("text", 0) | k.pop("universal_newlines", 0)
    enc = k.pop("encoding", None)
    k.pop("errors", None)
    if enc:
        text = 1
    if text and isinstance(k.get("input"), str):
        k["input"] = k["input"].encode()
    r = _orig_run(*a, **k)
    if text:
        if r.stdout is not None:
            r.stdout = _decode(r.stdout)
        if r.stderr is not None:
            r.stderr = _decode(r.stderr)
    return r


subprocess.run = _run

_orig_popen_init = subprocess.Popen.__init__


def _popen_init(self, *a, **k):
    if os.name == "nt":
        k["creationflags"] = (k.get("creationflags") or 0) | 0x0800_0000
    _orig_popen_init(self, *a, **k)


subprocess.Popen.__init__ = _popen_init

sys.excepthook = (
    lambda t, v, tb: (
        sys.__excepthook__(t, v, tb),
        print("\n[Agent Hint]: NO GUESSING! You MUST probe first. "
              "If a common package is missing, pip-install it."),
    ) if issubclass(t, (ImportError, AttributeError)) else sys.__excepthook__(t, v, tb)
)
