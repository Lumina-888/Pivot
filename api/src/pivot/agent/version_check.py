"""Version compatibility checks for checkpoint recovery.

Per 04-A section 4.2 and AGENT_SPEC section 8: a Run's graph, state
schema, prompt, tools, model, dependency lock and budget policy versions
are fixed when the Run is created. Recovery must verify the current
environment matches the locked versions and fail closed on any mismatch
or missing version: never silently swap graph, tools or model, and never
fall back to a different execution path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pivot.db.models import RunExecution

#: RunExecution fields that form the recovery version lock, in the order
#: they are reported in mismatch results.
VERSION_FIELDS: tuple[str, ...] = (
    "graph_version",
    "state_schema_version",
    "prompt_version",
    "tools_version",
    "model_version",
    "dependencies_lock_version",
    "budget_policy_version",
)


@dataclass(frozen=True)
class VersionMismatch:
    """One locked version field that does not match the environment."""

    field: str
    locked: str
    current: str | None


@dataclass(frozen=True)
class VersionCheckResult:
    """Outcome of comparing a RunExecution lock against the environment."""

    mismatches: tuple[VersionMismatch, ...] = ()

    @property
    def compatible(self) -> bool:
        return not self.mismatches


class VersionChecker:
    """Compares a RunExecution version lock with current versions."""

    def verify_compatibility(
        self,
        execution: RunExecution,
        current_versions: Mapping[str, str],
    ) -> VersionCheckResult:
        """Return every field whose current version differs from the lock.

        A field missing from ``current_versions`` counts as a mismatch:
        an environment that cannot state its version is not compatible
        (fail closed).
        """
        mismatches = []
        for field in VERSION_FIELDS:
            locked = getattr(execution, field)
            current = current_versions.get(field)
            if current is None or current != locked:
                mismatches.append(
                    VersionMismatch(field=field, locked=locked, current=current)
                )
        return VersionCheckResult(mismatches=tuple(mismatches))

    def locked_versions(self, execution: RunExecution) -> dict[str, str]:
        """Return the RunExecution lock as a plain field-to-version dict."""
        return {field: getattr(execution, field) for field in VERSION_FIELDS}
