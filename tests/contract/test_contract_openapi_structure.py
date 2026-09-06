"""契约测试：OpenAPI 路由/方法与公共格式（SPEC §5.1~5.5、附录 B/C）。

验证：
- openapi 版本与 servers base path（/api/v1）；
- §5.2~5.5 全部路径与方法的超集关系（契约不得少于 SPEC 声明路由）；
- 认证接口之外的所有 operation 强制 bearerAuth（服务端授权，SPEC §1.2、FR-RBAC）；
- 不透明 ID 与 ISO8601 UTC 时间格式组件；
- POST /runs 请求结构（SPEC §5.4 示例）；
- 上传 multipart 字段（SPEC §5.3）。
"""

from conftest import schema_ref, validate, validate_against_root

# SPEC §5.2~5.5 路由表（契约必须覆盖的最小集合）
SPEC_ROUTES = {
    "/auth/login": {"post"},
    "/auth/refresh": {"post"},
    "/auth/logout": {"post"},
    "/auth/change-password": {"post"},
    "/documents": {"get", "post"},
    "/documents/{id}": {"get"},
    "/documents/{id}/versions": {"get"},
    "/documents/{id}/retry": {"post"},
    "/documents/{id}/delete": {"post"},
    "/documents/{id}/preview": {"get"},
    "/documents/{id}/download": {"get"},
    "/search": {"get"},
    "/conversations": {"get", "post"},
    "/conversations/{id}": {"get", "delete"},
    "/conversations/{id}/messages": {"get"},
    "/runs": {"post"},
    "/runs/{id}": {"get"},
    "/runs/{id}/events": {"get"},
    "/runs/{id}/cancel": {"post"},
    "/exports": {"post"},
    "/exports/{id}": {"get"},
    "/admin/metrics": {"get"},
    "/admin/tasks": {"get"},
    "/admin/users": {"get", "post"},
    "/admin/users/{id}": {"patch"},
    "/admin/audit-events": {"get"},
}

# 允许匿名访问的接口（仅登录与刷新；SPEC §5.2）
PUBLIC_PATHS = {"/auth/login", "/auth/refresh"}

HTTP_METHODS = {"get", "post", "patch", "put", "delete"}


def iter_operations(openapi_doc):
    for path, path_item in openapi_doc.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method in path_item:
                yield path, method, path_item[method]


def test_openapi_version_and_identity(openapi_doc):
    assert openapi_doc["openapi"].startswith("3.0")
    assert openapi_doc["info"]["title"]
    assert openapi_doc["info"]["version"]


def test_servers_base_path_is_api_v1(openapi_doc):
    servers = openapi_doc.get("servers", [])
    assert servers, "契约必须声明 servers"
    for server in servers:
        assert server["url"].rstrip("/").endswith("/api/v1")


def test_routes_cover_spec_section5(openapi_doc):
    paths = openapi_doc["paths"]
    for route, methods in SPEC_ROUTES.items():
        assert route in paths, f"SPEC §5 路由缺失：{route}"
        assert methods.issubset(set(paths[route])), f"{route} 缺少方法：{methods}"


def test_bearer_security_scheme_defined(openapi_doc):
    scheme = openapi_doc["components"]["securitySchemes"]["bearerAuth"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme.get("bearerFormat") == "JWT"


def effective_security(openapi_doc, operation):
    """operation 显式 security 优先；未声明时继承文件级全局 security。"""
    return operation.get("security", openapi_doc.get("security", []))


def test_all_protected_operations_require_bearer(openapi_doc):
    for path, method, operation in iter_operations(openapi_doc):
        if path in PUBLIC_PATHS:
            continue
        security = effective_security(openapi_doc, operation)
        assert security, f"{method.upper()} {path} 未声明 security"
        assert any("bearerAuth" in entry for entry in security), (
            f"{method.upper()} {path} 未声明 bearerAuth"
        )


def test_admin_operations_require_bearer(openapi_doc):
    """FR-RBAC-001：普通用户请求 /api/v1/admin/* 必须由服务端拒绝。"""
    for path, method, operation in iter_operations(openapi_doc):
        if path.startswith("/admin/"):
            security = effective_security(openapi_doc, operation)
            assert any("bearerAuth" in entry for entry in security), (
                f"{method.upper()} {path} 后台接口必须声明 bearerAuth"
            )


def test_public_auth_operations_allow_anonymous(openapi_doc):
    """仅 login/refresh 匿名（SPEC §5.2）；其余默认经全局 security 保护。"""
    for path, method, operation in iter_operations(openapi_doc):
        if path in PUBLIC_PATHS:
            assert operation.get("security") == [], (
                f"{method.upper()} {path} 必须显式声明 security: [] 覆盖全局鉴权"
            )


def test_id_component_is_opaque_string(openapi_doc):
    """SPEC §5.1/附录 B.3：ID 是不透明字符串，禁止依赖自增暴露业务顺序。"""
    id_schema = schema_ref(openapi_doc, "#/components/schemas/Id")
    assert id_schema["type"] == "string"
    assert "integer" not in id_schema.get("type", "")


def test_time_component_is_iso8601_utc(openapi_doc):
    ts = schema_ref(openapi_doc, "#/components/schemas/TimeStamp")
    assert ts["type"] == "string"
    assert ts.get("format") == "date-time"


def test_create_run_request_structure(openapi_doc):
    """SPEC §5.4 POST /runs 请求。"""
    create_run = schema_ref(openapi_doc, "#/components/schemas/CreateRunRequest")
    assert {"conversation_id", "question", "idempotency_key"}.issubset(
        set(create_run.get("required", []))
    )
    props = create_run["properties"]
    assert props["scope_type"]["enum"] == ["global", "document"]
    assert props["scope_document_id"]["type"] == "string"
    # 示例载荷可校验（含 $ref 解析）
    validate_against_root(
        {
            "conversation_id": "conv_001",
            "question": "请说明迟到处理规则",
            "scope_type": "document",
            "scope_document_id": "doc_001",
            "idempotency_key": "idem_001",
        },
        create_run,
        openapi_doc,
    )


def test_run_created_response_fields(openapi_doc):
    """SPEC §5.4：POST /runs 返回至少 run_id/message_id/initial_state/request_id。"""
    created = schema_ref(openapi_doc, "#/components/schemas/RunCreated")
    assert {"run_id", "message_id", "initial_state", "request_id"}.issubset(
        set(created.get("required", []))
    )


def test_upload_multipart_fields(openapi_doc):
    """SPEC §5.3：上传 multipart + 幂等键 + 服务端可计算 content_sha256。"""
    upload = schema_ref(openapi_doc, "#/components/schemas/UploadDocument")
    assert {"title", "file"}.issubset(set(upload.get("required", [])))
    props = upload["properties"]
    assert props["classification"]["type"] == "string"
    assert props["external_llm_allowed"]["type"] == "boolean"
    assert props["file"]["format"] == "binary"
    post = openapi_doc["paths"]["/documents"]["post"]
    assert "multipart/form-data" in post["requestBody"]["content"]
    # 上传可携带幂等键（写操作按需支持 Idempotency-Key，SPEC §5.1）
    param_names = [p.get("name") for p in (post.get("parameters") or [])]
    assert "Idempotency-Key" in param_names


def test_events_endpoint_is_sse(openapi_doc):
    events = openapi_doc["paths"]["/runs/{id}/events"]["get"]
    content = events["responses"]["200"]["content"]
    assert "text/event-stream" in content


def test_tbd_p0_not_frozen_in_schema(openapi_doc):
    """TBD-P0 仅以注解出现，不得在 schema 中静默填默认值（SPEC 引言、§0.6）。"""
    created = schema_ref(openapi_doc, "#/components/schemas/RunCreated")
    initial_state = created["properties"]["initial_state"]
    assert initial_state.get("x-tbd-p0") is True or "TBD-P0" in initial_state.get(
        "description", ""
    ), "initial_state 结构仍属 TBD-P0，须显式标注而非冻结具体字段"
