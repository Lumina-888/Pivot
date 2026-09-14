/** Unbuffered SSE upstream helper. Origin is injected; never a production URL. */

export function sseResponseHeaders(): Record<string, string> {
  return {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  };
}

export function sseUpstreamUrl(origin: string, runId: string): string {
  const raw = String(origin ?? "").trim();
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("PIVOT_API_ORIGIN must be an absolute http(s) origin");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("PIVOT_API_ORIGIN must be an absolute http(s) origin");
  }
  if (parsed.username || parsed.password) {
    throw new Error("PIVOT_API_ORIGIN must not include credentials");
  }
  if (parsed.pathname !== "/" && parsed.pathname !== "") {
    throw new Error("PIVOT_API_ORIGIN must not include a path");
  }
  if (parsed.search || parsed.hash) {
    throw new Error("PIVOT_API_ORIGIN must not include a query or fragment");
  }
  return `${parsed.origin}/api/v1/runs/${encodeURIComponent(runId)}/events`;
}
