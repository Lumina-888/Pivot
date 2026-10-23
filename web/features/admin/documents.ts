import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { DocumentActionResponse, DocumentList, DocumentUploadResponse } from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function listAdminDocuments(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentList> {
  return api.get<DocumentList>("/documents", token(accessToken), fetcher);
}

export async function uploadDocument(
  file: File,
  options: { title?: string; space?: string; externalLlmAllowed?: boolean } = {},
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentUploadResponse> {
  const form = new FormData();
  const fallbackTitle = file.name.replace(/\.[^.]+$/, "");
  form.set("title", options.title?.trim() || fallbackTitle || file.name);
  form.set("space", options.space?.trim() || "shared");
  form.set("external_llm_allowed", options.externalLlmAllowed ? "true" : "false");
  form.set("file", file);
  return api.post<DocumentUploadResponse>("/documents", form, token(accessToken), fetcher);
}

export async function retryDocument(
  documentId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentActionResponse> {
  return api.post<DocumentActionResponse>(
    `/documents/${encodeURIComponent(documentId)}/retry`,
    undefined,
    token(accessToken),
    fetcher,
  );
}

export async function deleteDocument(
  documentId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentActionResponse> {
  return api.post<DocumentActionResponse>(
    `/documents/${encodeURIComponent(documentId)}/delete`,
    undefined,
    token(accessToken),
    fetcher,
  );
}

export function documentStateLabel(doc: { current_version?: { state?: string } | null }): string {
  return doc.current_version?.state ?? "unknown";
}
