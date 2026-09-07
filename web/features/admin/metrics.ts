import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function getAdminMetrics(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<Record<string, unknown>> {
  const value = await api.get<unknown>("/admin/metrics", token(accessToken), fetcher);
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

export function metricEntries(metrics: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(metrics).map(([key, value]) => [
    key,
    typeof value === "string" || typeof value === "number" || typeof value === "boolean"
      ? String(value)
      : JSON.stringify(value),
  ]);
}
