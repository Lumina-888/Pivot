"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Page } from "../../../components/layouts/Page";
import { Table } from "../../../components/ui/Table";
import { ApiError } from "../../../lib/api/client";
import { listLibraryDocuments } from "../library";
import { libraryDocumentHref } from "../routes";
import type { DocumentSummary } from "../types";
import { StatusBanner } from "./StatusBanner";

export function LibraryView() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listLibraryDocuments();
        if (!cancelled) {
          setDocuments(list.items);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.envelope.message : "无法加载知识库");
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
  }, []);

  return (
    <Page className="page-sm">
      <h2 className="sec">
        <span className="bar" />
        知识库
      </h2>
      {loading ? <StatusBanner tone="loading">正在加载文档…</StatusBanner> : null}
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {!loading && !error ? (
        <Table
          caption="已授权文档"
          headers={["标题", "空间", "更新"]}
          empty="暂无已授权文档"
        >
          {documents.length
            ? documents.map((doc) => (
                <tr key={doc.document_id}>
                  <td>
                    <Link href={libraryDocumentHref(doc.document_id)}>{doc.title}</Link>
                  </td>
                  <td>{doc.space ?? "—"}</td>
                  <td>{doc.created_at.slice(0, 10)}</td>
                </tr>
              ))
            : undefined}
        </Table>
      ) : null}
    </Page>
  );
}
