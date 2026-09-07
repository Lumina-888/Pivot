"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Page } from "../../../components/layouts/Page";
import { Badge } from "../../../components/ui/Badge";
import { ApiError } from "../../../lib/api/client";
import { getLibraryDocument } from "../library";
import { documentChatHref } from "../routes";
import type { DocumentDetail } from "../types";
import { StatusBanner } from "./StatusBanner";

export function DocumentView({ documentId }: { documentId: string }) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const detail = await getLibraryDocument(documentId);
        if (!cancelled) {
          setDocument(detail);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.envelope.message : "无法加载文档");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  return (
    <Page>
      <p className="muted">
        <Link href="/library">知识库</Link> › 文档详情
      </p>
      {loading ? <StatusBanner tone="loading">正在加载文档…</StatusBanner> : null}
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {document ? (
        <>
          <h1>{document.title}</h1>
          <p className="muted">
            {document.space ?? "知识库"} · {document.created_at.slice(0, 10)}
          </p>
          <div className="doc-actions">
            {(document.tags ?? []).map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
          <div className="doc-actions">
            <Link className="btn btn-primary" href={documentChatHref(document.document_id)}>
              仅针对本文提问
            </Link>
          </div>
          <p className="muted">提问将使用结构化 document scope，不会扩大到全局知识库。</p>
        </>
      ) : null}
    </Page>
  );
}
