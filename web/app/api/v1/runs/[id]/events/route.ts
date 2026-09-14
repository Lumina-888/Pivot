import { NextRequest } from "next/server";
import { sseResponseHeaders, sseUpstreamUrl } from "@/lib/api/sse-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: { id: string } }) {
  const origin = String(process.env.PIVOT_API_ORIGIN ?? "").trim();
  if (!origin) {
    return new Response("Not Found", { status: 404 });
  }

  const headers = new Headers({ Accept: "text/event-stream" });
  const authorization = request.headers.get("authorization");
  if (authorization) {
    headers.set("authorization", authorization);
  }
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) {
    headers.set("Last-Event-ID", lastEventId);
  }
  const requestId = request.headers.get("x-request-id");
  if (requestId) {
    headers.set("X-Request-ID", requestId);
  }
  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.set("cookie", cookie);
  }

  const upstream = await fetch(sseUpstreamUrl(origin, context.params.id), {
    headers,
    cache: "no-store",
    signal: request.signal,
  });
  if (!upstream.body) {
    return new Response(upstream.statusText, { status: upstream.status });
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: sseResponseHeaders(),
  });
}
