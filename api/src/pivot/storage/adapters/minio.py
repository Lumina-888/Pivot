"""MinIO adapter port marker.

No SDK/client is imported here. Runtime wiring supplies an ObjectStore
implementation, keeping unit tests and domain modules vendor-independent.
"""

from pivot.storage.protocols import ObjectStore

__all__ = ["ObjectStore"]
