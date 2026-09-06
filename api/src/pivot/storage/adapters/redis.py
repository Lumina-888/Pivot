"""Redis adapter port marker.

Redis is intentionally exposed only through queue/cache protocols. It is not a
source of business facts and no Redis SDK is required by this module.
"""

from pivot.storage.protocols import CacheStore, QueueStore

__all__ = ["CacheStore", "QueueStore"]
