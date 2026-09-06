from __future__ import annotations

from fakes import pdf_bytes


def test_FR_DOC_008_orphan_scan_is_idempotent(service):
    version = service.upload(
        filename="a.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="a",
        actor_id="usr_admin",
        request_id="req_up",
    )
    first = service.scan_orphans(
        object_keys=(version.storage_key, "orphan/obj"),
        vector_version_ids=(version.id, "ver_ghost"),
    )
    second = service.scan_orphans(
        object_keys=(version.storage_key, "orphan/obj"),
        vector_version_ids=(version.id, "ver_ghost"),
    )
    assert first == second
    assert first["objects"] == ("orphan/obj",)
    assert first["vectors"] == ("ver_ghost",)
