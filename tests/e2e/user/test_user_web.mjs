import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const fixtureDir = import.meta.dirname;
const repoRoot = path.resolve(fixtureDir, "../../..");
const webRoot = path.join(repoRoot, "web");

function loadTs(relativePath) {
  return import(pathToFileURL(path.join(webRoot, relativePath)).href);
}

function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

function read(relativePath) {
  return fs.readFileSync(path.join(webRoot, relativePath), "utf8");
}

function exists(relativePath) {
  return fs.existsSync(path.join(webRoot, relativePath));
}

function envelope(seq, extra = {}) {
  return {
    run_id: extra.run_id ?? "run_001",
    message_id: extra.message_id ?? "msg_001",
    seq,
    timestamp: "2026-09-06T08:00:00Z",
    stage: extra.stage ?? "retrieving",
    payload: extra.payload ?? {},
  };
}

function test_FR_AUTH_001_six_user_routes_exist_and_assembly_page_removed() {
  assert.equal(exists("app/page.tsx"), false, "M08 assembly page must be removed");
  for (const file of [
    "app/(user)/login/page.tsx",
    "app/(user)/(app)/page.tsx",
    "app/(user)/(app)/library/page.tsx",
    "app/(user)/(app)/library/[id]/page.tsx",
    "app/(user)/(app)/search/page.tsx",
    "app/(user)/(app)/chat/page.tsx",
    "app/(user)/(app)/chat/[id]/page.tsx",
  ]) {
    assert.equal(exists(file), true, `missing ${file}`);
  }
}

async function test_FR_AUTH_001_login_success_redirects_home() {
  const { resetAuthForTests, getAccessToken } = await loadTs("lib/auth/session.ts");
  const { loginWithCredentials } = await loadTs("features/user/auth.ts");
  resetAuthForTests();
  const fetcher = async (url, init) => {
    assert.match(String(url), /\/api\/v1\/auth\/login$/);
    assert.equal(init.credentials, "include");
    const body = JSON.parse(init.body);
    assert.equal(body.username, "alice");
    assert.equal(body.password, "secret");
    return jsonResponse(200, {
      access_token: "tok_user",
      token_type: "Bearer",
      expires_in: 900,
      refresh_token_cookie: true,
    });
  };
  const result = await loginWithCredentials("alice", "secret", fetcher);
  assert.deepEqual(result, { ok: true, redirectTo: "/" });
  assert.equal(getAccessToken(), "tok_user");
}

async function test_FR_AUTH_001_invalid_credentials_generic_error() {
  const { resetAuthForTests, getAccessToken } = await loadTs("lib/auth/session.ts");
  const { loginWithCredentials, GENERIC_LOGIN_ERROR } = await loadTs("features/user/auth.ts");
  resetAuthForTests();
  const fetcher = async () =>
    jsonResponse(401, {
      code: "AUTH_INVALID_CREDENTIALS",
      message: "用户不存在",
      request_id: "req_login_fail",
      retryable: false,
    });
  const result = await loginWithCredentials("nobody", "wrong", fetcher);
  assert.equal(result.ok, false);
  assert.equal(result.message, GENERIC_LOGIN_ERROR);
  assert.notEqual(result.message, "用户不存在");
  assert.equal(getAccessToken(), null);
}

async function test_FR_SEARCH_001_library_lists_authorized_documents() {
  const { listLibraryDocuments } = await loadTs("features/user/library.ts");
  const fetcher = async (url, init) => {
    assert.equal(String(url), "/api/v1/documents");
    assert.equal(init.headers.get("authorization"), "Bearer tok_lib");
    assert.equal(init.credentials, "include");
    return jsonResponse(200, {
      items: [
        {
          document_id: "doc_hr_001",
          title: "考勤管理制度 v3",
          space: "人事制度",
          created_at: "2026-08-30T00:00:00Z",
        },
      ],
      pagination: null,
    });
  };
  const list = await listLibraryDocuments("tok_lib", fetcher);
  assert.equal(list.items.length, 1);
  assert.equal(list.items[0].document_id, "doc_hr_001");
  assert.equal(list.pagination, null);
}

async function test_FR_SEARCH_001_global_search_keeps_query() {
  const { searchPageHref } = await loadTs("features/user/routes.ts");
  const { searchDocuments } = await loadTs("features/user/search.ts");
  assert.equal(searchPageHref("年假 累计"), "/search?q=" + encodeURIComponent("年假 累计"));
  const fetcher = async (url, init) => {
    assert.equal(String(url), "/api/v1/search?q=" + encodeURIComponent("年假"));
    assert.equal(init.headers.get("authorization"), "Bearer tok_search");
    return jsonResponse(200, {
      items: [{ document_id: "doc_hr_001", title: "考勤管理制度 v3", snippet: "年假不可跨年" }],
      pagination: null,
    });
  };
  const result = await searchDocuments("年假", "tok_search", fetcher);
  assert.equal(result.items[0].title, "考勤管理制度 v3");
}

async function test_FR_QA_001_search_carries_original_question_into_chat() {
  const { chatHrefFromSearch, parseChatSearchParams } = await loadTs("features/user/routes.ts");
  const question = "年假能否跨年累计？";
  const href = chatHrefFromSearch(question);
  assert.equal(href, `/chat?q=${encodeURIComponent(question)}`);
  const parsed = parseChatSearchParams({ q: question });
  assert.equal(parsed.question, question);
  assert.equal(parsed.scopeType, "global");
  assert.equal(parsed.scopeDocumentId, null);
}

async function test_FR_RAG_002_document_scope_does_not_widen_to_global() {
  const { documentChatHref, parseChatSearchParams } = await loadTs("features/user/routes.ts");
  const { startQuestion } = await loadTs("features/user/chat.ts");
  const href = documentChatHref("doc_hr_001", "年假规则");
  assert.match(href, /scope=document/);
  assert.match(href, /document_id=doc_hr_001/);
  const parsed = parseChatSearchParams({
    q: "年假规则",
    scope: "document",
    document_id: "doc_hr_001",
  });
  assert.equal(parsed.scopeType, "document");
  assert.equal(parsed.scopeDocumentId, "doc_hr_001");

  const calls = [];
  const fetcher = async (url, init) => {
    const hrefUrl = String(url);
    calls.push({ href: hrefUrl, body: init.body ? JSON.parse(init.body) : null });
    if (hrefUrl.endsWith("/conversations")) {
      return jsonResponse(201, {
        conversation_id: "conv_doc",
        owner_id: "user_1",
        title: "年假规则",
        scope_type: "document",
        scope_document_id: "doc_hr_001",
        created_at: "2026-09-06T08:00:00Z",
        updated_at: "2026-09-06T08:00:00Z",
      });
    }
    if (hrefUrl.endsWith("/runs")) {
      return jsonResponse(200, {
        run_id: "run_doc",
        message_id: "msg_doc",
        initial_state: {},
        request_id: "req_doc",
      });
    }
    throw new Error(`unexpected ${hrefUrl}`);
  };
  const started = await startQuestion({
    question: "年假规则",
    scopeType: "document",
    scopeDocumentId: "doc_hr_001",
    accessToken: "tok_scope",
    fetcher,
  });
  const runCall = calls.find((call) => call.href.endsWith("/runs"));
  assert.equal(runCall.body.scope_type, "document");
  assert.equal(runCall.body.scope_document_id, "doc_hr_001");
  assert.equal(started.scope.scope_type, "document");
  assert.notEqual(runCall.body.scope_type, "global");

  const widenFetcher = async (url, init) => {
    const hrefUrl = String(url);
    if (hrefUrl.endsWith("/runs")) {
      const body = JSON.parse(init.body);
      assert.equal(body.scope_type, "document");
      assert.equal(body.scope_document_id, "doc_hr_001");
      return jsonResponse(200, {
        run_id: "run_keep",
        message_id: "msg_keep",
        initial_state: {},
        request_id: "req_keep",
      });
    }
    throw new Error(`unexpected ${hrefUrl}`);
  };
  await startQuestion({
    question: "扩大范围？",
    conversation: {
      conversation_id: "conv_doc",
      owner_id: "user_1",
      title: "年假规则",
      scope_type: "document",
      scope_document_id: "doc_hr_001",
      created_at: "2026-09-06T08:00:00Z",
      updated_at: "2026-09-06T08:00:00Z",
    },
    scopeType: "global",
    accessToken: "tok_scope",
    fetcher: widenFetcher,
  });
}

async function test_FR_QA_004_citation_opens_non_persistent_evidence_drawer() {
  const { applyStreamEvent, closeEvidence, createEmptyChatState, openEvidence } = await loadTs(
    "features/user/chat.ts",
  );
  let state = createEmptyChatState();
  assert.equal(state.evidenceOpen, false);
  state = applyStreamEvent(state, {
    type: "citation",
    data: envelope(1, {
      stage: "drafting",
      payload: {
        citation_id: "cite_1",
        document_id: "doc_hr_001",
        title: "考勤管理制度 v3",
        locator: "P12 §5.2",
        snippet: "当年有效，不跨年结转",
      },
    }),
  });
  assert.equal(state.evidenceOpen, false);
  assert.equal(state.citations.length, 1);
  state = openEvidence(state, state.citations[0]);
  assert.equal(state.evidenceOpen, true);
  assert.equal(state.selectedCitation.locator, "P12 §5.2");
  state = closeEvidence(state);
  assert.equal(state.evidenceOpen, false);
  state = applyStreamEvent(state, {
    type: "completed",
    data: envelope(2, { stage: "answered" }),
  });
  assert.equal(state.evidenceOpen, false);
  assert.equal(state.status, "answered");
}

async function test_FR_QA_003_refused_state_is_visible() {
  const { applyStreamEvent, createEmptyChatState } = await loadTs("features/user/chat.ts");
  let state = createEmptyChatState();
  state = applyStreamEvent(state, {
    type: "refused",
    data: envelope(1, {
      stage: "refused",
      payload: { message: "当前问题缺少可引用的企业文档依据，已拒答。" },
    }),
  });
  assert.equal(state.status, "refused");
  assert.match(state.answer, /拒答/);
  const chatSource = read("features/user/components/ChatWorkspace.tsx");
  assert.match(chatSource, /status === "refused"/);
  assert.match(chatSource, /已拒答/);
}

async function test_FR_EXPORT_001_export_uses_persisted_answer_contract() {
  const { requestReadyDownload, isInternalStorageUrl } = await loadTs("features/user/export.ts");
  const calls = [];
  const fetcher = async (url, init) => {
    const href = String(url);
    calls.push({ href, method: init.method, body: init.body ? JSON.parse(init.body) : null });
    if (href.endsWith("/exports") && init.method === "POST") {
      assert.deepEqual(JSON.parse(init.body), {
        source_type: "conversation",
        source_id: "conv_001",
        format: "markdown",
      });
      return jsonResponse(202, { export_id: "exp_001", state: "requested" }, { "content-type": "application/json" });
    }
    if (href.endsWith("/exports/exp_001")) {
      return jsonResponse(200, {
        export_id: "exp_001",
        state: "ready",
        download_url: "https://files.example.internal/signed/exp_001?token=short",
        expires_at: "2026-09-06T09:00:00Z",
      });
    }
    throw new Error(href);
  };
  const result = await requestReadyDownload({
    sourceId: "conv_001",
    format: "markdown",
    accessToken: "tok_export",
    fetcher,
  });
  assert.equal(result.created.state, "requested");
  assert.equal(result.status.state, "ready");
  assert.equal(result.downloadUrl, "https://files.example.internal/signed/exp_001?token=short");
  assert.equal(isInternalStorageUrl("http://minio:9000/bucket/obj"), true);
  assert.equal(isInternalStorageUrl(result.downloadUrl), false);
  assert.equal(
    calls.some((call) => call.href.includes("/runs") || call.href.includes("/conversations/")),
    false,
  );
}

async function test_FR_EXPORT_003_expired_download_is_blocked() {
  const { downloadUrlForReady, getExportStatus } = await loadTs("features/user/export.ts");
  const expired = await getExportStatus("exp_dead", "tok_export", async (url) => {
    assert.equal(String(url), "/api/v1/exports/exp_dead");
    return jsonResponse(410, {
      code: "EXPORT_EXPIRED",
      message: "导出已过期",
      request_id: "req_exp",
      retryable: false,
    });
  });
  assert.equal(expired.state, "expired");
  assert.equal(downloadUrlForReady(expired), null);
  assert.equal(
    downloadUrlForReady({
      export_id: "exp_minio",
      state: "ready",
      download_url: "http://127.0.0.1:9000/pivot/export.docx",
      expires_at: "2026-09-06T09:00:00Z",
    }),
    null,
  );
}

function test_pages_call_authorized_api_not_hidden_entry() {
  const library = read("features/user/library.ts");
  const search = read("features/user/search.ts");
  const chat = read("features/user/chat.ts");
  const exp = read("features/user/export.ts");
  assert.match(library, /\/documents/);
  assert.match(search, /\/search\?q=/);
  assert.match(chat, /\/runs/);
  assert.match(exp, /\/exports/);
  assert.doesNotMatch(library + search + chat + exp, /localStorage|sessionStorage/);
}

function test_FR_STREAM_003_chat_follows_sse_until_terminal() {
  const workspace = read("features/user/components/ChatWorkspace.tsx");
  assert.match(workspace, /followRunEvents/);
  assert.match(workspace, /runEventsUrl/);
}

const tests = [
  ["test_FR_AUTH_001_six_user_routes_exist_and_assembly_page_removed", test_FR_AUTH_001_six_user_routes_exist_and_assembly_page_removed],
  ["test_FR_AUTH_001_login_success_redirects_home", test_FR_AUTH_001_login_success_redirects_home],
  ["test_FR_AUTH_001_invalid_credentials_generic_error", test_FR_AUTH_001_invalid_credentials_generic_error],
  ["test_FR_SEARCH_001_library_lists_authorized_documents", test_FR_SEARCH_001_library_lists_authorized_documents],
  ["test_FR_SEARCH_001_global_search_keeps_query", test_FR_SEARCH_001_global_search_keeps_query],
  ["test_FR_QA_001_search_carries_original_question_into_chat", test_FR_QA_001_search_carries_original_question_into_chat],
  ["test_FR_RAG_002_document_scope_does_not_widen_to_global", test_FR_RAG_002_document_scope_does_not_widen_to_global],
  ["test_FR_QA_004_citation_opens_non_persistent_evidence_drawer", test_FR_QA_004_citation_opens_non_persistent_evidence_drawer],
  ["test_FR_QA_003_refused_state_is_visible", test_FR_QA_003_refused_state_is_visible],
  ["test_FR_EXPORT_001_export_uses_persisted_answer_contract", test_FR_EXPORT_001_export_uses_persisted_answer_contract],
  ["test_FR_EXPORT_003_expired_download_is_blocked", test_FR_EXPORT_003_expired_download_is_blocked],
  ["test_pages_call_authorized_api_not_hidden_entry", test_pages_call_authorized_api_not_hidden_entry],
  ["test_FR_STREAM_003_chat_follows_sse_until_terminal", test_FR_STREAM_003_chat_follows_sse_until_terminal],
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
