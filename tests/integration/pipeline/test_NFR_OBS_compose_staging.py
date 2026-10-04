"""dev-staging Compose overlay. Not GATE-P0-007/008 verified and not started by CI."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_BASE = _ROOT / "docker-compose.yml"
_OVERLAY = _ROOT / "docker-compose.staging.yml"
_NGINX = _ROOT / "ops" / "nginx" / "staging.conf"
_ENV_EXAMPLE = _ROOT / "ops" / "compose.staging.env.example"
_RUNBOOK = _ROOT / "ops" / "runbook-dev-staging.md"
_UNIT = _ROOT / "ops" / "pivot-staging.service"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-staging.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_INTENT = _ROOT / "ops" / "compose-intent.md"
_GITIGNORE = _ROOT / ".gitignore"
_CHANGE = _ROOT / "progress" / "changes" / "20260914-M11-compose-staging.md"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"

_NGINX_IMAGE = "nginx:1.26.3-alpine"
_APP_SERVICES = ("postgres", "minio", "qdrant", "redis", "api", "web", "worker", "nginx")
_DATASTORES = ("postgres", "minio", "qdrant", "redis")
_DATASTORE_PORTS = ("5432", "9000", "9001", "6333", "6379", "8000", "3000", "8001")
_VENDOR_MARKERS = (
    "siliconflow",
    "deepseek.com",
    "mineru.net",
    "opendatalab",
    "openai.com",
    "api.xiaomimimo",
    "mimo-v2.5",
    "sk-",
)
_SELF_HOST_MARKERS = (
    "mineru",
    "ollama",
    "vllm",
    "nvidia",
    "gpu",
    "langfuse",
    "litellm",
)


def _service_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    in_services = False
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if not in_services:
            continue
        if (
            line
            and not line[:1].isspace()
            and line.rstrip().endswith(":")
            and not line.startswith("#")
        ):
            break
        stripped = line.strip()
        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and stripped.endswith(":")
            and not stripped.startswith("#")
        ):
            current = stripped[:-1]
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


def _reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _parse_memory_mib(value: str) -> int:
    raw = value.strip().strip('"').strip("'").upper()
    if raw.endswith("GI") or raw.endswith("GIB"):
        return int(float(raw[: raw.index("G")]) * 1024)
    if raw.endswith("G"):
        return int(float(raw[:-1]) * 1024)
    if raw.endswith("MI") or raw.endswith("MIB"):
        return int(float(raw[: raw.index("M")]))
    if raw.endswith("M"):
        return int(float(raw[:-1]))
    raise AssertionError(f"unsupported memory value {value!r}")


def _limit_field(body: str, field: str) -> str:
    in_limits = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("limits:"):
            in_limits = True
            continue
        if in_limits and (stripped.startswith("reservations:") or stripped.startswith("limits:")):
            if stripped.startswith("reservations:"):
                break
        if in_limits and stripped.startswith(f"{field}:"):
            return stripped.split(":", 1)[1].strip()
    raise AssertionError(f"missing deploy.resources.limits.{field}")


def _example_assignment(text: str, key: str) -> str | None:
    prefix = f"{key}="
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :]
    return None


def test_NFR_OBS_compose_staging_overlay_pins_nginx_and_healthcheck():
    assert _OVERLAY.is_file(), "ND-STG-04 must add docker-compose.staging.yml"
    text = _OVERLAY.read_text(encoding="utf-8")
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("image:"):
            assert ":latest" not in stripped
    services = _service_blocks(text)
    assert "nginx" in services
    body = services["nginx"]
    assert "profiles:" in body
    assert "app" in body
    assert _NGINX_IMAGE in body
    assert "healthcheck:" in body
    assert "depends_on:" in body
    assert "web:" in body
    assert "service_healthy" in body
    assert "restart:" in body
    assert "unless-stopped" in body
    assert "limits:" in body
    assert "reservations:" in body
    assert "4C8G" not in text
    assert "4c8g" not in text.lower()
    base = _BASE.read_text(encoding="utf-8")
    assert "nginx" not in _service_blocks(base)


def test_NFR_OBS_compose_staging_binds_http_loopback_by_default():
    text = _OVERLAY.read_text(encoding="utf-8")
    nginx = _service_blocks(text)["nginx"]
    assert "${PIVOT_STAGING_HTTP_BIND:-127.0.0.1}:80:80" in nginx
    assert "0.0.0.0" not in nginx
    assert re.search(r":443:", nginx) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(example, "PIVOT_STAGING_HTTP_BIND") == "127.0.0.1"
    assert _example_assignment(example, "PIVOT_API_ORIGIN") == "http://api:8000"


def test_NFR_OBS_compose_staging_does_not_publish_datastore_ports():
    overlay = _OVERLAY.read_text(encoding="utf-8")
    services = _service_blocks(overlay)
    for name in _DATASTORES:
        assert name in services
        body = services[name]
        assert "ports:" not in body
        for port in _DATASTORE_PORTS:
            assert f"{port}:" not in body
            assert f":{port}" not in body
    for name in ("api", "web", "worker"):
        body = services[name]
        assert "ports:" not in body
    nginx = services["nginx"]
    assert "80:80" in nginx
    for port in _DATASTORE_PORTS:
        assert port not in nginx


def test_NFR_OBS_compose_staging_nginx_proxies_web_only():
    conf = _NGINX.read_text(encoding="utf-8")
    assert "listen 80" in conf
    assert "listen 443" not in conf
    assert "proxy_pass http://web:3000" in conf
    lowered = conf.lower()
    for marker in ("postgres", "minio", "qdrant", "redis", "6333", "5432", "6379", "9000"):
        assert marker not in lowered
    assert "mineru" not in lowered
    assert "proxy_buffering off" in lowered


def test_NFR_OBS_compose_staging_resource_limits_fit_8gib():
    overlay = _OVERLAY.read_text(encoding="utf-8")
    services = _service_blocks(overlay)
    memory = 0
    cpus = 0.0
    for name in _APP_SERVICES:
        assert name in services, f"staging overlay missing {name}"
        body = services[name]
        assert "restart:" in body
        assert "unless-stopped" in body
        assert "reservations:" in body
        memory += _parse_memory_mib(_limit_field(body, "memory"))
        cpus += float(_limit_field(body, "cpus").strip('"'))
    assert memory <= 6144, f"staging memory limits {memory}MiB leave too little OS headroom on 8GiB"
    assert memory >= 4096, f"staging memory limits {memory}MiB look incomplete"
    assert cpus <= 4.0, f"staging cpu limits {cpus} exceed a 4C host"
    assert "4C8G" not in overlay
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "fixture" in evidence.lower() or "不是冻结" in evidence
    assert "TBD-P0" in evidence


def test_NFR_OBS_compose_staging_does_not_self_host_models():
    overlay = _OVERLAY.read_text(encoding="utf-8").lower()
    nginx = _NGINX.read_text(encoding="utf-8").lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8").lower()
    for text in (overlay, nginx):
        for marker in _SELF_HOST_MARKERS:
            assert marker not in text
    for marker in _VENDOR_MARKERS:
        assert marker not in overlay
        assert marker not in nginx
        assert marker not in example
    services = _service_blocks(_OVERLAY.read_text(encoding="utf-8"))
    assert set(services) <= set(_APP_SERVICES) | {"logging"}
    assert "nginx" in services
    intent = _INTENT.read_text(encoding="utf-8")
    assert "MinerU" in intent or "mineru" in intent.lower()
    assert "不自建" in intent or "外部" in intent


def test_NFR_OBS_compose_staging_env_is_gitignored():
    private_paths = (".env", "ops/compose.staging.env")
    git = ["git", "-C", str(_ROOT), "-c", f"core.excludesFile={os.devnull}"]
    tracked = subprocess.run(
        [*git, "ls-files", "--cached", "-z", "--", *private_paths],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert not tracked.stdout, "private environment configuration is in the Git index"
    ignored = subprocess.run(
        [*git, "check-ignore", "--no-index", "--verbose", "-z", "--stdin"],
        input="\0".join(private_paths) + "\0",
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert ignored.returncode in (0, 1), "Git ignore-rule query failed"
    assert ignored.returncode == 0, (
        "private environment paths must match repository .gitignore"
    )
    fields = ignored.stdout.split("\0")
    assert fields[-1] == "" and len(fields) == 4 * len(private_paths) + 1, (
        "private environment paths must match repository .gitignore"
    )
    for index, relative in enumerate(private_paths):
        source, _, pattern, path = fields[index * 4 : index * 4 + 4]
        assert source == _GITIGNORE.relative_to(_ROOT).as_posix(), (
            "private environment paths must match repository .gitignore"
        )
        assert path == relative
        assert not pattern.startswith("!"), "private environment path is explicitly unignored"
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "TBD-P0" in example
    assert "PIVOT_TOKEN_SECRET=" in example
    assert "PIVOT_EMBEDDING=" in example
    assert _example_assignment(example, "PIVOT_EMBEDDING") == "hash"
    assert _example_assignment(example, "PIVOT_LLM") == "local"
    assert _example_assignment(example, "PIVOT_PARSER") == "local"


@pytest.fixture
def private_env_repo(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("/.env\n/ops/compose.staging.env\n", encoding="utf-8")
    (tmp_path / "ops").mkdir()
    monkeypatch.setattr(f"{__name__}._ROOT", tmp_path)
    monkeypatch.setattr(f"{__name__}._GITIGNORE", gitignore)
    return tmp_path


@pytest.mark.parametrize("present", [False, True])
def test_NFR_SEC_014_private_env_local_files_are_allowed(private_env_repo, present):
    if present:
        for relative in (".env", "ops/compose.staging.env"):
            (private_env_repo / relative).write_text("fixture_only=true\n", encoding="utf-8")
    test_NFR_OBS_compose_staging_env_is_gitignored()


@pytest.mark.parametrize("relative", [".env", "ops/compose.staging.env"])
def test_NFR_SEC_014_private_env_force_staged_is_rejected(private_env_repo, relative):
    (private_env_repo / relative).write_text("fixture_only=true\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(private_env_repo), "add", "--force", "--", relative],
        check=True,
        capture_output=True,
    )
    with pytest.raises(AssertionError, match="in the Git index"):
        test_NFR_OBS_compose_staging_env_is_gitignored()


@pytest.mark.parametrize("relative", [".env", "ops/compose.staging.env"])
def test_NFR_SEC_014_private_env_missing_rule_is_rejected(private_env_repo, relative):
    other = "ops/compose.staging.env" if relative == ".env" else ".env"
    (private_env_repo / ".gitignore").write_text(f"/{other}\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must match repository"):
        test_NFR_OBS_compose_staging_env_is_gitignored()


@pytest.mark.parametrize("exclude_source", ["comment", "local", "global"])
def test_NFR_SEC_014_private_env_non_repo_rules_are_rejected(private_env_repo, exclude_source):
    (private_env_repo / ".gitignore").write_text(
        "# .env and *.env must be ignored\n", encoding="utf-8"
    )
    if exclude_source == "local":
        (private_env_repo / ".git" / "info" / "exclude").write_text(
            "/.env\n/ops/compose.staging.env\n", encoding="utf-8"
        )
    elif exclude_source == "global":
        excludes = private_env_repo / "global-ignore"
        excludes.write_text("/.env\n/ops/compose.staging.env\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(private_env_repo), "config", "core.excludesFile", str(excludes)],
            check=True,
            capture_output=True,
        )
    with pytest.raises(AssertionError, match="must match repository"):
        test_NFR_OBS_compose_staging_env_is_gitignored()


def test_NFR_OBS_compose_staging_env_example_has_no_vendor_secrets():
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    lowered = example.lower()
    for marker in _VENDOR_MARKERS:
        assert marker not in lowered
    assert "https://" not in lowered
    assert re.search(r"PIVOT_EMBEDDING_API_KEY=\S+", example) is None
    assert re.search(r"PIVOT_LLM_API_KEY=\S+", example) is None
    assert re.search(r"PIVOT_PARSER_TOKEN=\S+", example) is None
    assert "do not commit" in lowered or "不" in example


def test_NFR_OBS_compose_staging_runbook_lists_owner_prereqs():
    runbook = _RUNBOOK.read_text(encoding="utf-8")
    for needle in ("SSH", "安全组", "磁盘", "域名"):
        assert needle in runbook
    assert "22" in runbook
    assert "80" in runbook
    assert "docker-compose.staging.yml" in runbook
    assert "GATE-P0-007" in runbook or "GATE-P0-008" in runbook
    assert "unverified" in runbook.lower()
    assert "不" in runbook
    unit = _UNIT.read_text(encoding="utf-8")
    assert "docker compose" in unit.lower() or "docker-compose" in unit.lower()
    assert "docker-compose.staging.yml" in unit
    assert "sk-" not in unit.lower()
    assert "siliconflow" not in unit.lower()


def test_NFR_OBS_ci_does_not_apply_staging_compose():
    workflow = _WORKFLOW.read_text(encoding="utf-8").lower()
    grouped = _GROUPED.read_text(encoding="utf-8").lower()
    intent = _INTENT.read_text(encoding="utf-8")
    for text in (workflow, grouped):
        assert "docker compose up" not in text
        assert "docker build" not in text
        assert "docker-compose.staging.yml" not in text
    assert "CI" in intent
    assert "staging" in intent.lower() or "overlay" in intent.lower()
    assert "不得" in intent or "不启动" in intent or "不调用" in intent


def test_NFR_OBS_compose_staging_nginx_when_running():
    require = os.environ.get("PIVOT_REQUIRE_COMPOSE_STAGING") == "1"
    if not _reachable(80):
        if require:
            pytest.fail("compose staging nginx is not reachable on 127.0.0.1:80")
        pytest.skip("compose staging nginx not running on 127.0.0.1:80")
    try:
        with urllib.request.urlopen("http://127.0.0.1/login", timeout=1) as response:
            status = response.status
    except (urllib.error.URLError, TimeoutError) as exc:
        if require:
            pytest.fail(f"compose staging nginx /login failed: {exc}")
        pytest.skip(f"compose staging nginx /login not ready: {exc}")
    assert status == 200


def test_NFR_CAP_006_not_frozen_by_staging_limits():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    change = _CHANGE.read_text(encoding="utf-8")
    for text in (evidence, change):
        assert "NFR-CAP-006" in text or "4C8G" in text or "8GiB" in text or "8G" in text
        assert "TBD-P0" in text
        assert "不是" in text or "不冻" in text
    overlay = _OVERLAY.read_text(encoding="utf-8")
    assert "4C8G" not in overlay
    assert "verified" in overlay.lower()
    assert "not gate-p0-007/008 verified" in overlay.lower()


def test_GATE_P0_007_not_verified_by_staging_compose():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-007" in evidence
    assert "unverified" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-007" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_GATE_P0_008_not_verified_by_staging_compose():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "SSH" in evidence or "安全组" in evidence or "未" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
