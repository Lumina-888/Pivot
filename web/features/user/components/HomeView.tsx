"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { Page } from "../../../components/layouts/Page";
import { ApiError } from "../../../lib/api/client";
import { listLibraryDocuments } from "../library";
import { chatHrefFromSearch, libraryDocumentHref, searchPageHref } from "../routes";
import type { DocumentSummary } from "../types";
import { StatusBanner } from "./StatusBanner";

export function HomeView() {
  const router = useRouter();
  const [mode, setMode] = useState<"search" | "ask">("search");
  const [query, setQuery] = useState("");
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

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = query.trim();
    if (!next) {
      return;
    }
    router.push(mode === "ask" ? chatHrefFromSearch(next) : searchPageHref(next));
  }

  return (
    <Page>
      <section className="hero">
        <div className="ht">
          <h1>问枢 · 企业知识的轴心</h1>
          <p>搜索企业文档，或直接提问——答案均带出处，可追溯。</p>
        </div>
        <form className="searchbox" onSubmit={submit}>
          <button type="button" className="tab" data-on={mode === "search"} onClick={() => setMode("search")}>
            搜文档
          </button>
          <button type="button" className="tab" data-on={mode === "ask"} onClick={() => setMode("ask")}>
            问 AI
          </button>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={mode === "ask" ? "直接向知识库提问…" : "搜索制度、手册、合同…"}
          />
          <button className="btn btn-primary" type="submit">
            {mode === "ask" ? "提问" : "搜索"}
          </button>
        </form>
      </section>

      <h2 className="sec">
        <span className="bar" />
        知识空间
      </h2>
      <div className="spaces">
        {["人事制度", "研发文档", "合同库"].map((space) => (
          <Link key={space} className="space" href="/library">
            <h3>{space}</h3>
            <p>进入知识库浏览已授权文档</p>
          </Link>
        ))}
      </div>

      <div className="row2">
        <div className="card">
          <div className="sec" style={{ marginTop: 0 }}>
            <span className="bar" />
            最近文档
          </div>
          {loading ? <StatusBanner tone="loading">正在加载文档…</StatusBanner> : null}
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          {!loading && !error && documents.length === 0 ? (
            <StatusBanner tone="empty">暂无已授权文档</StatusBanner>
          ) : null}
          <ul className="dlist">
            {documents.slice(0, 6).map((doc) => (
              <li key={doc.document_id}>
                <Link href={libraryDocumentHref(doc.document_id)}>
                  <b>{doc.title}</b>
                  <span className="muted">{doc.space ?? "知识库"}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <div className="sec" style={{ marginTop: 0 }}>
            <span className="bar" />
            快捷入口
          </div>
          <div className="quick">
            <Link href="/chat">新建对话 · 向知识库提问</Link>
            <Link href="/library">浏览知识库</Link>
          </div>
        </div>
      </div>
    </Page>
  );
}
