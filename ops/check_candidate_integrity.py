#!/usr/bin/env python3
"""Read-only offline candidate evidence check; never install or approve dependencies.

Uses packaging from the existing pytest toolchain, not the candidate environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from email.parser import BytesParser
from lzma import LZMAError
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

PROJECT_INPUTS = frozenset(
    {"api/pyproject.toml", "worker/pyproject.toml", "tests/contract/requirements.txt"}
)
SHA256 = re.compile(r"[0-9a-f]{64}")
LOCK_ENTRY = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s+--hash=sha256:([0-9a-f]{64})")


class IntegrityError(ValueError):
    """A redacted failure category, without caller-controlled content."""


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise IntegrityError(category)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise IntegrityError("json_constant")


def _sha(value: object) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise IntegrityError("sha256_shape")
    return value


def _filename(value: object) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise IntegrityError("filename_shape")
    _require(not any(char in value for char in "/\\:\x00"), "filename_shape")
    return value


def _inside(base: Path, relative: str) -> Path:
    path = base / relative
    _require(path.resolve().is_relative_to(base.resolve()), "path_boundary")
    _require(path.is_file(), "file_missing")
    return path


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lock_packages(text: str) -> dict[str, tuple[str, str]]:
    records = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_ENTRY.fullmatch(line)
        if match is None:
            raise IntegrityError("lock_entry")
        name, version, sha = match.groups()
        name = canonicalize_name(name, validate=True)
        Version(version)
        _require(name not in records, "duplicate_lock_package")
        records[name] = (version, sha)
    return records


def _manifest_packages(rows: object) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise IntegrityError("packages_shape")
    packages = {}
    for row in rows:
        _require(isinstance(row, dict), "package_shape")
        name, version = row.get("name"), row.get("version")
        _require(isinstance(name, str) and isinstance(version, str), "package_identity")
        name = canonicalize_name(name, validate=True)
        parsed_version = Version(version)
        _require(name not in packages, "duplicate_package")
        wheel = _filename(row.get("wheel"))
        wheel_name, wheel_version, _, _ = parse_wheel_filename(wheel)
        _require(name == wheel_name and parsed_version == wheel_version, "wheel_identity")
        _sha(row.get("sha256"))
        packages[name] = row
    return packages


def _check_wheel(base: Path, row: dict) -> None:
    path = _inside(base, row["wheel"])
    with path.open("rb") as stream:
        _require(hashlib.file_digest(stream, "sha256").hexdigest() == row["sha256"], "wheel_digest")
        stream.seek(0)
        with ZipFile(stream) as archive:
            metadata = [
                entry
                for entry in archive.infolist()
                if len(entry.filename.split("/")) == 2
                and entry.filename.split("/")[0].endswith(".dist-info")
                and entry.filename.split("/")[1] == "METADATA"
            ]
            _require(len(metadata) == 1, "wheel_metadata_count")
            message = BytesParser().parsebytes(archive.read(metadata[0]), headersonly=True)
            names, versions = message.get_all("Name", []), message.get_all("Version", [])
            _require(len(names) == len(versions) == 1, "wheel_metadata_identity")
            _require(
                canonicalize_name(names[0], validate=True) == canonicalize_name(row["name"])
                and Version(versions[0]) == Version(row["version"]),
                "wheel_metadata_identity",
            )


def check_candidate(manifest: Path, project_root: Path, wheelhouse: Path | None = None) -> dict:
    """Check exact evidence identity, not resolution, platform readiness or approval."""
    try:
        data = json.loads(
            _text(manifest), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        _require(isinstance(data, dict), "manifest_shape")
        _require(
            data.get("status") == "proposed" and data.get("approval") == "pending",
            "candidate_status",
        )
        packages = _manifest_packages(data.get("packages"))
        lock = _inside(manifest.parent, _filename(data.get("candidate_lock_file")))
        text = _text(lock)
        _require(_text_digest(text) == _sha(data.get("candidate_lock_sha256")), "lock_digest")
        expected = {name: (row["version"], row["sha256"]) for name, row in packages.items()}
        _require(_lock_packages(text) == expected, "lock_package_set")
        inputs = data.get("project_input_sha256")
        _require(isinstance(inputs, dict) and inputs.keys() == PROJECT_INPUTS, "project_inputs")
        for relative, sha in inputs.items():
            _require(
                _text_digest(_text(_inside(project_root, relative))) == _sha(sha), "project_digest"
            )
        if wheelhouse is not None:
            for row in packages.values():
                _check_wheel(wheelhouse, row)
        return {
            "status": "consistent",
            "packages_checked": len(packages),
            "wheel_bytes_checked": wheelhouse is not None,
            "approval": "not_dependency_approval",
        }
    except IntegrityError:
        raise
    except (
        OSError, ValueError, TypeError, BadZipFile, KeyError, RuntimeError, ZlibError, LZMAError
    ):
        raise IntegrityError("unreadable_or_invalid_material") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    try:
        result = check_candidate(args.manifest, args.project_root, args.wheelhouse)
    except IntegrityError as error:
        print(json.dumps({"status": "invalid", "category": str(error)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
