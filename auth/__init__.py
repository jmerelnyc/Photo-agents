"""Photo Agents license / API-key gate.

The agent runtime refuses to start unless the user has a valid Photo Agents
API key. See :mod:`photoagents.auth.license` for the gate.
"""

from photoagents.auth.license import (
    LICENSE_ENDPOINT,
    LicenseError,
    ensure_authenticated,
    load_api_key,
    validate_api_key,
)

__all__ = [
    "LICENSE_ENDPOINT",
    "LicenseError",
    "ensure_authenticated",
    "load_api_key",
    "validate_api_key",
]
