"""S2: folder scope in the shared search filter (ADR-018 D3).

passes_filters is the single scope rule shared by the corpus search
path and the retriever search path. Inside a visible library, a chunk
in a restricted folder passes only when the folder is visible to the
caller or its document carries an exception grant: folders never
replace exceptions. Chunks without a folder fact sit in the default
folder, which is the library itself, so the library check alone
decides them.
"""

from __future__ import annotations

from pivot.retrieval.filters import passes_filters
from pivot.retrieval.models import ChunkRecord, RetrievalQuery


def _chunk(chunk_id, document_id, library_id, folder_id):
    return ChunkRecord(
        chunk_id=chunk_id,
        version_id="ver-1",
        document_id=document_id,
        text="出差申请单。",
        title="制度",
        library_id=library_id,
        folder_id=folder_id,
    )


def _query(visible_folders):
    return RetrievalQuery(
        text="出差",
        principal_id="usr_dave",
        library_ids=("pub", "dept_eng"),
        exception_document_ids=("doc-exc",),
        visible_folder_ids=visible_folders,
    )


def test_FR_RBAC_004_folder_filter_passes_visible_folder_and_default() -> None:
    query = _query(("fld_a",))
    assert passes_filters(
        _chunk("c1", "doc-a", "dept_eng", "fld_a"), query
    ) is True
    assert passes_filters(
        _chunk("c2", "doc-b", "dept_eng", None), query
    ) is True


def test_FR_RBAC_004_folder_filter_blocks_invisible_folder() -> None:
    query = _query(("fld_a",))
    assert passes_filters(
        _chunk("c1", "doc-a", "dept_eng", "fld_b"), query
    ) is False


def test_FR_RBAC_004_folder_filter_exception_survives_invisible_folder() -> None:
    query = _query(("fld_a",))
    assert passes_filters(
        _chunk("c1", "doc-exc", "dept_eng", "fld_b"), query
    ) is True


def test_FR_RBAC_004_folder_filter_no_folder_constraint_is_legacy() -> None:
    query = RetrievalQuery(
        text="出差",
        principal_id="usr_dave",
        library_ids=("pub", "dept_eng"),
        exception_document_ids=(),
        visible_folder_ids=None,
    )
    # Without a folder constraint (legacy callers), the folder fact is
    # ignored and the library check alone decides.
    assert passes_filters(
        _chunk("c1", "doc-a", "dept_eng", "fld_b"), query
    ) is True
