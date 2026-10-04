"""Offline candidate evidence checks, not Agent or supply-chain approval."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_LZMA, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "ops/check_candidate_integrity.py"
SPEC = importlib.util.spec_from_file_location("candidate_integrity", TOOL)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def candidate(tmp_path):
    project = tmp_path / "project"
    inputs = {}
    for relative in checker.PROJECT_INPUTS:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# synthetic input\n")
        inputs[relative] = digest(path.read_bytes())
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    wheel = wheelhouse / "demo_pkg-1.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "demo_pkg-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.0\n\n",
        )
    sha = digest(wheel.read_bytes())
    lock = tmp_path / "candidate.lock.txt"
    lock.write_text(f"# proposed only\ndemo-pkg==1.0 --hash=sha256:{sha}\n")
    data = {
        "status": "proposed",
        "approval": "pending",
        "candidate_lock_file": lock.name,
        "candidate_lock_sha256": digest(lock.read_bytes()),
        "project_input_sha256": inputs,
        "packages": [{"name": "demo-pkg", "version": "1.0", "wheel": wheel.name, "sha256": sha}],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data))
    return manifest, project, wheelhouse, data


def save(candidate):
    candidate[0].write_text(json.dumps(candidate[3]))


def check(candidate, *, wheels=True):
    return checker.check_candidate(candidate[0], candidate[1], candidate[2] if wheels else None)


def test_FR_AGENT_009_candidate_valid_bytes_and_pending_state(candidate):
    result = check(candidate)
    assert result == {
        "status": "consistent",
        "packages_checked": 1,
        "wheel_bytes_checked": True,
        "approval": "not_dependency_approval",
    }
    assert check(candidate, wheels=False)["wheel_bytes_checked"] is False


@pytest.mark.parametrize("field,value", [("status", "accepted"), ("approval", "approved")])
def test_FR_AGENT_009_candidate_never_accepts_relabelled_approval(candidate, field, value):
    candidate[3][field] = value
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="candidate_status"):
        check(candidate)


@pytest.mark.parametrize("field", ["candidate_lock_sha256", "project_input_sha256", "packages"])
def test_FR_AGENT_009_candidate_requires_evidence_fields(candidate, field):
    candidate[3].pop(field)
    save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate)


@pytest.mark.parametrize("replacement", ["", "bogus", "0" * 64])
def test_FR_AGENT_009_candidate_rejects_lock_digest_drift(candidate, replacement):
    candidate[3]["candidate_lock_sha256"] = replacement
    save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate)


@pytest.mark.parametrize(
    "line",
    [
        "--index-url https://private.invalid/secret",
        "demo-pkg==1.0",
        "demo-pkg>=1.0 --hash=sha256:" + "0" * 64,
        "demo-pkg==1.0; python_version>'3' --hash=sha256:" + "0" * 64,
        "demo-pkg @ https://private.invalid/secret",
    ],
)
def test_FR_AGENT_009_candidate_rejects_noncanonical_lock_directives(candidate, line):
    lock = candidate[0].parent / candidate[3]["candidate_lock_file"]
    lock.write_text(line + "\n")
    candidate[3]["candidate_lock_sha256"] = digest(lock.read_bytes())
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="lock_entry"):
        check(candidate)


@pytest.mark.parametrize("change", ["extra", "missing", "duplicate", "hash", "version"])
def test_FR_AGENT_009_candidate_requires_exact_lock_package_set(candidate, change):
    lock = candidate[0].parent / candidate[3]["candidate_lock_file"]
    text = lock.read_text()
    if change == "extra":
        text += "other==1.0 --hash=sha256:" + "0" * 64 + "\n"
    elif change == "missing":
        text = "# empty\n"
    elif change == "duplicate":
        text += text.replace("demo-pkg", "Demo_Pkg")
    elif change == "hash":
        text = text.replace(candidate[3]["packages"][0]["sha256"], "0" * 64)
    else:
        text = text.replace("==1.0", "==2.0")
    lock.write_text(text)
    candidate[3]["candidate_lock_sha256"] = digest(lock.read_bytes())
    save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate)


def test_FR_AGENT_009_candidate_rejects_normalized_manifest_duplicates(candidate):
    duplicate = dict(candidate[3]["packages"][0], name="Demo_Pkg")
    candidate[3]["packages"].append(duplicate)
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="duplicate_package"):
        check(candidate)


@pytest.mark.parametrize(
    "wheel",
    [
        "../secret.whl",
        "C:\\secret.whl",
        "/secret.whl",
        "demo.tar.gz",
        "other-1.0-py3-none-any.whl",
        "demo_pkg-2.0-py3-none-any.whl",
    ],
)
def test_FR_AGENT_009_candidate_rejects_unsafe_or_wrong_wheel_name(candidate, wheel):
    candidate[3]["packages"][0]["wheel"] = wheel
    save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate, wheels=False)


@pytest.mark.parametrize("path", ["../secret", "/secret", "api/../secret", "private.env"])
def test_FR_AGENT_009_candidate_restricts_input_paths(candidate, path):
    candidate[3]["project_input_sha256"][path] = "0" * 64
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="project_inputs"):
        check(candidate)


def test_FR_AGENT_009_candidate_rejects_input_missing_drift_and_symlink(candidate, tmp_path):
    path = candidate[1] / "api/pyproject.toml"
    path.write_text("changed")
    with pytest.raises(checker.IntegrityError, match="project_digest"):
        check(candidate)
    path.unlink()
    with pytest.raises(checker.IntegrityError):
        check(candidate)
    outside = tmp_path / "outside"
    outside.write_text("# synthetic input\n")
    path.symlink_to(outside)
    with pytest.raises(checker.IntegrityError, match="path_boundary"):
        check(candidate)


def test_FR_AGENT_009_candidate_text_hash_normalizes_crlf_only(candidate):
    for path in [
        candidate[0].parent / candidate[3]["candidate_lock_file"],
        candidate[1] / "api/pyproject.toml",
    ]:
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert check(candidate)["status"] == "consistent"


@pytest.mark.parametrize("problem", ["missing", "changed", "symlink", "metadata", "duplicate"])
def test_FR_AGENT_009_candidate_checks_wheel_bytes_and_identity(candidate, tmp_path, problem):
    row = candidate[3]["packages"][0]
    wheel = candidate[2] / row["wheel"]
    if problem == "missing":
        wheel.unlink()
    elif problem == "changed":
        wheel.write_bytes(b"corrupt")
    elif problem == "symlink":
        outside = tmp_path / "outside.whl"
        wheel.rename(outside)
        wheel.symlink_to(outside)
    else:
        with ZipFile(wheel, "w") as archive:
            archive.writestr("demo_pkg-1.0.dist-info/METADATA", "Name: other\nVersion: 1.0\n")
            if problem == "duplicate":
                archive.writestr("other-1.0.dist-info/METADATA", "Name: demo-pkg\nVersion: 1.0\n")
        row["sha256"] = digest(wheel.read_bytes())
        lock = candidate[0].parent / candidate[3]["candidate_lock_file"]
        lock.write_text(f"demo-pkg==1.0 --hash=sha256:{row['sha256']}\n")
        candidate[3]["candidate_lock_sha256"] = digest(lock.read_bytes())
        save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate)


@pytest.mark.parametrize("lock_name", ["../secret", "/secret", "C:\\secret", None])
def test_FR_AGENT_009_candidate_rejects_unsafe_or_missing_lock_name(candidate, lock_name):
    candidate[3]["candidate_lock_file"] = lock_name
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="filename_shape"):
        check(candidate)


def test_FR_AGENT_009_candidate_rejects_lock_symlink_escape(candidate, tmp_path):
    lock = candidate[0].parent / candidate[3]["candidate_lock_file"]
    outside = tmp_path.parent / (tmp_path.name + ".lock")
    outside.write_bytes(lock.read_bytes())
    try:
        lock.unlink()
        lock.symlink_to(outside)
        with pytest.raises(checker.IntegrityError, match="path_boundary"):
            check(candidate)
    finally:
        outside.unlink()


@pytest.mark.parametrize("rows", [[], {}, [None], [{"name": "demo-pkg"}]])
def test_FR_AGENT_009_candidate_rejects_malformed_package_rows(candidate, rows):
    candidate[3]["packages"] = rows
    save(candidate)
    with pytest.raises(checker.IntegrityError):
        check(candidate)


def test_FR_AGENT_009_candidate_requires_all_project_inputs(candidate):
    candidate[3]["project_input_sha256"].pop("worker/pyproject.toml")
    save(candidate)
    with pytest.raises(checker.IntegrityError, match="project_inputs"):
        check(candidate)


def test_FR_AGENT_009_candidate_cli_success_preserves_pending(candidate):
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--manifest",
            str(candidate[0]),
            "--project-root",
            str(candidate[1]),
            "--wheelhouse",
            str(candidate[2]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == check(candidate)
    assert json.loads(candidate[0].read_text())["approval"] == "pending"


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_FR_AGENT_009_candidate_rejects_non_json_constants(candidate, constant):
    text = json.dumps(candidate[3])[:-1] + ',"ignored":' + constant + "}"
    candidate[0].write_text(text)
    with pytest.raises(checker.IntegrityError, match="json_constant"):
        check(candidate)


def test_FR_AGENT_009_candidate_rejects_duplicate_json_keys(candidate):
    candidate[0].write_text('{"status":"proposed","status":"approved"}')
    with pytest.raises(checker.IntegrityError, match="duplicate_json_key"):
        check(candidate)


@pytest.fixture(params=[ZIP_DEFLATED, ZIP_BZIP2, ZIP_LZMA], ids=["deflate", "bzip2", "lzma"])
def compressed_candidate(candidate, request):
    wheel = candidate[2] / candidate[3]["packages"][0]["wheel"]
    with ZipFile(wheel, "w", compression=request.param) as archive:
        archive.writestr(
            "demo_pkg-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.0\n\n",
        )
    data = bytearray(wheel.read_bytes())
    name_length, extra_length = struct.unpack_from("<HH", data, 26)
    offset = 30 + name_length + extra_length
    # Corrupt codec headers, leaving the ZIP directory and identities intact.
    if request.param == ZIP_DEFLATED:
        data[offset] = 7  # Reserved DEFLATE block type.
    elif request.param == ZIP_BZIP2:
        data[offset] = 0  # Invalid bzip2 signature.
    else:
        data[offset + 4] = 255  # Invalid LZMA properties.
    return candidate, wheel, data


def sync_wheel_digest(candidate, wheel):
    row = candidate[3]["packages"][0]
    row["sha256"] = digest(wheel.read_bytes())
    lock = candidate[0].parent / candidate[3]["candidate_lock_file"]
    lock.write_text(f"demo-pkg==1.0 --hash=sha256:{row['sha256']}\n")
    candidate[3]["candidate_lock_sha256"] = digest(lock.read_bytes())
    save(candidate)


def test_FR_AGENT_009_candidate_accepts_valid_compressed_metadata(compressed_candidate):
    candidate, wheel, _ = compressed_candidate
    sync_wheel_digest(candidate, wheel)
    assert check(candidate)["status"] == "consistent"


def test_FR_AGENT_009_candidate_rejects_corrupt_compressed_metadata(compressed_candidate):
    candidate, wheel, corrupt_data = compressed_candidate
    wheel.write_bytes(corrupt_data)
    sync_wheel_digest(candidate, wheel)
    with pytest.raises(checker.IntegrityError, match="^unreadable_or_invalid_material$"):
        check(candidate)


def test_FR_AGENT_009_candidate_compression_cli_errors_are_redacted(compressed_candidate):
    candidate, wheel, corrupt_data = compressed_candidate
    wheel.write_bytes(corrupt_data)
    sync_wheel_digest(candidate, wheel)
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--manifest",
            str(candidate[0]),
            "--project-root",
            str(candidate[1]),
            "--wheelhouse",
            str(candidate[2]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "status": "invalid",
        "category": "unreadable_or_invalid_material",
    }


def test_FR_AGENT_009_candidate_cli_errors_are_redacted(candidate):
    candidate[0].write_text('{"secret":"DO_NOT_ECHO_ME",bad json}')
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--manifest",
            str(candidate[0]),
            "--project-root",
            str(candidate[1]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "invalid"
    assert "DO_NOT_ECHO_ME" not in result.stdout + result.stderr
    assert str(candidate[0]) not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "directory,count", [("", 111), ("linux-bookworm", 109), ("linux-ubuntu", 109)]
)
def test_FR_AGENT_009_candidate_versioned_material_is_consistent(directory, count):
    base = ROOT / "evidence/agent-m03/nd-agent-02-c" / directory
    result = checker.check_candidate(base / "candidate-manifest.json", ROOT)
    assert result["packages_checked"] == count
    assert result["approval"] == "not_dependency_approval"
