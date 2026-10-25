"""S2: search-route authorize defers on row-less hits (ADR-018 D3).

The search route's live recheck is document-level, unlike the QA
hook: it enforces library, folder and exception channels for hits
whose document row exists in this assembly, but defers (passes) when
the row is missing. Search legitimately serves payloads whose rows
live in another store (worker ingest publishes vectors while the
HTTP assembly holds no rows) or nowhere (raw vector upserts), and a
row-less document cannot have been moved into a folder, because
moves go through the service, which requires a row. The payload
scope (library + exception, via passes_filters) remains the
enforcement for those hits. Version currency is deliberately not
checked here: search hits are document-level, and the QA hook keeps
the strict version check for version-pinned evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pivot.documents.ports import DocumentRecord
from pivot.http.bootstrap import _llama_backend
from pivot.http.settings import RuntimeSettings
from pivot.retrieval.fakes import HashingQueryEmbedder


class _Client:
    """Minimal in-memory Qdrant client double for index-set open."""

    def __init__(self) -> None:
        self.collections: set[str] = set()

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)

    def upsert(self, collection_name: str, points) -> None:
        return None

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        return []

    def delete(self, collection_name, points_selector=None) -> None:
        return None

    def scroll(self, collection_name, *, limit, offset=None):
        return [], None


class _Store:
    """Native vector store double with no payloads."""

    def scroll(self, *, limit, offset=None):
        return [], None


class _Rows:
    def __init__(self, documents) -> None:
        self._documents = documents

    def get(self, document_id: str):
        return self._documents.get(document_id)

    def list_for_document(self, document_id: str):
        return []


def _search_authorize(documents, *, libraries, folders, exceptions):
    _, _, _, _, search_authorize = _llama_backend(
        RuntimeSettings(
            storage="memory",
            token_secret="test-secret",
            access_ttl=60,
            refresh_ttl=3600,
            export_ttl=3600,
            download_ttl=300,
            export_public_base="https://files.pivot.test",
            retrieval_k=4,
            qdrant_collection="pivot-chunks",
            qdrant_vector_size=4,
            qdrant_distance="Cosine",
            bm25_k1=1.2,
            bm25_b=0.75,
            llama_qdrant_client=_Client(),
        ),
        qdrant_store=_Store(),
        query_embedder=HashingQueryEmbedder(dimension=4),
        document_rows=_Rows(documents),
        version_rows=_Rows({}),
        visible_libraries_for=lambda principal_id: libraries,
        visible_folders_for=lambda principal_id: folders,
        exception_documents_for=lambda principal_id: exceptions,
    )
    return search_authorize


def _doc(document_id, *, library_id, folder_id=None, deleted=False):
    return DocumentRecord(
        id=document_id,
        title="t",
        space="hr",
        created_by="usr_admin",
        library_id=library_id,
        folder_id=folder_id,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


def test_FR_RBAC_004_search_authorize_defers_when_no_document_row() -> None:
    authorize = _search_authorize(
        {}, libraries=set(), folders=set(), exceptions=set()
    )
    # No row at all: the payload scope decided already, so defer.
    assert authorize("usr_bob", "doc_unknown", "ver_unknown") is True


def test_FR_RBAC_004_search_authorize_denies_deleted_document() -> None:
    authorize = _search_authorize(
        {"doc_del": _doc("doc_del", library_id="pub", deleted=True)},
        libraries={"pub"},
        folders=set(),
        exceptions=set(),
    )
    assert authorize("usr_bob", "doc_del", "ver_del") is False


def test_FR_RBAC_004_search_authorize_allows_visible_default_folder() -> None:
    authorize = _search_authorize(
        {"doc_pub": _doc("doc_pub", library_id="pub")},
        libraries={"pub"},
        folders=set(),
        exceptions=set(),
    )
    assert authorize("usr_bob", "doc_pub", "ver_pub") is True


def test_FR_RBAC_004_search_authorize_denies_invisible_folder() -> None:
    authorize = _search_authorize(
        {"doc_fld": _doc("doc_fld", library_id="dept_eng", folder_id="fld_a")},
        libraries={"dept_eng"},
        folders={"fld_b"},
        exceptions=set(),
    )
    assert authorize("usr_bob", "doc_fld", "ver_fld") is False


def test_FR_RBAC_004_search_authorize_exception_overrides_invisible_folder() -> None:
    authorize = _search_authorize(
        {"doc_fld": _doc("doc_fld", library_id="dept_eng", folder_id="fld_a")},
        libraries={"dept_eng"},
        folders={"fld_b"},
        exceptions={"doc_fld"},
    )
    assert authorize("usr_bob", "doc_fld", "ver_fld") is True


def test_FR_RBAC_004_search_authorize_allows_dept_admin_all_folders() -> None:
    authorize = _search_authorize(
        {"doc_fld": _doc("doc_fld", library_id="dept_eng", folder_id="fld_a")},
        libraries={"dept_eng"},
        folders={"fld_a", "fld_b"},
        exceptions=set(),
    )
    assert authorize("usr_alice", "doc_fld", "ver_fld") is True


def test_FR_RBAC_004_search_authorize_ignores_version_currency() -> None:
    authorize = _search_authorize(
        {"doc_pub": _doc("doc_pub", library_id="pub")},
        libraries={"pub"},
        folders=set(),
        exceptions=set(),
    )
    # A bogus version id does not deny a document-level search hit;
    # version currency is the QA hook's job, not the search route's.
    assert authorize("usr_bob", "doc_pub", "ver_bogus") is True
