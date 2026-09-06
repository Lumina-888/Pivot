from __future__ import annotations

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.parsing import ParserRegistry
from samples import ooxml_docx, ooxml_pptx, ooxml_xlsx, pdf_with_text


def test_M07_chunk_locator_covers_four_formats():
    registry = ParserRegistry()
    splitter = ChunkSplitter(ChunkingPolicy(max_chars=40, overlap_chars=4))
    samples = {
        "pdf": (pdf_with_text("Policy text for locator"), "page="),
        "docx": (ooxml_docx(["Heading path", "Body"]), "paragraph="),
        "pptx": (ooxml_pptx(["Slide title"]), "slide="),
        "xlsx": (ooxml_xlsx(["A1"]), "sheet="),
    }
    for kind, (content, prefix) in samples.items():
        parsed = registry.parse(kind, content)
        drafts = splitter.split(parsed.blocks)
        assert drafts
        assert all(draft.locator.startswith(prefix) for draft in drafts)
        assert all(
            draft.text_hash and draft.raw_char_end > draft.raw_char_start for draft in drafts
        )
