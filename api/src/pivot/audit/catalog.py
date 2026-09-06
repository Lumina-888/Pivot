"""Canonical audit actions required by FR-AUDIT-001 / SPEC §8.4."""

from __future__ import annotations

# SPEC §4.8 FR-AUDIT-001 / §8.4: at least these 15 categories.
REQUIRED_ACTIONS: tuple[str, ...] = (
    "auth.login",
    "auth.login_failed",
    "auth.logout",
    "auth.role_change",
    "auth.disable_user",
    "document.upload",
    "document.update",
    "document.delete",
    "document.retry",
    "qa.run",
    "export.create",
    "admin.debug_access",
    "authz.permission_change",
    "ops.backup_restore",
    "ops.config_change",
)

# Additional export lifecycle actions (FR-EXPORT-003).
EXPORT_LIFECYCLE_ACTIONS: tuple[str, ...] = (
    "export.create",
    "export.download",
    "export.failed",
    "export.expired",
)

# Accept sibling-module names without inventing a second vocabulary.
_ALIASES: dict[str, str] = {
    "login": "auth.login",
    "login_failed": "auth.login_failed",
    "logout": "auth.logout",
    "role_change": "auth.role_change",
    "disable_user": "auth.disable_user",
    "auth.enable_user": "auth.enable_user",
    "upload": "document.upload",
    "update": "document.update",
    "delete": "document.delete",
    "retry": "document.retry",
    "qa": "qa.run",
    "export": "export.create",
    "admin_debug": "admin.debug_access",
    "permission_change": "authz.permission_change",
    "backup_restore": "ops.backup_restore",
    "config_change": "ops.config_change",
}


def canonicalize(action: str) -> str:
    if not action or not isinstance(action, str):
        return "unknown"
    return _ALIASES.get(action, action)


def required_action_set() -> frozenset[str]:
    return frozenset(REQUIRED_ACTIONS)
