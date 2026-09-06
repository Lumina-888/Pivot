from __future__ import annotations

from pivot_worker.ingest import IngestRequest
from samples import ooxml_docx, ooxml_pptx, ooxml_xlsx, pdf_with_text


def test_FR_DOC_001_four_whitelist_formats_parse(worker):
    jobs = [
        ("pdf", pdf_with_text()),
        ("docx", ooxml_docx(["Attendance policy"])),
        ("pptx", ooxml_pptx(["Q3 review"])),
        ("xlsx", ooxml_xlsx(["late", "absent"])),
    ]
    for kind, content in jobs:
        result = worker.run(
            IngestRequest(
                version_id=f"ver_{kind}",
                kind=kind,
                content=content,
                message_id=f"msg_{kind}",
            )
        )
        assert result["status"] == "ok"
        assert result["error_code"] is None
        assert result["content"]["locators"]
        assert result["trace"]["stage"] == "index"
