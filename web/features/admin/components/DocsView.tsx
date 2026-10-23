"use client";

import { type FormEvent, useEffect, useState } from "react";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Modal } from "../../../components/ui/Modal";
import { Table } from "../../../components/ui/Table";
import {
  deleteDocument,
  documentStateLabel,
  listAdminDocuments,
  retryDocument,
  uploadDocument,
} from "../documents";
import { errorMessage, isAdminForbidden } from "../rbac";
import type { DocumentSummary, PageStatus } from "../types";
import { ForbiddenView } from "./ForbiddenView";
import { StatusBanner } from "./StatusBanner";

function toneForState(state: string): "green" | "yellow" | "red" | "gray" | "blue" {
  if (state === "ready") {
    return "green";
  }
  if (state.includes("fail")) {
    return "red";
  }
  if (state.includes("queued") || state.includes("parsing") || state.includes("embed")) {
    return "yellow";
  }
  if (state.includes("delete")) {
    return "gray";
  }
  return "blue";
}

export function DocsView() {
  const [status, setStatus] = useState<PageStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [pendingDelete, setPendingDelete] = useState<DocumentSummary | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadSpace, setUploadSpace] = useState("");
  const [allowExternal, setAllowExternal] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function reload() {
    const list = await listAdminDocuments();
    setDocuments(list.items);
    setStatus(list.items.length ? "ready" : "empty");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reload();
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (isAdminForbidden(caught)) {
          setStatus("forbidden");
          return;
        }
        setError(errorMessage(caught, "无法加载文档"));
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "forbidden") {
    return <ForbiddenView />;
  }

  async function onRetry(doc: DocumentSummary) {
    setFeedback(null);
    try {
      const result = await retryDocument(doc.document_id);
      setFeedback(result.accepted ? `已受理重试：${doc.title}` : "重试未被受理");
      await reload();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "重试失败"));
    }
  }

  function onPickFile(file: File | null) {
    setUploadFile(file);
    if (file && !uploadTitle.trim()) {
      setUploadTitle(file.name.replace(/\.[^.]+$/, ""));
    }
  }

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile || uploading) {
      return;
    }
    setFeedback(null);
    setUploading(true);
    try {
      const created = await uploadDocument(uploadFile, {
        title: uploadTitle,
        space: uploadSpace,
        externalLlmAllowed: allowExternal,
      });
      setFeedback(`已上传，正在入库：${uploadTitle.trim() || uploadFile.name}（状态 ${created.state}）`);
      setUploadOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadSpace("");
      setAllowExternal(false);
      await reload();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "上传失败"));
    } finally {
      setUploading(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    setFeedback(null);
    try {
      const result = await deleteDocument(pendingDelete.document_id);
      setFeedback(result.accepted ? `已受理删除：${pendingDelete.title}` : "删除未被受理");
      setPendingDelete(null);
      await reload();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "删除失败"));
    }
  }

  return (
    <div className="admin-page">
      <h1>文档管理</h1>
      <div className="admin-toolbar">
        <Button onClick={() => setUploadOpen(true)}>上传文档</Button>
      </div>
      {status === "loading" ? <StatusBanner tone="loading">正在加载文档…</StatusBanner> : null}
      {status === "error" ? <StatusBanner tone="error">{error ?? "无法加载文档"}</StatusBanner> : null}
      {status === "empty" ? <StatusBanner tone="empty">暂无文档</StatusBanner> : null}
      {feedback ? <StatusBanner tone="loading">{feedback}</StatusBanner> : null}
      {documents.length ? (
        <Table caption="文档状态" headers={["标题", "空间", "状态", "操作"]}>
          {documents.map((doc) => {
            const state = documentStateLabel(doc);
            const failed = state.includes("fail");
            return (
              <tr key={doc.document_id}>
                <td>{doc.title}</td>
                <td>{doc.space ?? "—"}</td>
                <td>
                  <Badge tone={toneForState(state)}>{state}</Badge>
                </td>
                <td>
                  <Button variant="ghost" disabled={!failed} onClick={() => void onRetry(doc)}>
                    重试
                  </Button>{" "}
                  <Button variant="danger" onClick={() => setPendingDelete(doc)}>
                    删除
                  </Button>
                </td>
              </tr>
            );
          })}
        </Table>
      ) : null}
      <Modal open={uploadOpen} title="上传文档" onClose={() => setUploadOpen(false)}>
        <form className="admin-create" onSubmit={onUpload}>
          <label htmlFor="upload-file">文件</label>
          <input
            id="upload-file"
            type="file"
            accept=".pdf,.docx,.pptx,.xlsx"
            onChange={(event) => onPickFile(event.target.files?.[0] ?? null)}
            required
          />
          <label htmlFor="upload-title">标题</label>
          <input
            id="upload-title"
            value={uploadTitle}
            onChange={(event) => setUploadTitle(event.target.value)}
          />
          <label htmlFor="upload-space">空间</label>
          <input
            id="upload-space"
            value={uploadSpace}
            placeholder="shared"
            onChange={(event) => setUploadSpace(event.target.value)}
          />
          <label htmlFor="upload-external">
            <input
              id="upload-external"
              type="checkbox"
              checked={allowExternal}
              onChange={(event) => setAllowExternal(event.target.checked)}
            />{" "}
            允许外部模型使用本文档内容
          </label>
          <p className="muted">支持 .pdf、.docx、.pptx、.xlsx。上传后自动解析入库，状态可在列表中查看。</p>
          <Button type="submit" disabled={uploading || !uploadFile}>
            {uploading ? "上传中…" : "上传"}
          </Button>
        </form>
      </Modal>
      <Modal open={Boolean(pendingDelete)} title="确认删除" onClose={() => setPendingDelete(null)}>
        <p>删除将立即从列表和检索下线，并异步清理存储。此操作不可恢复文档内容，但审计会保留。</p>
        <div className="admin-toolbar">
          <Button variant="danger" onClick={() => void confirmDelete()}>
            确认删除
          </Button>
          <Button variant="ghost" onClick={() => setPendingDelete(null)}>
            取消
          </Button>
        </div>
      </Modal>
    </div>
  );
}
