import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import { buildAuditQuery } from "./routes";
import type { AuditEventInfo, AuditEventList, AuditQuery } from "./types";

const SENSITIVE_KEY = /prompt|secret|token|password|thinking|completion|hidden/i;

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function listAuditEvents(
  query: AuditQuery = {},
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AuditEventList> {
  return api.get<AuditEventList>(buildAuditQuery(query), token(accessToken), fetcher);
}

export function visibleAuditMetadata(metadata: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!metadata) {
    return {};
  }
  const visible: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(metadata)) {
    if (SENSITIVE_KEY.test(key)) {
      continue;
    }
    if (typeof value === "string" && SENSITIVE_KEY.test(value)) {
      continue;
    }
    visible[key] = value;
  }
  return visible;
}

export function canExpandAuditEvent(event: AuditEventInfo): boolean {
  const action = event.action.toLowerCase();
  return action.includes("qa") || action.includes("ask") || action.includes("question") || Boolean(event.run_id);
}
