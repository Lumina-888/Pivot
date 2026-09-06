"""Short-lived access tokens with token_version (FR-AUTH-003).

JWT numeric lifetimes remain TBD-P0; callers inject ttl rather than freezing it.
The encoder is HMAC-SHA256 over a compact payload so unit tests need no PyJWT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pivot.auth.errors import invalid_credentials
from pivot.auth.ports import Clock, Principal, UserAccount


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@dataclass(frozen=True)
class AccessToken:
    raw: str
    principal: Principal
    expires_at: datetime


class TokenService:
    def __init__(self, secret: str, access_ttl: int, clock: Clock) -> None:
        if not secret:
            raise ValueError("token secret required")
        self._secret = secret.encode("utf-8")
        self._access_ttl = access_ttl
        self._clock = clock

    @property
    def access_ttl(self) -> int:
        return self._access_ttl

    def issue(self, user: UserAccount) -> AccessToken:
        now = self._clock.now()
        expires_at = now + timedelta(seconds=self._access_ttl)
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "tv": user.token_version,
            "jti": secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        raw = self._encode(payload)
        return AccessToken(
            raw=raw,
            principal=Principal(
                user_id=user.id,
                username=user.username,
                role=user.role,
                token_version=user.token_version,
                status=user.status,
            ),
            expires_at=expires_at,
        )

    def parse(self, token: str, request_id: str) -> Principal:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            expected = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64url(signature_b64)):
                raise ValueError("bad signature")
            payload: dict[str, Any] = json.loads(_unb64url(payload_b64))
            if int(payload["exp"]) <= int(self._clock.now().timestamp()):
                raise ValueError("expired")
        except (ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
            raise invalid_credentials(request_id) from exc
        return Principal(
            user_id=str(payload["sub"]),
            username=str(payload["username"]),
            role=str(payload["role"]),
            token_version=int(payload["tv"]),
        )

    def _encode(self, payload: dict[str, Any]) -> str:
        header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header}.{body}".encode("ascii")
        signature = _b64url(hmac.new(self._secret, signing_input, hashlib.sha256).digest())
        return f"{header}.{body}.{signature}"


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
