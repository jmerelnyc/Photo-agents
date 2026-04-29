"""Remote-validated Photo Agents API key gate.

The runtime calls :func:`ensure_authenticated` before doing anything else.
That function:

1. Locates the user's API key (env var, on-disk config, or interactive prompt).
2. Validates the key against ``LICENSE_ENDPOINT`` over HTTPS.
3. Caches a successful validation for 24 hours so we do not hammer the
   endpoint on every run.
4. Exits the process with a clear error if the key is missing or rejected.

On-disk state lives in ``~/.photoagents/config.json``::

    {
      "api_key": "pk_live_...",
      "last_validated_at": 1714560000,
      "validation_ttl": 86400,
      "tier": "pro",
      "expires_at": "2026-12-31T23:59:59Z"
    }
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


LICENSE_ENDPOINT = "https://photo-agents.com/v1/keys/validate"
SIGNUP_URL = "https://photo-agents.com/account/keys"
CLIENT_VERSION = "0.1.0"

CONFIG_DIR = Path.home() / ".photoagents"
CONFIG_PATH = CONFIG_DIR / "config.json"

VALIDATION_TTL_SECONDS = 24 * 60 * 60  # 24 hours
ENV_KEY = "PHOTOAGENTS_API_KEY"


class LicenseError(RuntimeError):
    """Raised when the API key gate cannot be satisfied."""


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _read_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # restrict perms on POSIX so other local users cannot read the key
    if os.name != "nt":
        try:
            CONFIG_PATH.chmod(0o600)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Key location
# ---------------------------------------------------------------------------

def load_api_key(*, prompt_if_missing: bool = True) -> str | None:
    """Return the user's Photo Agents API key, or ``None`` if unavailable.

    Lookup order:
      1. ``PHOTOAGENTS_API_KEY`` environment variable.
      2. ``api_key`` field in ``~/.photoagents/config.json``.
      3. If ``prompt_if_missing`` and stdin is a tty, prompt interactively
         and offer to persist the answer.
    """
    env_key = os.environ.get(ENV_KEY, "").strip()
    if env_key:
        return env_key

    cfg = _read_config()
    saved = (cfg.get("api_key") or "").strip()
    if saved:
        return saved

    if not prompt_if_missing or not sys.stdin.isatty():
        return None

    print(
        f"\nA Photo Agents API key is required.\n"
        f"Sign in and copy yours from {SIGNUP_URL}\n"
    )
    try:
        entered = getpass.getpass("Photo Agents API key: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None

    if not entered:
        return None

    answer = input("Save this key for future runs? [Y/n] ").strip().lower()
    if answer in ("", "y", "yes"):
        cfg["api_key"] = entered
        _write_config(cfg)

    return entered


# ---------------------------------------------------------------------------
# Remote validation
# ---------------------------------------------------------------------------

def validate_api_key(api_key: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """POST the key to LICENSE_ENDPOINT and return the parsed response.

    Raises :class:`LicenseError` on rejection or transport failure.
    Successful responses look like::

        {"valid": true, "tier": "pro", "expires_at": "2026-12-31T23:59:59Z"}
    """
    payload = {"api_key": api_key, "client_version": CLIENT_VERSION}
    try:
        resp = requests.post(LICENSE_ENDPOINT, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise LicenseError(f"Could not reach Photo Agents license server: {exc}") from exc

    if resp.status_code == 401 or resp.status_code == 403:
        raise LicenseError("Photo Agents API key was rejected (unauthorized).")
    if resp.status_code >= 400:
        raise LicenseError(
            f"Photo Agents license server returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise LicenseError(f"License server returned non-JSON body: {exc}") from exc

    if not body.get("valid"):
        reason = body.get("reason") or "unknown reason"
        raise LicenseError(f"Photo Agents API key was rejected: {reason}")

    return body


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _cached_validation_is_fresh(cfg: dict[str, Any], key: str) -> bool:
    if cfg.get("api_key") != key:
        return False
    last = cfg.get("last_validated_at")
    ttl = cfg.get("validation_ttl", VALIDATION_TTL_SECONDS)
    if not isinstance(last, (int, float)):
        return False
    return (time.time() - float(last)) < float(ttl)


def _fail(message: str) -> "None":
    print(f"\n[Photo Agents] {message}", file=sys.stderr)
    print(f"[Photo Agents] Get or manage your key at {SIGNUP_URL}", file=sys.stderr)
    sys.exit(1)


def ensure_authenticated() -> str:
    """Block until a valid Photo Agents API key is available.

    Returns the key on success. Calls ``sys.exit(1)`` on failure.
    """
    api_key = load_api_key()
    if not api_key:
        _fail("API key required to start the agent.")

    cfg = _read_config()

    # Fast path: cached validation still fresh.
    if _cached_validation_is_fresh(cfg, api_key):
        return api_key

    # Slow path: revalidate against the license server.
    try:
        body = validate_api_key(api_key)
    except LicenseError as exc:
        # Network errors are tolerated only if we previously validated this exact
        # key — otherwise the user is brand new and we cannot let them through.
        if "Could not reach" in str(exc) and cfg.get("api_key") == api_key and cfg.get("last_validated_at"):
            print(f"[Photo Agents] Warning: {exc}. Using cached validation.", file=sys.stderr)
            return api_key
        _fail(str(exc))

    cfg["api_key"] = api_key
    cfg["last_validated_at"] = int(time.time())
    cfg["validation_ttl"] = VALIDATION_TTL_SECONDS
    if "tier" in body:
        cfg["tier"] = body["tier"]
    if "expires_at" in body:
        cfg["expires_at"] = body["expires_at"]
    _write_config(cfg)
    return api_key
