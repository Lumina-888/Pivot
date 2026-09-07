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

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function read(relativePath) {
  return fs.readFileSync(path.join(webRoot, relativePath), "utf8");
}

function exists(relativePath) {
  return fs.existsSync(path.join(webRoot, relativePath));
}

function test_FR_RBAC_001_four_admin_routes_exist() {
  for (const file of [
    "app/(admin)/admin/page.tsx",
    "app/(admin)/admin/docs/page.tsx",
    "app/(admin)/admin/users/page.tsx",
    "app/(admin)/admin/audit/page.tsx",
  ]) {
    assert.equal(exists(file), true, `missing ${file}`);
  }
}

async function test_FR_RBAC_001_regular_user_admin_api_is_forbidden() {
  const { ApiError } = await loadTs("lib/api/client.ts");
  const { listAuditEvents } = await loadTs("features/admin/audit.ts");
  const { isAdminForbidden } = await loadTs("features/admin/rbac.ts");
  const fetcher = async (url) => {
    assert.equal(String(url), "/api/v1/admin/audit-events");
    return jsonResponse(403, {
      code: "AUTH_FORBIDDEN",
      message: "无权限访问管理接口",
      request_id: "req_forbid",
      retryable: false,
    });
  };
  await assert.rejects(
    () => listAuditEvents({}, "tok_user", fetcher),
    (error) => {
      assert.equal(error instanceof ApiError, true);
      assert.equal(error.status, 403);
      assert.equal(error.envelope.code, "AUTH_FORBIDDEN");
      assert.equal(isAdminForbidden(error), true);
      return true;
    },
  );
}

async function test_FR_DOC_006_admin_lists_document_states() {
  const { listAdminDocuments, documentStateLabel } = await loadTs("features/admin/documents.ts");
  const fetcher = async (url, init) => {
    assert.equal(String(url), "/api/v1/documents");
    assert.equal(init.headers.get("authorization"), "Bearer tok_admin");
    return jsonResponse(200, {
      items: [
        {
          document_id: "doc_001",
          title: "考勤管理制度 v3",
          created_at: "2026-08-30T00:00:00Z",
          current_version: { version_id: "ver_001", state: "ready" },
        },
        {
          document_id: "doc_002",
          title: "损坏合同",
          created_at: "2026-08-31T00:00:00Z",
          current_version: { version_id: "ver_002", state: "parse_failed" },
        },
      ],
      pagination: null,
    });
  };
  const list = await listAdminDocuments("tok_admin", fetcher);
  assert.equal(list.pagination, null);
  assert.equal(documentStateLabel(list.items[0]), "ready");
  assert.equal(documentStateLabel(list.items[1]), "parse_failed");
}

async function test_FR_DOC_007_retry_and_delete_return_accepted() {
  const { retryDocument, deleteDocument } = await loadTs("features/admin/documents.ts");
  const retry = await retryDocument("doc_fail", "tok_admin", async (url, init) => {
    assert.equal(String(url), "/api/v1/documents/doc_fail/retry");
    assert.equal(init.method, "POST");
    return jsonResponse(202, { document_id: "doc_fail", accepted: true });
  });
  const removed = await deleteDocument("doc_old", "tok_admin", async (url, init) => {
    assert.equal(String(url), "/api/v1/documents/doc_old/delete");
    assert.equal(init.method, "POST");
    return jsonResponse(202, { document_id: "doc_old", accepted: true });
  });
  assert.equal(retry.accepted, true);
  assert.equal(removed.accepted, true);
  const docsView = read("features/admin/components/DocsView.tsx");
  assert.match(docsView, /确认删除/);
}

async function test_FR_AUTH_003_disable_user_patches_disabled() {
  const { disableUser } = await loadTs("features/admin/users.ts");
  const user = await disableUser("user_2", "tok_admin", async (url, init) => {
    assert.equal(String(url), "/api/v1/admin/users/user_2");
    assert.equal(init.method, "PATCH");
    assert.deepEqual(JSON.parse(init.body), { status: "disabled" });
    return jsonResponse(200, {
      user_id: "user_2",
      username: "lisi",
      role: "user",
      status: "disabled",
      created_at: "2026-01-01T00:00:00Z",
    });
  });
  assert.equal(user.status, "disabled");
}

async function test_FR_AUDIT_002_audit_is_readonly_and_redacted() {
  const { listAuditEvents, visibleAuditMetadata, canExpandAuditEvent } = await loadTs("features/admin/audit.ts");
  const { buildAuditQuery } = await loadTs("features/admin/routes.ts");
  const source = read("features/admin/audit.ts");
  assert.doesNotMatch(source, /api\.(post|patch)\(/);
  assert.doesNotMatch(source, /method:\s*"DELETE"/);
  assert.equal(buildAuditQuery({}), "/admin/audit-events");
  assert.equal(buildAuditQuery({ actor: "alice", action: "login" }), "/admin/audit-events?actor=alice&action=login");
  assert.doesNotMatch(buildAuditQuery({ actor: "alice" }), /page=/);

  const fetcher = async (url) => {
    assert.equal(String(url), "/api/v1/admin/audit-events?actor=alice");
    return jsonResponse(200, {
      items: [
        {
          audit_event_id: "aud_1",
          actor: "alice",
          action: "qa",
          target: "会话 conv_1",
          result: "answered",
          run_id: "run_1",
          metadata: {
            prompt: "完整系统提示词",
            hit_documents: ["doc_001"],
            thinking: "隐藏思考链",
          },
          created_at: "2026-09-06T08:00:00Z",
        },
      ],
      pagination: null,
    });
  };
  const list = await listAuditEvents({ actor: "alice" }, "tok_admin", fetcher);
  const visible = visibleAuditMetadata(list.items[0].metadata);
  assert.equal("prompt" in visible, false);
  assert.equal("thinking" in visible, false);
  assert.deepEqual(visible.hit_documents, ["doc_001"]);
  assert.equal(canExpandAuditEvent(list.items[0]), true);
  assert.equal(list.pagination, null);
}

async function test_NFR_OBS_admin_metrics_are_untyped() {
  const { getAdminMetrics, metricEntries } = await loadTs("features/admin/metrics.ts");
  const metrics = await getAdminMetrics("tok_admin", async (url) => {
    assert.equal(String(url), "/api/v1/admin/metrics");
    return jsonResponse(200, { any_future_key: 3 });
  });
  assert.equal(metrics.any_future_key, 3);
  assert.deepEqual(metricEntries(metrics), [["any_future_key", "3"]]);
  const source = read("features/admin/metrics.ts");
  assert.doesNotMatch(source, /document_count|chunk_count|user_count/);
}

function test_pages_show_forbidden_and_loading_states() {
  const shell = read("features/admin/components/AdminAppShell.tsx");
  const forbidden = read("features/admin/components/ForbiddenView.tsx");
  const docs = read("features/admin/components/DocsView.tsx");
  const users = read("features/admin/components/UsersView.tsx");
  const audit = read("features/admin/components/AuditView.tsx");
  assert.match(forbidden, /无权限访问管理后台/);
  assert.match(shell + docs + users + audit, /AUTH_FORBIDDEN|forbidden/);
  assert.match(docs, /正在加载/);
  assert.match(users, /暂无用户/);
  assert.match(audit, /只读/);
}

const tests = [
  ["test_FR_RBAC_001_four_admin_routes_exist", test_FR_RBAC_001_four_admin_routes_exist],
  ["test_FR_RBAC_001_regular_user_admin_api_is_forbidden", test_FR_RBAC_001_regular_user_admin_api_is_forbidden],
  ["test_FR_DOC_006_admin_lists_document_states", test_FR_DOC_006_admin_lists_document_states],
  ["test_FR_DOC_007_retry_and_delete_return_accepted", test_FR_DOC_007_retry_and_delete_return_accepted],
  ["test_FR_AUTH_003_disable_user_patches_disabled", test_FR_AUTH_003_disable_user_patches_disabled],
  ["test_FR_AUDIT_002_audit_is_readonly_and_redacted", test_FR_AUDIT_002_audit_is_readonly_and_redacted],
  ["test_NFR_OBS_admin_metrics_are_untyped", test_NFR_OBS_admin_metrics_are_untyped],
  ["test_pages_show_forbidden_and_loading_states", test_pages_show_forbidden_and_loading_states],
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
