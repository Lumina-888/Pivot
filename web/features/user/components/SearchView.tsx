"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { Page } from "../../../components/layouts/Page";
import { Button } from "../../../components/ui/Button";
import { ApiError } from "../../../lib/api/client";
import { chatHrefFromSearch, libraryDocumentHref, searchPageHref } from "../routes";
import { searchDocuments } from "../search";
import type { SearchResultItem } from "../types";
import { StatusBanner } from "./StatusBanner";

export function SearchView({ initialQuery }: { initialQuery: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [items, setItems] = useState<SearchResultItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(initialQuery));

  useEffect(() => {
    setQuery(initialQuery);
    if (!initialQuery.trim()) {
      setItems([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const result = await searchDocuments(initialQuery);
        if (!cancelled) {
          setItems(result.items);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.envelope.message : "搜索失败");
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
  }, [initialQuery]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(searchPageHref(query));
  }

  return (
    <Page className="page-sm">
      <h2 className="sec">
        <span className="bar" />
        全局搜索
      </h2>
      <form className="searchbox" onSubmit={submit} style={{ marginBottom: 16, minWidth: "100%" }}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入关键词，回车检索…" />
        <Button type="submit">检索</Button>
        <Link className="btn btn-ghost" href={chatHrefFromSearch(query)}>
          直接问 AI
        </Link>
      </form>
      {initialQuery ? <p className="muted">当前问题：{initialQuery}</p> : null}
      {loading ? <StatusBanner tone="loading">正在检索…</StatusBanner> : null}
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {!loading && !error && initialQuery && items.length === 0 ? (
        <StatusBanner tone="empty">没有匹配的已授权文档</StatusBanner>
      ) : null}
      <ul className="dlist">
        {items.map((item) => (
          <li key={item.document_id}>
            <Link href={libraryDocumentHref(item.document_id)}>
              <b>{item.title}</b>
              <span className="muted">{item.snippet ?? item.space ?? ""}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Page>
  );
}
