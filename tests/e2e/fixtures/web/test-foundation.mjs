import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const fixtureDir = import.meta.dirname;
const webRoot = path.resolve(fixtureDir, "../../../../web");
const css = fs.readFileSync(path.join(webRoot, "app/globals.css"), "utf8");
const sessionSource = fs.readFileSync(path.join(webRoot, "lib/auth/session.ts"), "utf8");
const streamSource = fs.readFileSync(path.join(webRoot, "lib/stream/sse.ts"), "utf8");
const topbarSource = fs.readFileSync(path.join(webRoot, "components/layouts/Topbar.tsx"), "utf8");
const modalSource = fs.readFileSync(path.join(webRoot, "components/ui/Modal.tsx"), "utf8");
const drawerSource = fs.readFileSync(path.join(webRoot, "components/ui/Drawer.tsx"), "utf8");
const toastSource = fs.readFileSync(path.join(webRoot, "components/ui/Toast.tsx"), "utf8");
const buttonSource = fs.readFileSync(path.join(webRoot, "components/ui/Button.tsx"), "utf8");

function test_NFR_UX_design_tokens_align_s3() {
  for (const token of [
    "--c-bg: #f1f5f9",
    "--c-surface: #ffffff",
    "--c-border: #dbe2ea",
    "--c-head: #234060",
    "--c-accent: #1d4ed8",
    "--c-accent-2: #3b82f6",
    "--c-text: #1e293b",
    "--c-muted: #64748b",
    "--c-ok: #16a34a",
    "--c-danger: #dc2626",
    "--radius: 8px",
  ]) {
    assert.match(css, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
}

function test_NFR_UX_001_keyboard_and_focus_visible() {
  assert.match(css, /:focus-visible/);
  assert.match(css, /outline: 2px solid var\(--c-accent-2\)/);
  assert.match(topbarSource, /ctrlKey/);
  assert.match(topbarSource, /event\.key\.toLowerCase\(\) === "k"/);
  assert.match(modalSource, /Escape/);
  assert.match(drawerSource, /Escape/);
  assert.match(buttonSource, /disabled=\{disabled \|\| loading\}/);
}

function test_NFR_UX_003_aria_live_and_reduced_motion() {
  assert.match(css, /prefers-reduced-motion/);
  assert.match(toastSource, /aria-live="polite"/);
  assert.match(toastSource, /role="status"/);
  assert.match(css, /\.toaster/);
}

function test_FR_AUTH_001_no_long_lived_token_in_storage() {
  assert.doesNotMatch(sessionSource, /localStorage|sessionStorage/);
  assert.match(sessionSource, /HttpOnly cookie/);
}

function test_FR_STREAM_003_sse_reconnect_contract() {
  assert.match(streamSource, /Last-Event-ID/);
  assert.match(streamSource, /SSE_EVENTS/);
  assert.match(streamSource, /terminalSeen/);
}

async function loadTs(relativePath) {
  const fileUrl = pathToFileURL(path.join(webRoot, relativePath)).href;
  return import(fileUrl);
}

function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

async function test_FR_AUTH_001_session_keeps_access_token_in_memory() {
  const { login, logout, getAccessToken, resetAuthForTests } = await loadTs("lib/auth/session.ts");
  resetAuthForTests();
  const fetcher = async (url, init) => {
    assert.match(String(url), /\/api\/v1\/auth\/(login|logout)$/);
    assert.equal(init.credentials, "include");
    if (String(url).endsWith("/auth/login")) {
      return jsonResponse(200, {
        access_token: "tok_memory_only",
        token_type: "Bearer",
        expires_in: 900,
        refresh_token_cookie: true,
      });
    }
    return new Response(null, { status: 204 });
  };
  await login("alice", "secret", fetcher);
  assert.equal(getAccessToken(), "tok_memory_only");
  await logout(fetcher);
  assert.equal(getAccessToken(), null);
}

async function test_contract_error_package_is_decoded() {
  const { api, ApiError } = await loadTs("lib/api/client.ts");
  const fetcher = async () =>
    jsonResponse(401, {
      code: "AUTH_INVALID_CREDENTIALS",
      message: "账号或密码错误",
      request_id: "req_001",
      retryable: false,
    });
  await assert.rejects(
    () => api.post("/auth/login", { username: "a", password: "b" }, undefined, fetcher),
    (error) => {
      assert.equal(error instanceof ApiError, true);
      assert.equal(error.envelope.code, "AUTH_INVALID_CREDENTIALS");
      assert.equal(error.envelope.request_id, "req_001");
      return true;
    },
  );
}

function sseStream(chunks) {
  return new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

function envelope(seq, extra = {}) {
  return {
    run_id: "run_001",
    message_id: "msg_001",
    seq,
    timestamp: "2026-09-06T08:00:00Z",
    stage: extra.stage ?? "retrieving",
    payload: extra.payload ?? {},
  };
}

async function test_FR_STREAM_002_seq_dedup_and_single_terminal() {
  const { connectSse } = await loadTs("lib/stream/sse.ts");
  const events = [];
  const statuses = [];
  const body = [
    `event: run_started\nid: 1\ndata: ${JSON.stringify(envelope(1, { stage: "received" }))}\n\n`,
    `event: token\nid: 1\ndata: ${JSON.stringify(envelope(1, { stage: "drafting" }))}\n\n`,
    `event: completed\nid: 2\ndata: ${JSON.stringify(envelope(2, { stage: "answered" }))}\n\n`,
    `event: failed\nid: 3\ndata: ${JSON.stringify(envelope(3, { stage: "failed" }))}\n\n`,
    `event: unknown\nid: 4\ndata: ${JSON.stringify(envelope(4))}\n\n`,
  ].join("");
  await connectSse({
    url: "/api/v1/runs/run_001/events",
    onStatus: (status) => statuses.push(status),
    onEvent: (event) => events.push(event),
    fetcher: async (url, init) => {
      assert.equal(String(url), "/api/v1/runs/run_001/events");
      assert.equal(init.headers.get("Accept"), "text/event-stream");
      assert.equal(init.credentials, "include");
      return new Response(sseStream([body]), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      });
    },
  });
  assert.deepEqual(statuses, ["connecting", "open", "closed"]);
  assert.deepEqual(
    events.map((event) => [event.type, event.data.seq]),
    [
      ["run_started", 1],
      ["completed", 2],
    ],
  );
}

async function test_FR_STREAM_003_reconnects_from_last_event_id() {
  const { connectSse } = await loadTs("lib/stream/sse.ts");
  let lastEventId;
  await connectSse({
    url: "/api/v1/runs/run_001/events",
    lastEventId: 17,
    token: "tok_001",
    onEvent: () => {},
    fetcher: async (_url, init) => {
      lastEventId = init.headers.get("Last-Event-ID");
      assert.equal(init.headers.get("authorization"), "Bearer tok_001");
      return new Response(sseStream([]), { status: 200 });
    },
  });
  assert.equal(lastEventId, "17");
}

async function test_FR_STREAM_002_sse_client_ignores_keepalive_comments() {
  const { connectSse } = await loadTs("lib/stream/sse.ts");
  const events = [];
  const body = [
    ": keepalive\n\n",
    `event: run_started\nid: 1\ndata: ${JSON.stringify(envelope(1, { stage: "received" }))}\n\n`,
    ": keepalive\n\n",
    `event: completed\nid: 2\ndata: ${JSON.stringify(envelope(2, { stage: "answered" }))}\n\n`,
  ].join("");
  await connectSse({
    url: "/api/v1/runs/run_001/events",
    onEvent: (event) => events.push(event),
    fetcher: async () =>
      new Response(sseStream([body]), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
  });
  assert.deepEqual(
    events.map((event) => [event.type, event.data.seq]),
    [
      ["run_started", 1],
      ["completed", 2],
    ],
  );
}

async function test_FR_STREAM_003_follow_run_events_reconnects_until_terminal() {
  const { followRunEvents } = await loadTs("lib/stream/sse.ts");
  const events = [];
  const lastEventIds = [];
  let calls = 0;
  await followRunEvents({
    url: "/api/v1/runs/run_001/events",
    retryDelayMs: 0,
    onEvent: (event) => events.push(event),
    fetcher: async (_url, init) => {
      calls += 1;
      lastEventIds.push(init.headers.get("Last-Event-ID"));
      if (calls === 1) {
        const body = `event: run_started\nid: 1\ndata: ${JSON.stringify(envelope(1, { stage: "received" }))}\n\n`;
        return new Response(sseStream([body]), {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }
      const body = `event: completed\nid: 2\ndata: ${JSON.stringify(envelope(2, { stage: "answered" }))}\n\n`;
      return new Response(sseStream([body]), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      });
    },
  });
  assert.equal(calls, 2);
  assert.deepEqual(lastEventIds, [null, "1"]);
  assert.deepEqual(
    events.map((event) => [event.type, event.data.seq]),
    [
      ["run_started", 1],
      ["completed", 2],
    ],
  );
}

async function test_FR_AUTH_001_web_api_base_stays_same_origin() {
  const { API_BASE } = await loadTs("lib/api/client.ts");
  assert.equal(API_BASE, "/api/v1");
  assert.doesNotMatch(API_BASE, /^https?:\/\//);
}

async function loadProxy() {
  return import(pathToFileURL(path.join(webRoot, "lib/api/proxy.mjs")).href);
}

async function test_FR_AUTH_001_next_rewrites_api_v1_to_injected_origin() {
  const { apiProxyRewrites, API_PROXY_SOURCE } = await loadProxy();
  const rules = apiProxyRewrites("http://127.0.0.1:8000");
  assert.deepEqual(rules, [
    {
      source: API_PROXY_SOURCE,
      destination: "http://127.0.0.1:8000/api/v1/:path*",
    },
  ]);
}

function test_FR_AUTH_001_next_config_wires_injected_origin() {
  const source = fs.readFileSync(path.join(webRoot, "next.config.mjs"), "utf8");
  assert.match(source, /apiProxyRewrites/);
  assert.match(source, /PIVOT_API_ORIGIN/);
  assert.match(source, /rewrites\s*\(/);
  assert.doesNotMatch(source, /minio|openai|qdrant|s3\.amazonaws/i);
  assert.doesNotMatch(source, /127\.0\.0\.1|localhost/);
}

async function test_NFR_OBS_next_rewrites_omitted_when_origin_missing() {
  const { apiProxyRewrites } = await loadProxy();
  assert.deepEqual(apiProxyRewrites(undefined), []);
  assert.deepEqual(apiProxyRewrites(""), []);
  assert.deepEqual(apiProxyRewrites("   "), []);
}

async function test_NFR_SEC_next_proxy_rejects_non_http_origin() {
  const { apiProxyRewrites } = await loadProxy();
  assert.throws(() => apiProxyRewrites("ftp://127.0.0.1:8000"), /http/);
  assert.throws(() => apiProxyRewrites("not-a-url"), /origin/);
  assert.throws(() => apiProxyRewrites("http://127.0.0.1:8000/api/v1"), /path/);
}

async function test_FR_STREAM_002_next_sse_route_disables_buffering() {
  const { sseResponseHeaders, sseUpstreamUrl } = await loadTs("lib/api/sse-proxy.ts");
  const headers = sseResponseHeaders();
  assert.equal(headers["Content-Type"], "text/event-stream");
  assert.match(headers["Cache-Control"], /no-cache/);
  assert.match(headers["Cache-Control"], /no-transform/);
  assert.equal(headers["X-Accel-Buffering"], "no");
  assert.equal(headers.Connection, "keep-alive");
  assert.equal(
    sseUpstreamUrl("http://127.0.0.1:8000", "run_001"),
    "http://127.0.0.1:8000/api/v1/runs/run_001/events",
  );
  const route = fs.readFileSync(
    path.join(webRoot, "app/api/v1/runs/[id]/events/route.ts"),
    "utf8",
  );
  assert.match(route, /force-dynamic/);
  assert.match(route, /sseResponseHeaders/);
  assert.match(route, /upstream\.body/);
  assert.match(route, /PIVOT_API_ORIGIN/);
  assert.doesNotMatch(route, /minio|openai|qdrant/i);
}

function test_GATE_P0_005_not_verified_by_next_rewrite() {
  const evidence = fs.readFileSync(
    path.join(webRoot, "../evidence/wave3-m11/next-api-proxy.md"),
    "utf8",
  );
  assert.match(evidence, /GATE-P0-005/);
  assert.match(evidence, /unverified/i);
  assert.match(evidence, /rewrite|proxy/i);
  const limits = fs.readFileSync(path.join(webRoot, "../evidence/wave2-m11/limits.md"), "utf8");
  const line = limits.split(/\r?\n/).find((item) => item.includes("GATE-P0-005"));
  assert.ok(line);
  assert.match(line, /unverified/i);
  assert.doesNotMatch(line.replace(/unverified/gi, ""), /verified/i);
}

const tests = [
  ["test_NFR_UX_design_tokens_align_s3", test_NFR_UX_design_tokens_align_s3],
  ["test_NFR_UX_001_keyboard_and_focus_visible", test_NFR_UX_001_keyboard_and_focus_visible],
  ["test_NFR_UX_003_aria_live_and_reduced_motion", test_NFR_UX_003_aria_live_and_reduced_motion],
  ["test_FR_AUTH_001_no_long_lived_token_in_storage", test_FR_AUTH_001_no_long_lived_token_in_storage],
  ["test_FR_STREAM_003_sse_reconnect_contract", test_FR_STREAM_003_sse_reconnect_contract],
  ["test_FR_AUTH_001_session_keeps_access_token_in_memory", test_FR_AUTH_001_session_keeps_access_token_in_memory],
  ["test_contract_error_package_is_decoded", test_contract_error_package_is_decoded],
  ["test_FR_STREAM_002_seq_dedup_and_single_terminal", test_FR_STREAM_002_seq_dedup_and_single_terminal],
  ["test_FR_STREAM_003_reconnects_from_last_event_id", test_FR_STREAM_003_reconnects_from_last_event_id],
  ["test_FR_STREAM_002_sse_client_ignores_keepalive_comments", test_FR_STREAM_002_sse_client_ignores_keepalive_comments],
  ["test_FR_STREAM_003_follow_run_events_reconnects_until_terminal", test_FR_STREAM_003_follow_run_events_reconnects_until_terminal],
  ["test_FR_AUTH_001_web_api_base_stays_same_origin", test_FR_AUTH_001_web_api_base_stays_same_origin],
  ["test_FR_AUTH_001_next_rewrites_api_v1_to_injected_origin", test_FR_AUTH_001_next_rewrites_api_v1_to_injected_origin],
  ["test_FR_AUTH_001_next_config_wires_injected_origin", test_FR_AUTH_001_next_config_wires_injected_origin],
  ["test_NFR_OBS_next_rewrites_omitted_when_origin_missing", test_NFR_OBS_next_rewrites_omitted_when_origin_missing],
  ["test_NFR_SEC_next_proxy_rejects_non_http_origin", test_NFR_SEC_next_proxy_rejects_non_http_origin],
  ["test_FR_STREAM_002_next_sse_route_disables_buffering", test_FR_STREAM_002_next_sse_route_disables_buffering],
  ["test_GATE_P0_005_not_verified_by_next_rewrite", test_GATE_P0_005_not_verified_by_next_rewrite],
];

let failed = 0;
for (const [name, fn] of tests) {
  try {
    await fn();
    console.log(`ok ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`not ok ${name}`);
    console.error(error);
  }
}

if (failed) {
  process.exit(1);
}
console.log(`${tests.length} passed`);
