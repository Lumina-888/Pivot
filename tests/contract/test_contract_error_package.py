"""契约测试：统一错误包（SPEC §5.1、附录 B.1）。

验证：
- components/schemas/Error 必填字段与类型；
- SPEC §5.1 错误包示例可校验；
- code 枚举覆盖 SPEC 附录 B.1 全部错误码且无重复；
- 每个 operation 的错误响应统一引用 Error（default 响应）。
"""

import pytest

from conftest import schema_ref, validate

# SPEC 附录 B.1 错误码全集（contract-v0.1 冻结枚举的来源）
SPEC_ERROR_CODES = [
    "AUTH_INVALID_CREDENTIALS",
    "AUTH_FORBIDDEN",
    "RESOURCE_NOT_FOUND",
    "RESOURCE_FORBIDDEN",
    "IDEMPOTENCY_CONFLICT",
    "UNSUPPORTED_EXTENSION",
    "INVALID_FILE_SIGNATURE",
    "UNSUPPORTED_SCAN_PDF",
    "ENCRYPTED_FILE",
    "CORRUPTED_FILE",
    "RESOURCE_LIMIT",
    "EXTERNAL_LLM_NOT_ALLOWED",
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_TEMPORARY_ERROR",
    "RUN_CANCELLED",
    "RUN_TIMEOUT",
    "VERIFICATION_UNAVAILABLE",
    "EXPORT_EXPIRED",
]

# SPEC §5.1 统一错误包示例
ERROR_EXAMPLE = {
    "code": "RESOURCE_FORBIDDEN",
    "message": "无权访问该资源",
    "request_id": "req_001",
    "details": {},
    "retryable": False,
}


def test_error_schema_required_fields_and_types(openapi_doc):
    error = schema_ref(openapi_doc, "#/components/schemas/Error")
    assert set(error.get("required", [])) == {"code", "message", "request_id"}
    props = error["properties"]
    assert props["code"]["type"] == "string"
    assert props["message"]["type"] == "string"
    assert props["request_id"]["type"] == "string"
    assert props["retryable"]["type"] == "boolean"
    assert props["details"]["type"] == "object"


def test_error_example_from_spec_validates(openapi_doc):
    error = schema_ref(openapi_doc, "#/components/schemas/Error")
    validate(ERROR_EXAMPLE, error)


def test_error_code_enum_covers_spec_appendix_b1(openapi_doc):
    error = schema_ref(openapi_doc, "#/components/schemas/Error")
    codes = error["properties"]["code"]["enum"]
    assert len(codes) == len(set(codes)), "错误码枚举不得重复"
    for expected in SPEC_ERROR_CODES:
        assert expected in codes, f"附录 B.1 错误码缺失：{expected}"


def test_error_codes_are_non_empty_upper_snake(openapi_doc):
    error = schema_ref(openapi_doc, "#/components/schemas/Error")
    for code in error["properties"]["code"]["enum"]:
        assert code.isupper() and "_" in code, f"错误码应使用大写下划线命名：{code}"


def test_every_operation_has_unified_error_response(openapi_doc):
    for path, path_item in openapi_doc["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "patch", "put", "delete"}:
                continue
            assert "default" in operation.get("responses", {}), (
                f"{method.upper()} {path} 缺少统一错误 default 响应"
            )
            default = operation["responses"]["default"]
            error_ref = default["content"]["application/json"]["schema"]["$ref"]
            assert error_ref == "#/components/schemas/Error", (
                f"{method.upper()} {path} default 响应必须引用统一 Error schema"
            )


def test_error_never_leaks_sensitive_content(openapi_doc):
    """错误 schema 不得携带 stack/secret/internal 等字段（SPEC §5.1、§8.4）。"""
    error = schema_ref(openapi_doc, "#/components/schemas/Error")
    leaked = {"stack", "stacktrace", "secret", "token", "password", "sql", "traceback"}
    assert not leaked.intersection(error["properties"]), "错误包不得包含敏感字段"
