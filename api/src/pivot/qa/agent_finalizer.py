"""
Agent Finalizer 实现

实现结构化答案生成：
- 整合已授权的证据
- 生成结构化答案（answer + claims）
- 绑定证据引用
"""

from __future__ import annotations

from typing import Any

from pivot.qa.ports import DraftWriter, EvidenceHit, Verifier


class StructuredFinalizer:
    """
    结构化答案生成器

    将已授权的证据整合成结构化答案
    """

    def __init__(
        self,
        draft_writer: DraftWriter,
        verifier: Verifier | None = None,
    ) -> None:
        self.draft_writer = draft_writer
        self.verifier = verifier

    def finalize(
        self,
        question: str,
        evidences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        生成结构化答案

        Args:
            question: 用户问题
            evidences: 已授权的证据列表（来自 EvidenceRegistry）

        Returns:
            结构化答案：
            {
                "answer": str,  # 答案文本
                "claims": [     # 声明列表
                    {
                        "text": str,
                        "evidence_ids": [str, ...]
                    }
                ],
                "status": "completed" | "insufficient_evidence"
            }
        """
        # 检查是否有足够证据
        if not evidences:
            return {
                "answer": "抱歉，未找到相关证据来回答您的问题。",
                "claims": [],
                "status": "insufficient_evidence",
            }

        # 转换为 EvidenceHit 格式
        hits = tuple(
            EvidenceHit(
                chunk_id=ev["chunk_id"],
                document_id=ev["document_id"],
                version_id=ev["version_id"],
                text=ev["text"],
                locator=ev.get("locator", ""),
                external_llm_allowed=ev.get("external_llm_allowed", False),
            )
            for ev in evidences
        )

        # 生成草稿答案
        answer_text, claims, citations = self.draft_writer.draft(question, hits)

        # 如果有 Verifier，验证答案
        if self.verifier:
            verification_result = self.verifier.verify(claims, citations, hits)
            if verification_result != "pass":
                # 验证失败，返回保守答案
                return {
                    "answer": "抱歉，无法生成可靠的答案。",
                    "claims": [],
                    "status": "verification_failed",
                }

        # 构建结构化响应
        # 将 citations 映射到 evidence_ids
        structured_claims = []
        for claim in claims:
            claim_citations = [c for c in citations if c.get("claim_index") == claim.get("index")]
            evidence_ids = [
                evidences[c["evidence_index"]]["evidence_id"]
                for c in claim_citations
                if c.get("evidence_index") is not None and c["evidence_index"] < len(evidences)
            ]

            structured_claims.append(
                {
                    "text": claim.get("text", ""),
                    "evidence_ids": evidence_ids,
                }
            )

        return {
            "answer": answer_text,
            "claims": structured_claims,
            "status": "completed",
        }
