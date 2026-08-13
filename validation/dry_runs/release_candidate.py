"""Historical RC_003 release-candidate archive tooling.

This module preserves the old hash-based candidate process for archive
reproducibility. It is not part of the current internal DataTrust review
workflow and must not be treated as a future product acceptance requirement.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from validation.dry_runs.reviewer_packet import ROOT, verify_packet

DRY_RUN_ROOT = ROOT / "validation" / "dry_runs"
CANDIDATE_ROOT = DRY_RUN_ROOT / "release_candidates"

EXPLICIT_FILES = (
    ".python-version",
    "README.md",
    "METHODOLOGY.md",
    "pyproject.toml",
    "setup.py",
    "examples/loan_data.csv",
    "validation/README.md",
)
TRACKED_DIRECTORIES = (
    "src/datatrust",
    "tests",
    "validation/dry_runs",
)
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "evidence",
    "packets",
    "release_candidates",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def is_tracked(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
        return False
    return not any(part in EXCLUDED_PARTS for part in relative.parts)


def tracked_files() -> list[Path]:
    paths = {ROOT / relative for relative in EXPLICIT_FILES}
    for directory in TRACKED_DIRECTORIES:
        paths.update(path for path in (ROOT / directory).rglob("*") if is_tracked(path))
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise AssertionError(f"Candidate source files are missing: {missing}")
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def file_hashes() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): sha256_bytes(path.read_bytes())
        for path in tracked_files()
    }


def aggregate_hash(files: dict[str, str]) -> str:
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(files.items()))
    return sha256_bytes(payload.encode("utf-8"))


def create_candidate(candidate_id: str, packet_manifest_path: Path | None = None) -> Path:
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", candidate_id):
        raise ValueError("Candidate ID must contain only uppercase letters, numbers, '_' or '-'.")

    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
    destination = CANDIDATE_ROOT / f"{candidate_id}.json"
    if destination.exists():
        raise FileExistsError(
            f"Candidate manifest already exists and is immutable: {destination}"
        )

    files = file_hashes()
    packet = None
    if packet_manifest_path is not None:
        packet_manifest_path = packet_manifest_path.resolve()
        verify_packet(packet_manifest_path)
        packet_manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
        packet = {
            "packet_id": packet_manifest["packet_id"],
            "packet_manifest_path": packet_manifest_path.relative_to(ROOT).as_posix(),
            "packet_aggregate_sha256": packet_manifest["aggregate_sha256_excluding_manifest"],
            "packet_archive_sha256": packet_manifest["archive_sha256"],
        }
    manifest = {
        "schema_version": 2,
        "candidate_id": candidate_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version_used_to_create": sys.version.split()[0],
        "identity_method": "SHA-256 over sorted candidate-relative paths and file hashes",
        "file_count": len(files),
        "aggregate_sha256": aggregate_hash(files),
        "files": files,
    }
    if packet is not None:
        manifest["reviewer_packet"] = packet
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def verify_candidate(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current_files = file_hashes()
    expected_files = manifest["files"]

    if current_files != expected_files:
        added = sorted(set(current_files) - set(expected_files))
        removed = sorted(set(expected_files) - set(current_files))
        changed = sorted(
            path
            for path in set(current_files).intersection(expected_files)
            if current_files[path] != expected_files[path]
        )
        raise AssertionError(
            "Release candidate changed. "
            f"Added: {added}; removed: {removed}; changed: {changed}"
        )

    current_aggregate = aggregate_hash(current_files)
    if current_aggregate != manifest["aggregate_sha256"]:
        raise AssertionError("Release candidate aggregate SHA-256 does not match.")
    packet = manifest.get("reviewer_packet")
    if packet:
        packet_manifest_path = ROOT / packet["packet_manifest_path"]
        verify_packet(packet_manifest_path)
        packet_manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
        if packet_manifest["aggregate_sha256_excluding_manifest"] != packet["packet_aggregate_sha256"]:
            raise AssertionError("Release candidate reviewer-packet aggregate SHA-256 does not match.")
        if packet_manifest["archive_sha256"] != packet["packet_archive_sha256"]:
            raise AssertionError("Release candidate reviewer-packet archive SHA-256 does not match.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify a dry-run release candidate.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--id", required=True, dest="candidate_id")
    create_parser.add_argument("--packet-manifest", type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "create":
        destination = create_candidate(args.candidate_id, args.packet_manifest)
        print(f"Created immutable release-candidate manifest: {destination}")
    else:
        verify_candidate(args.manifest)
        print(f"Release candidate verification passed: {args.manifest}")


if __name__ == "__main__":
    main()
