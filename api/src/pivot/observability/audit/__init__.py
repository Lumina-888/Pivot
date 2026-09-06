"""M01/M05-facing audit sink. Callers emit drafts; M06 persists and redacts."""

from pivot.observability.audit.sink import AuditLogSink

__all__ = ["AuditLogSink"]
