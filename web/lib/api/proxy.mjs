/** Same-origin /api/v1 rewrite helper. Origin is injected; never a production URL. */

export const API_PROXY_SOURCE = "/api/v1/:path*";

export function apiProxyRewrites(origin) {
  const raw = String(origin ?? "").trim();
  if (!raw) {
    return [];
  }
  let parsed;
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
  return [
    {
      source: API_PROXY_SOURCE,
      destination: `${parsed.origin}/api/v1/:path*`,
    },
  ];
}
