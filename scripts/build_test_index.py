"""Build/load a synthetic LlamaIndex demo without network or provider keys.

Run from the repository: python -m scripts.build_test_index --query '迟到三次怎么处理？'
The lexical demo embedding is a controlled fixture, not a semantic model.
Applications can inject PivotEmbedding(HttpQueryEmbedder(...)) into build/load.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import TextNode
from pivot.retrieval.llama_embeddings import PivotEmbedding
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
from pivot.retrieval.policy import RetrievalPolicy

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "tests/fixtures/documents"
INDEX = ROOT / "tests/fixtures/index"
DEMO_MODEL = "lexical-demo-v1"
DEMO_TERMS = (
    "迟到", "早退", "旷工", "请假", "病假", "事假", "加班", "调休", "补卡", "出差",
    "工资", "绩效", "津贴", "报销", "差旅", "票据", "账户", "体检", "年假", "培训",
    "福利", "申请", "主管", "工作日", "审批", "支付", "复核", "十日", "医院证明",
)


class DemoTokenizer:
    """Small explicit vocabulary for synthetic acceptance questions only."""

    def tokenize(self, text: str) -> tuple[str, ...]:
        return tuple(term for term in DEMO_TERMS if term in text)


class DemoEmbedder:
    """Local keyword vectors; unknown terms have an orthogonal nonzero vector."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [float(text.count(term)) for term in DEMO_TERMS]
            vector.append(0.0 if any(vector) else 1.0)
            vectors.append(vector)
        return vectors


def demo_embedding() -> PivotEmbedding:
    return PivotEmbedding(DemoEmbedder(), model_name=DEMO_MODEL, dimension=len(DEMO_TERMS) + 1)


def build_test_index(
    documents_dir: Path = DOCUMENTS,
    persist_dir: Path = INDEX,
    *,
    embed_model: BaseEmbedding | None = None,
) -> VectorStoreIndex:
    """Build deterministic paragraph nodes with real text locators and provenance."""
    embed_model = embed_model if embed_model is not None else demo_embedding()
    files = sorted(documents_dir.glob("*.txt"))
    if not files:
        raise ValueError("no synthetic .txt documents found")
    nodes = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        version_id = f"{path.stem}-{digest[:16]}"
        for position, paragraph in enumerate(re.split(r"\n\s*\n", text.strip())[1:], 1):
            locator, separator, body = paragraph.partition("\n")
            if not separator or not body.strip():
                raise ValueError("fixture paragraphs require a heading and body")
            metadata = {
                "document_id": path.stem, "version_id": version_id, "locator": locator,
                "ready": True, "current": True, "allowed": True, "expired": False,
                "deleted": False, "external_llm_allowed": True,
                "index_generation": f"demo-{digest[:16]}",
                "embedding_model_version": embed_model.model_name,
                "retrieval_config_version": "demo-hybrid-v1",
            }
            nodes.append(TextNode(
                id_=f"{version_id}-paragraph-{position}", text=body.strip(), extra_info=metadata,
                excluded_embed_metadata_keys=list(metadata),
                excluded_llm_metadata_keys=list(metadata),
            ))
    if not nodes:
        raise ValueError("no fixture paragraphs found")
    index = VectorStoreIndex(nodes, embed_model=embed_model, store_nodes_override=True)
    persist_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(persist_dir))
    (persist_dir / "pivot-index.json").write_text(json.dumps({
        "embedding_model_version": embed_model.model_name,
        "retrieval_config_version": "demo-hybrid-v1",
        "document_count": len(files), "chunk_count": len(nodes),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def load_test_index(
    persist_dir: Path = INDEX, *, embed_model: BaseEmbedding | None = None,
) -> VectorStoreIndex:
    embed_model = embed_model if embed_model is not None else demo_embedding()
    manifest = json.loads((persist_dir / "pivot-index.json").read_text(encoding="utf-8"))
    if manifest["embedding_model_version"] != embed_model.model_name:
        raise ValueError("embedding model changed; rebuild the index with a new generation")
    index = load_index_from_storage(
        StorageContext.from_defaults(persist_dir=str(persist_dir)), embed_model=embed_model,
    )
    if not isinstance(index, VectorStoreIndex):
        raise ValueError("expected vector index")
    return index


def create_demo_retriever(index: VectorStoreIndex) -> LlamaIndexRetriever:
    """Demo-only policy and trusted fixture authorization, no production defaults."""
    fixture_documents = {"sample_attendance", "sample_salary", "sample_benefits"}
    return LlamaIndexRetriever(
        index, policy=RetrievalPolicy(dense_k=5, bm25_k=5, rrf_k=60, evidence_limit=5),
        tokenizer=DemoTokenizer(), bm25_k1=1.2, bm25_b=0.75, dense_score_cutoff=0.05,
        authorize=lambda principal, document, version: (
            principal == "demo-user" and document in fixture_documents
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=Path, default=DOCUMENTS)
    parser.add_argument("--output", type=Path, default=INDEX)
    parser.add_argument("--query", default="迟到三次怎么处理？")
    parser.add_argument("--document-id")
    args = parser.parse_args()
    build_test_index(args.documents, args.output)
    result = create_demo_retriever(load_test_index(args.output)).retrieve(
        args.query, scope_type="document" if args.document_id else "global",
        scope_document_id=args.document_id, principal_id="demo-user",
    )
    print(f"fixture embedding={DEMO_MODEL}; status={result.status}; hits={len(result.evidence)}")
    for hit in result.evidence:
        print(f"{hit.document_id} / {hit.locator}: {hit.text}")


if __name__ == "__main__":
    main()
