"""M00 契约验证测试共用 Fixture。

仓库根以本文件位置推算：tests/contract/conftest.py -> 仓库根（parents[2]）。
契约文件缺失时显式 pytest.fail，保证 Red 阶段能表达失败原因（SPEC §0.4）。
"""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "spec" / "contracts"


def load_yaml(path: Path):
    if not path.exists():
        pytest.fail(f"契约文件缺失（Red）：{path.relative_to(REPO_ROOT)}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    if not path.exists():
        pytest.fail(f"契约文件缺失（Red）：{path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def openapi_doc():
    return load_yaml(CONTRACTS_DIR / "openapi.yaml")


@pytest.fixture(scope="session")
def sse_schema():
    return load_json(CONTRACTS_DIR / "sse.schema.json")


@pytest.fixture(scope="session")
def worker_schema():
    return load_json(CONTRACTS_DIR / "worker.schema.json")


def validate(instance, schema):
    """按 schema 声明版本校验实例；未声明时按 Draft7。"""
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    return jsonschema.validate(instance, schema, cls=validator_cls)


def _dereference(schema, root_document):
    """递归解引用 '#/components/schemas/*' 本地 $ref（仅本文件内引用）。

    用于把从 openapi.yaml 摘出的子组件展开为自洽 schema 后单独校验。
    """
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            name = ref.rsplit("/", 1)[1]
            return _dereference(root_document["components"]["schemas"][name], root_document)
        return {k: _dereference(v, root_document) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_dereference(item, root_document) for item in schema]
    return schema


def validate_against_root(instance, schema, root_document):
    """校验 OpenAPI 内抽取出的子 schema：先解引用本地 $ref 再按 Draft7 校验。"""
    expanded = _dereference(schema, root_document)
    return validate(instance, expanded)


def schema_ref(resolver_root: dict, ref: str):
    """解析 OpenAPI 组件内 $ref（仅支持本文件内 #/components/schemas/*）。"""
    if not ref.startswith("#/components/schemas/"):
        raise ValueError(f"不支持的 $ref：{ref}")
    name = ref.rsplit("/", 1)[1]
    return resolver_root["components"]["schemas"][name]
