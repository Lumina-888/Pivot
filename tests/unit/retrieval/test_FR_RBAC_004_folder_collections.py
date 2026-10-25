"""S1: folder collection naming for FR-RBAC-004 (ADR-018 D3).

Naming only: the default folder keeps the library collection, and a
restricted folder gets {native}__llama__{library_id}__{folder_id}.
Retrieval wiring to folder collections is S2.
"""

import pytest


def test_FR_RBAC_004_folder_collection_name() -> None:
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_qdrant_index import (
        llama_collection_name,
        llama_folder_collection_name,
    )

    assert (
        llama_folder_collection_name("pivot-chunks", "dept_eng", "fold_1")
        == "pivot-chunks__llama__dept_eng__fold_1"
    )
    # The default folder keeps the library collection, unchanged.
    assert (
        llama_collection_name("pivot-chunks", "dept_eng")
        == "pivot-chunks__llama__dept_eng"
    )


def test_FR_RBAC_004_folder_collection_name_rejects_blanks() -> None:
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_qdrant_index import (
        llama_folder_collection_name,
    )

    with pytest.raises(ValueError):
        llama_folder_collection_name("pivot-chunks", "", "fold_1")
    with pytest.raises(ValueError):
        llama_folder_collection_name("pivot-chunks", "dept_eng", "  ")
