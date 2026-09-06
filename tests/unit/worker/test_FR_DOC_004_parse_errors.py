from __future__ import annotations

from pivot_worker.ingest import IngestRequest
from samples import ooxml_docx, pdf_with_text


def test_FR_DOC_004_encrypted_corrupted_empty_and_scan_codes(worker, sink):
    cases = [
        (b"%PDF-1.4\n/Encrypt 1 0 R\n%%EOF\n", "ENCRYPTED_FILE"),
        (b"not-a-pdf", "CORRUPTED_FILE"),
        (b"%PDF-1.4\nBT ET\n%%EOF\n", "EMPTY_TEXT"),
        (b"%PDF-1.4\n/Subtype /Image\n%%EOF\n", "UNSUPPORTED_SCAN_PDF"),
        (pdf_with_text() + b"\n%%PAGE_FAIL\n", "PARTIAL_PAGE_FAILURE"),
        (ooxml_docx([]), "EMPTY_TEXT"),
    ]
    for content, code in cases:
        kind = "docx" if content[:2] == b"PK" else "pdf"
        result = worker.run(
            IngestRequest(
                version_id="ver_err",
                kind=kind,
                content=content,
                message_id=f"msg_{code}",
            )
        )
        assert result["status"] == "failed"
        assert result["error_code"] == code
        assert result["error_code"] in {item[1] for item in sink.parse_errors}
        assert worker.is_retryable(code) is False
