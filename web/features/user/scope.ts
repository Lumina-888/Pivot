import type { ConversationSummary, ResolvedScope, ScopeType } from "./types";

export function resolveQuestionScope(input: {
  scopeType?: ScopeType | string;
  scopeDocumentId?: string | null;
}): ResolvedScope {
  const documentId = input.scopeDocumentId?.trim();
  if (input.scopeType === "document" || documentId) {
    if (!documentId) {
      throw new Error("scope_document_id required");
    }
    return { scope_type: "document", scope_document_id: documentId };
  }
  return { scope_type: "global" };
}

export function runScopeFromConversation(
  conversation: ConversationSummary,
  requested?: { scopeType?: ScopeType | string; scopeDocumentId?: string | null },
): ResolvedScope {
  if (conversation.scope_type === "document") {
    const documentId = conversation.scope_document_id?.trim();
    if (!documentId) {
      throw new Error("document-scoped conversation missing scope_document_id");
    }
    return { scope_type: "document", scope_document_id: documentId };
  }
  return resolveQuestionScope(requested ?? {});
}

export function conversationCreateBody(title: string, scope: ResolvedScope) {
  if (scope.scope_type === "document") {
    return {
      title,
      scope_type: "document" as const,
      scope_document_id: scope.scope_document_id,
    };
  }
  return { title, scope_type: "global" as const };
}
