"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Drawer } from "../../../components/ui/Drawer";
import { Modal } from "../../../components/ui/Modal";
import { ApiError } from "../../../lib/api/client";
import { getAccessToken } from "../../../lib/auth/session";
import { connectSse } from "../../../lib/stream/sse";
import {
  applyStreamEvent,
  closeEvidence,
  createEmptyChatState,
  listConversations,
  listMessages,
  openEvidence,
  runEventsUrl,
  startQuestion,
} from "../chat";
import { requestReadyDownload } from "../export";
import { conversationHref, parseChatSearchParams } from "../routes";
import type { ChatViewState, ConversationSummary, ExportFormat, Message } from "../types";
import { StatusBanner } from "./StatusBanner";

export function ChatWorkspace({
  conversationId,
  searchParams,
}: {
  conversationId?: string;
  searchParams?: { q?: string | string[]; scope?: string | string[]; document_id?: string | string[] };
}) {
  const router = useRouter();
  const parsed = useMemo(() => parseChatSearchParams(searchParams ?? {}), [searchParams]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [state, setState] = useState<ChatViewState>(() =>
    createEmptyChatState({
      scope_type: parsed.scopeType,
      scope_document_id: parsed.scopeDocumentId ?? undefined,
    }),
  );
  const [draft, setDraft] = useState(parsed.question);
  const [listError, setListError] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportHref, setExportHref] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadSidebar = useCallback(async () => {
    try {
      const list = await listConversations();
      setConversations(list.items);
      setListError(null);
    } catch (caught) {
      setListError(caught instanceof ApiError ? caught.envelope.message : "无法加载会话");
    }
  }, []);

  useEffect(() => {
    void loadSidebar();
  }, [loadSidebar]);

  useEffect(() => {
    setDraft(parsed.question);
    setState((current) => ({
      ...current,
      question: parsed.question || current.question,
      scopeType: parsed.scopeType,
      scopeDocumentId: parsed.scopeDocumentId,
    }));
  }, [parsed]);

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const list = await listMessages(conversationId);
        if (!cancelled) {
          setMessages(list.items);
          setState((current) => ({ ...current, conversationId }));
        }
      } catch (caught) {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            conversationId,
            status: "failed",
            errorMessage: caught instanceof ApiError ? caught.envelope.message : "无法加载消息",
          }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || state.status === "loading") {
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState((current) => ({
      ...createEmptyChatState({
        scope_type: current.scopeType,
        scope_document_id: current.scopeDocumentId ?? undefined,
      }),
      conversationId: conversationId ?? current.conversationId,
      question,
      status: "loading",
      scopeType: current.scopeType,
      scopeDocumentId: current.scopeDocumentId,
    }));
    try {
      const started = await startQuestion({
        question,
        conversationId: conversationId ?? state.conversationId,
        scopeType: parsed.scopeType,
        scopeDocumentId: parsed.scopeDocumentId,
      });
      setState((current) => ({
        ...current,
        conversationId: started.conversation.conversation_id,
        runId: started.run.run_id,
        messageId: started.run.message_id,
        scopeType: started.scope.scope_type,
        scopeDocumentId: started.scope.scope_document_id ?? null,
      }));
      if (!conversationId) {
        router.replace(conversationHref(started.conversation.conversation_id));
      }
      await connectSse({
        url: runEventsUrl(started.run.run_id),
        token: getAccessToken() ?? undefined,
        signal: controller.signal,
        onEvent: (eventItem) => {
          setState((current) => applyStreamEvent(current, eventItem));
        },
      });
      await loadSidebar();
    } catch (caught) {
      setState((current) => ({
        ...current,
        status: "failed",
        errorMessage: caught instanceof ApiError ? caught.envelope.message : "问答失败",
      }));
    }
  }

  async function onExport(format: ExportFormat) {
    const sourceId = state.conversationId ?? conversationId;
    if (!sourceId) {
      setExportMessage("没有可导出的已完成会话");
      return;
    }
    setExportMessage("正在创建导出…");
    setExportHref(null);
    try {
      const result = await requestReadyDownload({ sourceId, format });
      if (result.status.state === "expired" || !result.downloadUrl) {
        setExportMessage("导出已过期，无法下载");
        return;
      }
      setExportHref(result.downloadUrl);
      setExportMessage("导出已就绪");
    } catch (caught) {
      if (caught instanceof ApiError && caught.envelope.code === "EXPORT_EXPIRED") {
        setExportMessage("导出已过期，无法下载");
        return;
      }
      setExportMessage(caught instanceof ApiError ? caught.envelope.message : "导出失败");
    }
  }

  const canExport = Boolean(state.conversationId ?? conversationId) &&
    (state.status === "answered" || state.status === "uncertain" || state.status === "refused" || messages.length > 0);

  return (
    <div className="chatwrap">
      <aside className="side">
        <Link href="/chat" className="btn btn-primary" style={{ width: "100%", marginBottom: 12 }}>
          新建对话
        </Link>
        {listError ? <StatusBanner tone="error">{listError}</StatusBanner> : null}
        {conversations.length === 0 && !listError ? (
          <StatusBanner tone="empty">暂无会话</StatusBanner>
        ) : null}
        {conversations.map((item) => (
          <Link
            key={item.conversation_id}
            className="sitem"
            data-active={item.conversation_id === (state.conversationId ?? conversationId)}
            href={conversationHref(item.conversation_id)}
          >
            {item.title}
          </Link>
        ))}
      </aside>
      <section className="chat">
        <div className="chead">
          <b>{state.question || "新对话"}</b>
          {state.scopeType === "document" && state.scopeDocumentId ? (
            <span className="chip">单文档 scope · {state.scopeDocumentId}</span>
          ) : (
            <span className="chip">全局知识库</span>
          )}
          <Button variant="ghost" disabled={!canExport} onClick={() => setExportOpen(true)}>
            导出
          </Button>
        </div>
        <div className="msgs">
          {state.status === "loading" ? <StatusBanner tone="loading">正在生成回答…</StatusBanner> : null}
          {state.status === "failed" ? (
            <StatusBanner tone="error">{state.errorMessage ?? "问答失败"}</StatusBanner>
          ) : null}
          {state.status === "uncertain" ? (
            <StatusBanner tone="uncertain">答案存疑，请核对引用证据。</StatusBanner>
          ) : null}
          {state.status === "refused" ? (
            <StatusBanner tone="refused">已拒答：缺少可引用的企业文档依据。</StatusBanner>
          ) : null}
          {messages.map((message) => (
            <div key={message.message_id} className={message.sender === "user" ? "mq" : "ma"}>
              {message.content}
            </div>
          ))}
          {state.question ? <div className="mq">{state.question}</div> : null}
          {state.answer ? (
            <div className="ma">
              <div>{state.answer}</div>
              {state.citations.length > 0 ? (
                <div style={{ marginTop: 10 }}>
                  {state.citations.map((citation, index) => (
                    <button
                      key={citation.citation_id ?? `${citation.document_id}-${index}`}
                      type="button"
                      className="cite"
                      onClick={() => setState((current) => openEvidence(current, citation))}
                    >
                      【{index + 1}】{citation.title ?? citation.locator ?? "证据"}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        <form className="composer" onSubmit={onSend}>
          <textarea
            rows={3}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="输入问题，Enter 发送。文档 scope 不会扩大到全局。"
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
            <Button type="submit" loading={state.status === "loading"}>
              发送
            </Button>
          </div>
        </form>
      </section>
      <Drawer
        open={state.evidenceOpen}
        title="证据"
        onClose={() => setState((current) => closeEvidence(current))}
      >
        {state.selectedCitation ? (
          <>
            <p>
              <b>{state.selectedCitation.title ?? "引用文档"}</b>
            </p>
            <p className="muted">{state.selectedCitation.locator ?? "定位受原文限制"}</p>
            <p>{state.selectedCitation.snippet ?? "无可展示摘录"}</p>
          </>
        ) : (
          <p className="muted">点击引用编号查看对应证据。</p>
        )}
      </Drawer>
      <Modal open={exportOpen} title="导出已完成答案" onClose={() => setExportOpen(false)}>
        <p className="muted">仅导出已持久化的最终答案、Claims 与 Citation，不会重新运行问答。</p>
        <div className="export-choices">
          <Button variant="ghost" onClick={() => void onExport("markdown")}>
            导出 Markdown
          </Button>
          <Button variant="ghost" onClick={() => void onExport("docx")}>
            导出 Word
          </Button>
        </div>
        {exportMessage ? <p className="muted">{exportMessage}</p> : null}
        {exportHref ? (
          <p>
            <a href={exportHref}>下载导出文件</a>
          </p>
        ) : null}
      </Modal>
    </div>
  );
}
