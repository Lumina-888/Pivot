#!/usr/bin/env python3
"""Prepare native Ubuntu candidate CI evidence, never publish or approve dependencies."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from urllib.parse import unquote, urlsplit

from check_candidate_integrity import IntegrityError, check_candidate
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("evidence/agent-m03/nd-agent-02-c")
NATIVE = {
    "os_id": "ubuntu",
    "os_version": "24.04",
    "architecture": "x86_64",
    "libc": "glibc",
    "libc_version": "2.39",
    "python_version": "3.12.10",
    "python_implementation": "CPython",
    "pip_version": "25.0.1",
}


class CandidateCIError(ValueError):
    """Redacted failure category; never expose supplied content or local paths."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise CandidateCIError(category)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise CandidateCIError("json_constant")


def read_object(path: Path) -> dict:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except CandidateCIError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise CandidateCIError("unreadable_material") from None
    if not isinstance(data, dict):
        raise CandidateCIError("object_shape")
    return data


def source_material(project_root: Path) -> tuple[dict, dict]:
    manifests = []
    for directory in (SOURCE, SOURCE / "linux-ubuntu"):
        path = project_root / directory / "candidate-manifest.json"
        require(
            path.resolve().is_relative_to(project_root.resolve()), "source_boundary"
        )
        check_candidate(path, project_root)
        manifests.append(read_object(path))
    return manifests[0], manifests[1]


def source_digests(project_root: Path) -> dict:
    return {
        directory.as_posix(): hashlib.sha256(
            (project_root / directory / "candidate-manifest.json").read_bytes()
        ).hexdigest()
        for directory in (SOURCE, SOURCE / "linux-ubuntu")
    }


def trial_path(trial: Path, project_root: Path) -> Path:
    base = (project_root / ".pi/artifacts/nd-agent-02-c").resolve()
    require(base.is_relative_to(project_root.resolve()), "trial_boundary")
    path = trial.resolve()
    require(path != base and path.is_relative_to(base), "trial_boundary")
    return path


def prepare_inputs(trial: Path, project_root: Path, environment: dict) -> dict:
    """Export constraints to a fresh trial; environment is explicit for controlled Fixtures."""
    require(environment == NATIVE, "native_environment")
    trial = trial_path(trial, project_root)
    windows, _ubuntu = source_material(project_root)
    constraints = "".join(
        f"{canonicalize_name(row['name'])}=={row['version']}\n"
        for row in windows["packages"]
    )
    roots = windows.get("roots")
    if not isinstance(roots, list) or not roots:
        raise CandidateCIError("candidate_roots")
    versions = {
        canonicalize_name(row["name"]): row["version"] for row in windows["packages"]
    }
    for root in roots:
        if not isinstance(root, str) or any(c in root for c in "\r\n"):
            raise CandidateCIError("candidate_roots")
        try:
            requirement = Requirement(root)
        except InvalidRequirement:
            raise CandidateCIError("candidate_roots") from None
        name = canonicalize_name(requirement.name)
        require(
            requirement.url is None
            and requirement.marker is None
            and name in versions
            and requirement.specifier.contains(versions[name]),
            "candidate_roots",
        )
    roots = "\n".join(roots) + "\n"
    require(not trial.exists(), "trial_exists")
    trial.mkdir(parents=True, exist_ok=False)
    (trial / "roots.txt").write_text(roots, encoding="utf-8")
    (trial / "versions-only.txt").write_text(constraints, encoding="utf-8")
    source_hashes = source_digests(project_root)
    write_json(
        trial / "environment.json",
        {
            "native": environment,
            "source_manifest_sha256": source_hashes,
            "validation_scope": "native-ubuntu-candidate-not-release",
            "approval": "pending",
        },
    )
    return {"status": "prepared", "approval": "pending"}


def write_native_candidate(trial: Path, project_root: Path) -> dict:
    """Bind a native pip report to candidate-only material, not dependency approval."""
    trial = trial_path(trial, project_root)
    for filename in ("resolve-report.json", "environment.json"):
        require((trial / filename).resolve().is_relative_to(trial), "trial_boundary")
    for filename in (
        "candidate-manifest.json",
        "candidate-ci-py312.lock.txt",
        "wrong-hash.lock.txt",
    ):
        path = trial / filename
        require(not path.exists() and not path.is_symlink(), "trial_outputs")
    windows, ubuntu = source_material(project_root)
    environment = read_object(trial / "environment.json")
    require(environment.get("native") == NATIVE, "native_environment")
    require(
        environment.get("source_manifest_sha256") == source_digests(project_root),
        "source_drift",
    )
    report_path = trial / "resolve-report.json"
    report = read_object(report_path)
    try:
        require(
            report["version"] == "1" and report["pip_version"] == "25.0.1",
            "native_report",
        )
        for key, expected in {
            "sys_platform": "linux",
            "platform_machine": "x86_64",
            "python_full_version": "3.12.10",
        }.items():
            require(report["environment"][key] == expected, "native_report")
        expected_packages = {
            canonicalize_name(row["name"]): (
                row["version"],
                row["wheel"],
                row["sha256"],
            )
            for row in ubuntu["packages"]
        }
        require(isinstance(report["install"], list), "native_report")
        packages = []
        seen = set()
        for item in report["install"]:
            metadata = item["metadata"]
            name = canonicalize_name(metadata["name"], validate=True)
            require(
                name not in seen
                and isinstance(item["is_yanked"], bool)
                and not item["is_yanked"],
                "native_report",
            )
            seen.add(name)
            raw_url = item["download_info"]["url"]
            require(isinstance(raw_url, str), "native_report")
            url = urlsplit(raw_url)
            require(
                url.scheme == "https"
                and url.netloc == "files.pythonhosted.org"
                and not url.query
                and not url.fragment,
                "native_report",
            )
            wheel = unquote(Path(url.path).name)
            sha = item["download_info"]["archive_info"]["hashes"]["sha256"]
            require(
                expected_packages.get(name) == (metadata["version"], wheel, sha),
                "native_report",
            )
            packages.append(
                {
                    "name": name,
                    "version": metadata["version"],
                    "wheel": wheel,
                    "sha256": sha,
                    "requires_python": metadata.get("requires_python"),
                    "requires_dist": metadata.get("requires_dist", []),
                }
            )
        require(seen == expected_packages.keys(), "native_report")
        packages.sort(key=lambda row: row["name"])
    except CandidateCIError:
        raise
    except (KeyError, TypeError, ValueError):
        raise CandidateCIError("native_report") from None
    lock = "".join(
        f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n"
        for row in packages
    )
    lock_name = "candidate-ci-py312.lock.txt"
    manifest = {
        "status": "proposed",
        "approval": "pending",
        "validation_scope": "native-ubuntu-candidate-not-release",
        "environment": report["environment"],
        "pip_version": report["pip_version"],
        "toolchain": environment,
        "roots": windows["roots"],
        "packages": packages,
        "candidate_lock_file": lock_name,
        "text_hash_normalization": "UTF-8 text with LF line endings",
        "candidate_lock_sha256": hashlib.sha256(lock.encode()).hexdigest(),
        "project_input_sha256": ubuntu["project_input_sha256"],
        "resolve_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }
    (trial / lock_name).write_text(lock, encoding="utf-8")
    write_json(trial / "candidate-manifest.json", manifest)
    wrong = packages[0]
    (trial / "wrong-hash.lock.txt").write_text(
        f"{wrong['name']}=={wrong['version']} --hash=sha256:{'0' * 64}\n",
        encoding="utf-8",
    )
    return check_candidate(trial / "candidate-manifest.json", project_root)


def native_environment() -> dict:
    release = platform.freedesktop_os_release()
    libc, libc_version = platform.libc_ver()
    return {
        "os_id": release.get("ID"),
        "os_version": release.get("VERSION_ID"),
        "architecture": platform.machine(),
        "libc": libc,
        "libc_version": libc_version,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pip_version": importlib.metadata.version("pip"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("prepare", "resolved"), required=True)
    parser.add_argument("--trial", type=Path, required=True)
    args = parser.parse_args()
    try:
        environment = native_environment()
        require(environment == NATIVE, "native_environment")
        trial = args.trial if args.trial.is_absolute() else ROOT / args.trial
        if args.stage == "prepare":
            result = prepare_inputs(trial, ROOT, environment)
            record = read_object(trial / "environment.json")
            record["provenance"] = {
                "kernel_release": platform.release(),
                "python_origin": "actions/setup-python"
                if os.environ.get("GITHUB_ACTIONS") == "true"
                else "unverified_native_python",
                **{
                    key: os.environ.get(key)
                    for key in (
                        "GITHUB_SHA",
                        "GITHUB_RUN_ID",
                        "GITHUB_RUN_ATTEMPT",
                        "ImageOS",
                        "ImageVersion",
                    )
                },
            }
            write_json(trial / "environment.json", record)
        else:
            result = write_native_candidate(trial, ROOT)
    except (CandidateCIError, IntegrityError) as error:
        print(json.dumps({"status": "invalid", "category": str(error)}))
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        print(json.dumps({"status": "invalid", "category": "unreadable_material"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
