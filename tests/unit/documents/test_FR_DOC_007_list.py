from __future__ import annotations

from fakes import pdf_bytes


def _upload(service, *, title: str, space: str = "shared"):
    return service.upload(
        filename=f"{title}.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + title.encode("ascii"),
        title=title,
        actor_id="usr_admin",
        request_id="req_up",
        space=space,
    )


def test_FR_DOC_007_list_library_excludes_tombstone(service):
    kept = _upload(service, title="kept")
    removed = _upload(service, title="removed")
    service.request_delete(removed.document_id, "req_del", "usr_admin")
    items = service.list_library(viewer_role="admin")
    ids = {item["document_id"] for item in items}
    assert kept.document_id in ids
    assert removed.document_id not in ids


def test_FR_DOC_001_list_library_uploaded_has_null_current_version(service):
    version = _upload(service, title="draft")
    items = service.list_library(viewer_role="admin")
    assert len(items) == 1
    assert items[0]["document_id"] == version.document_id
    assert items[0]["title"] == "draft"
    assert items[0]["current_version"] is None
    assert items[0]["created_at"]
    assert "storage_key" not in items[0]


def test_FR_RBAC_004_list_library_user_sees_only_shared(service):
    shared = _upload(service, title="shared-doc", space="shared")
    _upload(service, title="internal-doc", space="internal")
    user_ids = {item["document_id"] for item in service.list_library(viewer_role="user")}
    admin_ids = {item["document_id"] for item in service.list_library(viewer_role="admin")}
    assert user_ids == {shared.document_id}
    assert len(admin_ids) == 2
