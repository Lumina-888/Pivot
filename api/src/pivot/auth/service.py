"""Authentication and authorization application service (FR-AUTH / FR-RBAC)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from pivot.auth.cookies import Cookie, clear_refresh_cookie, refresh_cookie
from pivot.auth.errors import forbidden, invalid_credentials, not_found
from pivot.auth.ports import (
    AuditEventDraft,
    AuditSink,
    Clock,
    LoginAttemptLimiter,
    PasswordHasher,
    Principal,
    RefreshSession,
    RefreshTokenStore,
    UserAccount,
    UserDirectory,
)
from pivot.auth.tokens import TokenService, hash_refresh_token
from pivot.security.rbac import AccessControl
from pivot.shared.ids import new_id


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token_cookie: bool
    cookie: Cookie
    refresh_token: str

    def to_login_success(self) -> dict[str, str | int | bool]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token_cookie": self.refresh_token_cookie,
        }


@dataclass(frozen=True)
class CreatedUser:
    id: str
    username: str
    role: str
    status: str
    password_hash: str
    initial_password: str


class AuthService:
    def __init__(
        self,
        users: UserDirectory,
        hasher: PasswordHasher,
        tokens: TokenService,
        refresh_tokens: RefreshTokenStore,
        audits: AuditSink,
        attempts: LoginAttemptLimiter,
        access: AccessControl,
        clock: Clock,
        access_ttl: int,
        refresh_ttl: int,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._refresh_tokens = refresh_tokens
        self._audits = audits
        self._attempts = attempts
        self._access = access
        self._clock = clock
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def login(self, username: str, password: str, request_id: str) -> LoginResult:
        if self._attempts.is_blocked(username):
            self._audit("anonymous", "auth.login_failed", username, "blocked", request_id)
            raise invalid_credentials(request_id)
        user = self._users.get_by_username(username)
        if (
            user is None
            or user.status != "active"
            or not self._hasher.verify(password, user.password_hash)
        ):
            self._attempts.record_failure(username)
            self._audit("anonymous", "auth.login_failed", username, "denied", request_id)
            raise invalid_credentials(request_id)
        self._attempts.reset(username)
        result = self._issue_session(user)
        self._audit(user.id, "auth.login", user.id, "ok", request_id)
        return result

    def authenticate(self, access_token: str, request_id: str = "req_auth") -> Principal:
        principal = self._tokens.parse(access_token, request_id)
        user = self._users.get_by_id(principal.user_id)
        if user is None:
            raise invalid_credentials(request_id)
        if user.status != "active":
            raise forbidden(request_id)
        if user.token_version != principal.token_version:
            raise invalid_credentials(request_id)
        return Principal(
            user_id=user.id,
            username=user.username,
            role=user.role,
            token_version=user.token_version,
            status=user.status,
        )

    def refresh(self, refresh_token: str, request_id: str) -> LoginResult:
        session = self._refresh_tokens.get(hash_refresh_token(refresh_token))
        if session is None or session.revoked or session.expires_at <= self._clock.now():
            raise invalid_credentials(request_id)
        user = self._users.get_by_id(session.user_id)
        if (
            user is None
            or user.status != "active"
            or user.token_version != session.token_version
        ):
            raise invalid_credentials(request_id)
        self._refresh_tokens.revoke(session.token_hash)
        result = self._issue_session(user)
        self._audit(user.id, "auth.refresh", user.id, "ok", request_id)
        return result

    def logout(self, refresh_token: str, request_id: str) -> Cookie:
        token_hash = hash_refresh_token(refresh_token)
        session = self._refresh_tokens.get(token_hash)
        self._refresh_tokens.revoke(token_hash)
        actor = session.user_id if session is not None else "anonymous"
        self._audit(actor, "auth.logout", actor, "ok", request_id)
        return clear_refresh_cookie()

    def change_password(
        self,
        access_token: str,
        current_password: str,
        new_password: str,
        request_id: str,
    ) -> None:
        principal = self.authenticate(access_token, request_id)
        user = self._require_user(principal.user_id, request_id)
        if not self._hasher.verify(current_password, user.password_hash):
            raise invalid_credentials(request_id)
        self._rotate_password(user, new_password)
        self._audit(user.id, "auth.change_password", user.id, "ok", request_id)

    def list_users(self, actor_id: str, request_id: str) -> tuple[dict[str, str], ...]:
        self._require_admin_actor(actor_id, request_id)
        return tuple(self.to_admin_user(user) for user in self._users.list())

    def create_user(
        self,
        actor_id: str,
        username: str,
        initial_password: str,
        request_id: str,
    ) -> CreatedUser:
        self._require_admin_actor(actor_id, request_id)
        password_hash = self._hasher.hash(initial_password)
        now = self._clock.now()
        user = UserAccount(
            id=new_id("user"),
            username=username,
            password_hash=password_hash,
            role="user",
            status="active",
            token_version=1,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        self._users.save(user)
        self._audit(
            actor_id,
            "auth.create_user",
            user.id,
            "ok",
            request_id,
            metadata={"username": username},
        )
        return CreatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
            password_hash=user.password_hash,
            initial_password=initial_password,
        )

    def reset_password(
        self,
        actor_id: str,
        user_id: str,
        new_password: str,
        request_id: str,
    ) -> CreatedUser:
        self._require_admin_actor(actor_id, request_id)
        user = self._require_user(user_id, request_id)
        self._rotate_password(user, new_password)
        user.must_change_password = True
        self._users.save(user)
        self._audit(actor_id, "auth.reset_password", user.id, "ok", request_id)
        return CreatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
            password_hash=user.password_hash,
            initial_password=new_password,
        )

    def disable_user(self, actor_id: str, user_id: str, request_id: str) -> UserAccount:
        self._require_admin_actor(actor_id, request_id)
        user = self._require_known_user(user_id, request_id)
        user.status = "disabled"
        user.token_version += 1
        user.updated_at = self._clock.now()
        self._users.save(user)
        self._refresh_tokens.revoke_user(user.id)
        self._audit(actor_id, "auth.disable_user", user.id, "ok", request_id)
        return user

    def enable_user(self, actor_id: str, user_id: str, request_id: str) -> UserAccount:
        self._require_admin_actor(actor_id, request_id)
        user = self._require_known_user(user_id, request_id)
        user.status = "active"
        user.token_version += 1
        user.updated_at = self._clock.now()
        self._users.save(user)
        self._audit(actor_id, "auth.enable_user", user.id, "ok", request_id)
        return user

    def set_user_status(
        self, actor_id: str, user_id: str, status: str, request_id: str
    ) -> UserAccount:
        if status == "disabled":
            return self.disable_user(actor_id, user_id, request_id)
        if status == "active":
            return self.enable_user(actor_id, user_id, request_id)
        raise not_found(request_id)

    def to_admin_user(self, user: UserAccount) -> dict[str, str]:
        stamp = user.created_at or self._clock.now()
        updated = user.updated_at or stamp
        return {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "status": user.status,
            "created_at": self._format_utc(stamp),
            "updated_at": self._format_utc(updated),
        }

    def admin_user(self, user_id: str, request_id: str) -> dict[str, str]:
        return self.to_admin_user(self._require_known_user(user_id, request_id))

    def require_admin(self, principal: Principal, path: str, request_id: str) -> None:
        if not self._access.require_admin(principal):
            self._audit(
                principal.user_id,
                "auth.admin_forbidden",
                path,
                "denied",
                request_id,
            )
            raise forbidden(request_id)

    def authorize_conversation(
        self, principal: Principal, conversation_id: str, request_id: str = "req_authz"
    ) -> None:
        self._access.authorize_conversation(principal, conversation_id, request_id)

    def ensure_conversation_owner(
        self, principal: Principal, conversation_id: str, request_id: str = "req_authz"
    ) -> None:
        self._access.ensure_conversation_owner(principal, conversation_id, request_id)

    def authorize_document(
        self,
        principal: Principal,
        document_id: str,
        request_id: str = "req_authz",
        action: str = "read",
    ) -> None:
        self._access.authorize_document(principal, document_id, request_id, action=action)

    def authorize_chunk(
        self, principal: Principal, chunk_id: str, request_id: str = "req_authz"
    ) -> None:
        self._access.authorize_chunk(principal, chunk_id, request_id)

    def authorize_citation(
        self, principal: Principal, citation_id: str, request_id: str = "req_authz"
    ) -> None:
        self._access.authorize_citation(principal, citation_id, request_id)

    def authorize_export(
        self, principal: Principal, export_id: str, request_id: str = "req_authz"
    ) -> None:
        self._access.authorize_export(principal, export_id, request_id)

    def authorize_resource(
        self,
        principal: Principal,
        kind: str,
        identifier: str,
        request_id: str = "req_authz",
    ) -> None:
        self._access.authorize_resource(principal, kind, identifier, request_id)

    def _issue_session(self, user: UserAccount) -> LoginResult:
        access = self._tokens.issue(user)
        raw_refresh = secrets.token_urlsafe(32)
        self._refresh_tokens.save(
            RefreshSession(
                token_hash=hash_refresh_token(raw_refresh),
                user_id=user.id,
                token_version=user.token_version,
                expires_at=self._clock.now() + timedelta(seconds=self._refresh_ttl),
            )
        )
        return LoginResult(
            access_token=access.raw,
            token_type="Bearer",
            expires_in=self._access_ttl,
            refresh_token_cookie=True,
            cookie=refresh_cookie(raw_refresh, max_age=self._refresh_ttl),
            refresh_token=raw_refresh,
        )

    def _rotate_password(self, user: UserAccount, new_password: str) -> None:
        user.password_hash = self._hasher.hash(new_password)
        user.token_version += 1
        user.must_change_password = False
        user.updated_at = self._clock.now()
        self._users.save(user)
        self._refresh_tokens.revoke_user(user.id)

    def _require_user(self, user_id: str, request_id: str) -> UserAccount:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise invalid_credentials(request_id)
        return user

    def _require_known_user(self, user_id: str, request_id: str) -> UserAccount:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise not_found(request_id)
        return user

    def _format_utc(self, value) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _require_admin_actor(self, actor_id: str, request_id: str) -> UserAccount:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != "admin" or actor.status != "active":
            raise forbidden(request_id)
        return actor

    def _audit(
        self,
        actor: str,
        action: str,
        target: str,
        result: str,
        request_id: str,
        metadata: dict | None = None,
    ) -> None:
        self._audits.emit(
            AuditEventDraft(
                actor=actor,
                action=action,
                target=target,
                result=result,
                request_id=request_id,
                metadata=metadata or {},
            )
        )
