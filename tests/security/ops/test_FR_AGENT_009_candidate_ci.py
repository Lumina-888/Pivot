"""Candidate CI preparation boundaries; no network or Agent acceptance."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "ops/prepare_candidate_ci.py"
ENVIRONMENT = {
    "os_id": "ubuntu",
    "os_version": "24.04",
    "architecture": "x86_64",
    "libc": "glibc",
    "libc_version": "2.39",
    "python_version": "3.12.10",
    "python_implementation": "CPython",
    "pip_version": "25.0.1",
}


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "ops"))
    spec = importlib.util.spec_from_file_location("candidate_ci", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    inputs = {}
    for relative in (
        "api/pyproject.toml",
        "worker/pyproject.toml",
        "tests/contract/requirements.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# synthetic input\n")
        inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    base = root / "evidence/agent-m03/nd-agent-02-c"
    for directory in (base, base / "linux-ubuntu"):
        directory.mkdir(parents=True, exist_ok=True)
        lock = "demo-pkg==1.0 --hash=sha256:" + "a" * 64 + "\n"
        (directory / "candidate.lock.txt").write_text(lock)
        manifest = {
            "status": "proposed",
            "approval": "pending",
            "roots": ["demo-pkg==1.0"],
            "packages": [
                {
                    "name": "demo-pkg",
                    "version": "1.0",
                    "wheel": "demo_pkg-1.0-py3-none-any.whl",
                    "sha256": "a" * 64,
                }
            ],
            "candidate_lock_file": "candidate.lock.txt",
            "candidate_lock_sha256": hashlib.sha256(lock.encode()).hexdigest(),
            "project_input_sha256": inputs,
            "environment": {
                "sys_platform": "linux",
                "platform_machine": "x86_64",
                "python_full_version": "3.12.10",
            },
            "text_hash_normalization": "UTF-8 text with LF line endings",
        }
        (directory / "candidate-manifest.json").write_text(json.dumps(manifest))
    return root


def test_FR_AGENT_009_ci_preparation_exports_versions_not_windows_hashes(tool, project):
    trial = project / ".pi/artifacts/nd-agent-02-c/test-ci"
    result = tool.prepare_inputs(trial, project, ENVIRONMENT)
    assert result["approval"] == "pending"
    assert (trial / "roots.txt").read_text() == "demo-pkg==1.0\n"
    assert (trial / "versions-only.txt").read_text() == "demo-pkg==1.0\n"
    environment = json.loads((trial / "environment.json").read_text())
    assert environment["native"] == ENVIRONMENT
    assert environment["approval"] == "pending"


@pytest.mark.parametrize("field", list(ENVIRONMENT))
def test_FR_AGENT_009_ci_preparation_rejects_wrong_native_environment(
    tool, project, field
):
    trial = project / ".pi/artifacts/nd-agent-02-c/wrong-platform"
    environment = dict(ENVIRONMENT, **{field: "not-the-approved-platform"})
    with pytest.raises(tool.CandidateCIError, match="^native_environment$"):
        tool.prepare_inputs(trial, project, environment)
    assert not trial.exists()


@pytest.mark.parametrize("location", ["outside", "base", "symlink", "existing"])
def test_FR_AGENT_009_ci_preparation_restricts_fresh_output(
    tool, project, tmp_path, location
):
    base = project / ".pi/artifacts/nd-agent-02-c"
    base.mkdir(parents=True)
    trial = base / "trial"
    category = "trial_boundary"
    if location == "outside":
        trial = tmp_path / "outside"
    elif location == "base":
        trial = base
    elif location == "symlink":
        trial.symlink_to(tmp_path / "outside", target_is_directory=True)
    else:
        trial.mkdir()
        (trial / "keep.txt").write_text("existing evidence")
        category = "trial_exists"
    with pytest.raises(tool.CandidateCIError, match=f"^{category}$"):
        tool.prepare_inputs(trial, project, ENVIRONMENT)
    assert not (trial / "environment.json").exists()
    if location == "existing":
        assert (trial / "keep.txt").read_text() == "existing evidence"


@pytest.mark.parametrize(
    "roots",
    [
        [],
        ["--index-url https://private.invalid/secret"],
        ["demo-pkg @ https://private.invalid/secret"],
        ["unknown==1.0"],
        ["demo-pkg==2.0"],
        ["demo-pkg==1.0\n--extra-index-url https://private.invalid"],
    ],
)
def test_FR_AGENT_009_ci_preparation_rejects_unsafe_roots(tool, project, roots):
    manifest = project / "evidence/agent-m03/nd-agent-02-c/candidate-manifest.json"
    data = json.loads(manifest.read_text())
    data["roots"] = roots
    manifest.write_text(json.dumps(data))
    trial = project / ".pi/artifacts/nd-agent-02-c/unsafe-roots"
    with pytest.raises(tool.CandidateCIError, match="^candidate_roots$"):
        tool.prepare_inputs(trial, project, ENVIRONMENT)
    assert not trial.exists()


@pytest.fixture
def resolved(tool, project):
    trial = project / ".pi/artifacts/nd-agent-02-c/native-report"
    tool.prepare_inputs(trial, project, ENVIRONMENT)
    report = {
        "version": "1",
        "pip_version": "25.0.1",
        "environment": {
            "sys_platform": "linux",
            "platform_machine": "x86_64",
            "python_full_version": "3.12.10",
        },
        "install": [
            {
                "metadata": {"name": "demo-pkg", "version": "1.0"},
                "is_yanked": False,
                "download_info": {
                    "url": "https://files.pythonhosted.org/packages/demo_pkg-1.0-py3-none-any.whl",
                    "archive_info": {"hashes": {"sha256": "a" * 64}},
                },
            }
        ],
    }
    (trial / "resolve-report.json").write_text(json.dumps(report))
    return trial, report


def test_FR_AGENT_009_ci_report_generates_independent_pending_material(
    tool, project, resolved
):
    trial, _ = resolved
    result = tool.write_native_candidate(trial, project)
    assert result == {
        "status": "consistent",
        "packages_checked": 1,
        "wheel_bytes_checked": False,
        "approval": "not_dependency_approval",
    }
    manifest = json.loads((trial / "candidate-manifest.json").read_text())
    assert manifest["status"] == "proposed"
    assert manifest["approval"] == "pending"
    assert manifest["environment"]["sys_platform"] == "linux"
    assert (
        manifest["resolve_report_sha256"]
        == hashlib.sha256((trial / "resolve-report.json").read_bytes()).hexdigest()
    )
    lock = (trial / "candidate-ci-py312.lock.txt").read_text()
    assert lock == "demo-pkg==1.0 --hash=sha256:" + "a" * 64 + "\n"
    assert (trial / "wrong-hash.lock.txt").read_text() == (
        "demo-pkg==1.0 --hash=sha256:" + "0" * 64 + "\n"
    )


@pytest.mark.parametrize(
    "problem",
    [
        "platform",
        "architecture",
        "python",
        "pip",
        "report-version",
        "empty",
        "extra",
        "duplicate",
        "version",
        "hash",
        "wheel",
        "http",
        "host",
        "credentials",
        "port",
        "query",
        "fragment",
        "yanked",
        "yanked-type",
    ],
)
def test_FR_AGENT_009_ci_report_rejects_drift_before_outputs(
    tool, project, resolved, problem
):
    trial, report = resolved
    item = report["install"][0]
    if problem in {"platform", "architecture", "python"}:
        field = {
            "platform": "sys_platform",
            "architecture": "platform_machine",
            "python": "python_full_version",
        }[problem]
        report["environment"][field] = "wrong"
    elif problem == "pip":
        report["pip_version"] = "wrong"
    elif problem == "report-version":
        report["version"] = "wrong"
    elif problem == "empty":
        report["install"] = []
    elif problem == "extra":
        extra = json.loads(json.dumps(item))
        extra["metadata"]["name"] = "other"
        report["install"].append(extra)
    elif problem == "duplicate":
        report["install"].append(item)
    elif problem == "version":
        item["metadata"]["version"] = "2.0"
    elif problem == "hash":
        item["download_info"]["archive_info"]["hashes"]["sha256"] = "b" * 64
    elif problem.startswith("yanked"):
        item["is_yanked"] = True if problem == "yanked" else 0
    else:
        prefixes = {
            "wheel": "https://files.pythonhosted.org/packages/other-1.0-py3-none-any.whl",
            "http": "http://files.pythonhosted.org/packages/demo_pkg-1.0-py3-none-any.whl",
            "host": "https://private.invalid/packages/demo_pkg-1.0-py3-none-any.whl",
            "credentials": "https://secret@files.pythonhosted.org/demo_pkg-1.0-py3-none-any.whl",
            "port": "https://files.pythonhosted.org:444/demo_pkg-1.0-py3-none-any.whl",
            "query": "https://files.pythonhosted.org/demo_pkg-1.0-py3-none-any.whl?secret=fixture",
            "fragment": "https://files.pythonhosted.org/demo_pkg-1.0-py3-none-any.whl#secret",
        }
        item["download_info"]["url"] = prefixes[problem]
    (trial / "resolve-report.json").write_text(json.dumps(report))
    with pytest.raises(tool.CandidateCIError, match="^native_report$"):
        tool.write_native_candidate(trial, project)
    assert not (trial / "candidate-manifest.json").exists()
    assert not (trial / "candidate-ci-py312.lock.txt").exists()


@pytest.mark.parametrize(
    "filename",
    ["candidate-manifest.json", "candidate-ci-py312.lock.txt", "wrong-hash.lock.txt"],
)
def test_FR_AGENT_009_ci_report_never_overwrites_evidence(
    tool, project, resolved, filename
):
    trial, _ = resolved
    (trial / filename).write_text("keep evidence")
    with pytest.raises(tool.CandidateCIError, match="^trial_outputs$"):
        tool.write_native_candidate(trial, project)
    assert (trial / filename).read_text() == "keep evidence"


def test_FR_AGENT_009_ci_report_rejects_source_change_after_preparation(
    tool, project, resolved
):
    trial, _ = resolved
    source = project / "evidence/agent-m03/nd-agent-02-c/candidate-manifest.json"
    source.write_text(source.read_text() + "\n")
    with pytest.raises(tool.CandidateCIError, match="^source_drift$"):
        tool.write_native_candidate(trial, project)
    assert not (trial / "candidate-manifest.json").exists()


@pytest.mark.parametrize("filename", ["resolve-report.json", "environment.json"])
def test_FR_AGENT_009_ci_report_rejects_symlink_escape(
    tool, project, resolved, tmp_path, filename
):
    trial, _ = resolved
    path = trial / filename
    outside = tmp_path / "private.json"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(tool.CandidateCIError, match="^trial_boundary$"):
        tool.write_native_candidate(trial, project)
    assert not (trial / "candidate-manifest.json").exists()


def test_FR_AGENT_009_ci_preparation_cli_fails_closed_without_leaking_paths():
    # The candidate workflow redirects TMPDIR into the allowed trial tree; keep this
    # fixture outside the repository so it remains an actual boundary violation.
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as outside:
        trial = Path(outside) / "DO_NOT_ECHO_PRIVATE_PATH"
        result = subprocess.run(
            [sys.executable, str(TOOL), "--stage", "prepare", "--trial", str(trial)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert result.stderr == ""
        response = json.loads(result.stdout)
        assert response["status"] == "invalid"
        assert response["category"] in {"native_environment", "trial_boundary"}
        assert str(trial) not in result.stdout
        assert not trial.exists()


@pytest.fixture
def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/candidate-ubuntu.yml").read_text())


def test_FR_AGENT_009_ci_workflow_is_manual_read_only_and_pinned(workflow):
    assert set(workflow["on"]) == {"workflow_dispatch"}
    confirmation = workflow["on"]["workflow_dispatch"]["inputs"][
        "confirm_candidate_only"
    ]
    assert confirmation == {
        "description": "Candidate validation only; no dependency approval",
        "required": True,
        "type": "boolean",
        "default": False,
    }
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["candidate-validation"]
    assert job["if"] == "${{ inputs.confirm_candidate_only == true }}"
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["timeout-minutes"] == 40
    actions = [step for step in job["steps"] if "uses" in step]
    assert len(actions) == 3
    assert all(
        re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"]) for step in actions
    )
    assert actions[0]["with"]["persist-credentials"] is False
    assert actions[1]["with"]["python-version"] == "3.12.10"
    assert "cache" not in actions[1]["with"]


def test_FR_AGENT_009_ci_workflow_installs_isolated_hashes_without_live_services(
    workflow,
):
    job = workflow["jobs"]["candidate-validation"]
    body = "\n".join(step.get("run", "") for step in job["steps"])
    assert job["env"]["LANGCHAIN_TRACING_V2"] == "false"
    assert job["env"]["LANGSMITH_TRACING"] == "false"
    for required in (
        "--stage prepare",
        "--stage resolved",
        "--dry-run",
        "--ignore-installed",
        "--report",
        "--require-hashes",
        "--no-index",
        "--only-binary=:all:",
        "pip check",
        "test_dependency_probe.py",
        "test_budget_mapping_probe.py",
        "ops/run_grouped_tests.py --skip-web",
        "for name in verify rebuild",
        "THESE PACKAGES DO NOT MATCH THE HASHES",
    ):
        assert required in body
    for forbidden in (
        "--upgrade",
        "pip install -e",
        "docker compose",
        "docker build",
        "uvicorn",
        "secrets.",
        "continue-on-error",
    ):
        assert forbidden not in json.dumps(workflow)
    for step in job["steps"]:
        if "run" in step:
            assert step.get("shell") == "bash"
            result = subprocess.run(
                ["bash", "-n"],
                input=step["run"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr


def test_FR_AGENT_009_ci_workflow_artifacts_exclude_environments_and_wheels(workflow):
    upload = workflow["jobs"]["candidate-validation"]["steps"][-1]
    assert upload["if"] == "${{ always() }}"
    # upload-artifact v4 excludes every file beneath the hidden .pi directory by default.
    assert upload["with"].get("include-hidden-files") is True
    paths = upload["with"]["path"].splitlines()
    assert paths and all(
        path.startswith("${{ env.PIVOT_CANDIDATE_TRIAL }}/") for path in paths
    )
    assert all(
        path.rsplit("/", 1)[1]
        in {
            "*.json",
            "*.log",
            "*.txt",
        }
        for path in paths
    )
    assert "**" not in upload["with"]["path"]
    assert upload["with"]["retention-days"] == 7


@pytest.mark.parametrize(
    "payload,category",
    [
        ('{"secret":"DO_NOT_ECHO",broken}', "unreadable_material"),
        ('{"version":"1","version":"secret"}', "duplicate_json_key"),
        ('{"unused":NaN}', "json_constant"),
        ('{"unused":Infinity}', "json_constant"),
        ('{"unused":-Infinity}', "json_constant"),
        ("[]", "object_shape"),
    ],
)
def test_FR_AGENT_009_ci_report_rejects_invalid_json(
    tool, project, resolved, payload, category
):
    trial, _ = resolved
    (trial / "resolve-report.json").write_text(payload)
    with pytest.raises(tool.CandidateCIError, match=f"^{category}$"):
        tool.write_native_candidate(trial, project)
    assert not (trial / "candidate-manifest.json").exists()


@pytest.mark.parametrize("value", [None, [], 12, {}])
def test_FR_AGENT_009_ci_report_rejects_nonstring_url(tool, project, resolved, value):
    trial, report = resolved
    report["install"][0]["download_info"]["url"] = value
    (trial / "resolve-report.json").write_text(json.dumps(report))
    with pytest.raises(tool.CandidateCIError, match="^native_report$"):
        tool.write_native_candidate(trial, project)
    assert not (trial / "candidate-manifest.json").exists()


def test_FR_AGENT_009_ci_preparation_rejects_source_symlink_escape(
    tool, project, tmp_path
):
    source = project / "evidence/agent-m03/nd-agent-02-c/candidate-manifest.json"
    outside = tmp_path / "private.json"
    source.rename(outside)
    source.symlink_to(outside)
    trial = project / ".pi/artifacts/nd-agent-02-c/bad-source"
    with pytest.raises(tool.CandidateCIError, match="^source_boundary$"):
        tool.prepare_inputs(trial, project, ENVIRONMENT)
    assert not trial.exists()


def test_FR_AGENT_009_ci_workflow_bootstrap_matches_pending_candidate():
    directory = ROOT / "evidence/agent-m03/nd-agent-02-c"
    source = json.loads(
        (directory / "linux-ubuntu/candidate-manifest.json").read_text()
    )
    row = next(
        package for package in source["packages"] if package["name"] == "packaging"
    )
    lines = (directory / "ci-bootstrap.lock.txt").read_text().splitlines()
    entries = [line for line in lines if line and not line.startswith("#")]
    assert entries == [f"packaging=={row['version']} --hash=sha256:{row['sha256']}"]
    assert source["status"] == "proposed" and source["approval"] == "pending"
