import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { StreamEvent } from "../../lib/stream/sse";
import { conversationCreateBody, resolveQuestionScope, runScopeFromConversation } from "./scope";
import type {
  ChatViewState,
  CitationView,
  ConversationList,
  ConversationSummary,
  MessageList,
  ResolvedScope,
  RunCreated,
  ScopeType,
} from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export function createEmptyChatState(scope?: ResolvedScope): ChatViewState {
  return {
    conversationId: null,
    runId: null,
    messageId: null,
    question: "",
    answer: "",
    status: "idle",
    stage: "",
    citations: [],
    evidenceOpen: false,
    selectedCitation: null,
    errorMessage: null,
    scopeType: scope?.scope_type ?? "global",
    scopeDocumentId: scope?.scope_document_id ?? null,
  };
}

export function citationFromPayload(payload: Record<string, unknown>): CitationView {
  const locator =
    typeof payload.locator === "string"
      ? payload.locator
      : typeof payload.page === "number"
        ? `P${payload.page}`
        : undefined;
  return {
    citation_id: typeof payload.citation_id === "string" ? payload.citation_id : undefined,
    document_id: typeof payload.document_id === "string" ? payload.document_id : undefined,
    title: typeof payload.title === "string" ? payload.title : undefined,
    locator,
    snippet: typeof payload.snippet === "string" ? payload.snippet : undefined,
  };
}

export function openEvidence(state: ChatViewState, citation: CitationView): ChatViewState {
  return { ...state, evidenceOpen: true, selectedCitation: citation };
}

export function closeEvidence(state: ChatViewState): ChatViewState {
  return { ...state, evidenceOpen: false, selectedCitation: null };
}

export function applyStreamEvent(state: ChatViewState, event: StreamEvent): ChatViewState {
  const next: ChatViewState = {
    ...state,
    runId: event.data.run_id,
    messageId: event.data.message_id,
    stage: event.data.stage,
  };
  if (event.type === "token") {
    const delta = typeof event.data.payload.text === "string" ? event.data.payload.text : "";
    return { ...next, status: "loading", answer: `${state.answer}${delta}` };
  }
  if (event.type === "citation") {
    return { ...next, citations: [...state.citations, citationFromPayload(event.data.payload)] };
  }
  if (event.type === "completed") {
    return { ...next, status: "answered", evidenceOpen: false };
  }
  if (event.type === "uncertain") {
    return { ...next, status: "uncertain", evidenceOpen: false };
  }
  if (event.type === "refused") {
    const reason =
      typeof event.data.payload.message === "string"
        ? event.data.payload.message
        : "当前问题缺少可引用的企业文档依据，已拒答。";
    return {
      ...next,
      status: "refused",
      answer: state.answer || reason,
      evidenceOpen: false,
    };
  }
  if (event.type === "failed") {
    return {
      ...next,
      status: "failed",
      errorMessage: typeof event.data.payload.message === "string" ? event.data.payload.message : "问答失败",
      evidenceOpen: false,
    };
  }
  if (event.type === "cancelled") {
    return { ...next, status: "cancelled", evidenceOpen: false };
  }
  if (event.type === "run_started" || event.type === "stage") {
    return { ...next, status: "loading" };
  }
  return next;
}

export async function listConversations(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<ConversationList> {
  return api.get<ConversationList>("/conversations", token(accessToken), fetcher);
}

export async function getConversation(
  conversationId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<ConversationSummary> {
  return api.get<ConversationSummary>(
    `/conversations/${encodeURIComponent(conversationId)}`,
    token(accessToken),
    fetcher,
  );
}

export async function listMessages(
  conversationId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<MessageList> {
  return api.get<MessageList>(
    `/conversations/${encodeURIComponent(conversationId)}/messages`,
    token(accessToken),
    fetcher,
  );
}

export async function createConversation(
  title: string,
  scope: ResolvedScope,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<ConversationSummary> {
  return api.post<ConversationSummary>(
    "/conversations",
    conversationCreateBody(title, scope),
    token(accessToken),
    fetcher,
  );
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `idem_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export async function createRun(
  input: {
    conversationId: string;
    question: string;
    scope: ResolvedScope;
    idempotencyKey?: string;
  },
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<RunCreated> {
  const body: Record<string, string> = {
    conversation_id: input.conversationId,
    question: input.question,
    idempotency_key: input.idempotencyKey ?? newIdempotencyKey(),
    scope_type: input.scope.scope_type,
  };
  if (input.scope.scope_type === "document" && input.scope.scope_document_id) {
    body.scope_document_id = input.scope.scope_document_id;
  }
  return api.post<RunCreated>("/runs", body, token(accessToken), fetcher);
}

export function runEventsUrl(runId: string): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/events`;
}

export async function startQuestion(input: {
  question: string;
  conversation?: ConversationSummary | null;
  conversationId?: string | null;
  scopeType?: ScopeType | string;
  scopeDocumentId?: string | null;
  accessToken?: string;
  fetcher?: typeof fetch;
}): Promise<{ conversation: ConversationSummary; run: RunCreated; scope: ResolvedScope }> {
  const question = input.question.trim();
  const requested = resolveQuestionScope({
    scopeType: input.scopeType,
    scopeDocumentId: input.scopeDocumentId,
  });
  let conversation = input.conversation ?? null;
  if (!conversation && input.conversationId) {
    conversation = await getConversation(input.conversationId, input.accessToken, input.fetcher);
  }
  if (!conversation) {
    conversation = await createConversation(question, requested, input.accessToken, input.fetcher);
  }
  const scope = runScopeFromConversation(conversation, {
    scopeType: requested.scope_type,
    scopeDocumentId: requested.scope_document_id,
  });
  const run = await createRun(
    { conversationId: conversation.conversation_id, question, scope },
    input.accessToken,
    input.fetcher,
  );
  return { conversation, run, scope };
}
