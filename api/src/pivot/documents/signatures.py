"""Extension, declared MIME and magic-byte consistency (FR-DOC-001/002)."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

ALLOWED_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

REJECTED_LEGACY = {".doc", ".ppt", ".xls"}
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

OOXML_MARKERS = {
    ".docx": "word/",
    ".pptx": "ppt/",
    ".xlsx": "xl/",
}

_UNSAFE_FILENAME = re.compile(r"[^\w\u4e00-\u9fff.-]+", re.UNICODE)
KIND_MEDIA_TYPE = {
    "pdf": ALLOWED_MIME[".pdf"],
    "docx": ALLOWED_MIME[".docx"],
    "pptx": ALLOWED_MIME[".pptx"],
    "xlsx": ALLOWED_MIME[".xlsx"],
}


def normalize_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    if not name or name in {".", ".."} or ".." in filename:
        raise ValueError("unsafe filename")
    return name


def download_filename(title: str, extension: str) -> str:
    """Strip path segments and injection characters (SPEC §8.2, NFR-SEC-015)."""
    base = str(title or "document").replace("\\", "/").split("/")[-1]
    base = base.replace("..", "")
    cleaned = _UNSAFE_FILENAME.sub("_", base).strip("._") or "document"
    cleaned = cleaned[:120]
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    if ext not in ALLOWED_MIME:
        ext = ".bin"
    if not cleaned.lower().endswith(ext):
        cleaned = f"{cleaned}{ext}"
    return cleaned


def extension_of(filename: str) -> str:
    lower = normalize_filename(filename).lower()
    dot = lower.rfind(".")
    if dot < 0:
        return ""
    return lower[dot:]


def sniff_kind(content: bytes) -> str:
    if content.startswith(PDF_MAGIC):
        return "pdf"
    if content.startswith(OLE_MAGIC):
        return "ole"
    if content.startswith(ZIP_MAGIC):
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile:
            return "zip-corrupt"
        joined = " ".join(names)
        if "word/" in joined:
            return "docx"
        if "ppt/" in joined:
            return "pptx"
        if "xl/" in joined:
            return "xlsx"
        return "zip"
    return "unknown"


def validate_upload(filename: str, declared_mime: str, content: bytes) -> str:
    """Return canonical extension or raise ValueError with contract code name."""
    ext = extension_of(filename)
    if ext in REJECTED_LEGACY or ext not in ALLOWED_MIME:
        raise ValueError("UNSUPPORTED_EXTENSION")
    expected_mime = ALLOWED_MIME[ext]
    if declared_mime and declared_mime != expected_mime:
        raise ValueError("INVALID_FILE_SIGNATURE")
    kind = sniff_kind(content)
    expected_kind = ext.lstrip(".")
    if kind != expected_kind:
        raise ValueError("INVALID_FILE_SIGNATURE")
    return ext
