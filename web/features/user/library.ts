import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { DocumentDetail, DocumentList } from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function listLibraryDocuments(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentList> {
  return api.get<DocumentList>("/documents", token(accessToken), fetcher);
}

export async function getLibraryDocument(
  documentId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<DocumentDetail> {
  return api.get<DocumentDetail>(`/documents/${encodeURIComponent(documentId)}`, token(accessToken), fetcher);
}
