export const USER_NAV = [
  { href: "/", label: "首页" },
  { href: "/library", label: "知识库" },
  { href: "/chat", label: "对话" },
] as const;

export function searchPageHref(query: string): string {
  const q = query.trim();
  return q ? `/search?q=${encodeURIComponent(q)}` : "/search";
}

export function chatHrefFromSearch(query: string): string {
  const q = query.trim();
  return q ? `/chat?q=${encodeURIComponent(q)}` : "/chat";
}

export function documentChatHref(documentId: string, query = ""): string {
  const params = new URLSearchParams({
    scope: "document",
    document_id: documentId,
  });
  const q = query.trim();
  if (q) {
    params.set("q", q);
  }
  return `/chat?${params.toString()}`;
}

export function conversationHref(conversationId: string): string {
  return `/chat/${encodeURIComponent(conversationId)}`;
}

export function libraryDocumentHref(documentId: string): string {
  return `/library/${encodeURIComponent(documentId)}`;
}

export function parseChatSearchParams(searchParams: {
  q?: string | string[];
  scope?: string | string[];
  document_id?: string | string[];
}): { question: string; scopeType: "global" | "document"; scopeDocumentId: string | null } {
  const first = (value?: string | string[]) => (Array.isArray(value) ? value[0] : value) ?? "";
  const scope = first(searchParams.scope);
  const documentId = first(searchParams.document_id);
  if (scope === "document" && documentId) {
    return {
      question: first(searchParams.q),
      scopeType: "document",
      scopeDocumentId: documentId,
    };
  }
  return {
    question: first(searchParams.q),
    scopeType: "global",
    scopeDocumentId: null,
  };
}
