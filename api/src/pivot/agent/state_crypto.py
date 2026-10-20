"""Encryption seam for checkpoint state (04-C task 2.3, placeholder).

Per 04-A sections 4.2 and 8: sensitive checkpoint state is whitelist
normalized first, then encrypted before storage, and production use
requires an approved OpenBao key policy. That policy is still TBD-P0,
so the only scheme registered here is ``none``: an envelope that carries
the sanitized state unchanged. The envelope shape is the contract that
real encryption will later fill in without changing callers.

Fail closed: decrypting an envelope with an unknown or missing scheme
raises instead of passing data through, so a payload written by a real
cipher is never silently treated as plaintext by this placeholder.
"""

from __future__ import annotations

from typing import Any

SCHEME_NONE = "none"


class StateCryptoError(Exception):
    """Raised when a checkpoint state envelope cannot be handled."""


class StateCipher:
    """Encrypt and decrypt sanitized checkpoint state.

    Placeholder implementation: registers only the ``none`` scheme
    until the OpenBao key policy is approved (TBD-P0).
    """

    def encrypt(self, state: dict[str, Any]) -> dict[str, Any]:
        """Wrap sanitized state in an envelope. No encryption yet."""
        return {"encryption": SCHEME_NONE, "state": dict(state)}

    def decrypt(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Return the state from an envelope, failing closed on surprises."""
        if not isinstance(envelope, dict) or "state" not in envelope:
            raise StateCryptoError("Malformed checkpoint state envelope")
        scheme = envelope.get("encryption")
        if scheme != SCHEME_NONE:
            raise StateCryptoError(
                f"Unsupported checkpoint state encryption scheme: {scheme!r}"
            )
        return dict(envelope["state"])
