import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { SearchResponse } from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function searchDocuments(
  query: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<SearchResponse> {
  const q = query.trim();
  const path = `/search?q=${encodeURIComponent(q)}`;
  return api.get<SearchResponse>(path, token(accessToken), fetcher);
}
