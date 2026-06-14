import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DRY_RUN_ROOT = ROOT / "validation" / "dry_runs"
PACKET_ROOT = DRY_RUN_ROOT / "packets"

PACKET_FILES = {
    "validation/dry_runs/REVIEWER_PACKET_README.md": "README.md",
    "pyproject.toml": "pyproject.toml",
    "setup.py": "setup.py",
    "validation/dry_runs/TECHNICAL_REVIEWER_QUICKSTART.md":
        "reviewer_materials/TECHNICAL_REVIEWER_QUICKSTART.md",
    "validation/dry_runs/MANUAL_FIRST_ASSESSMENT.md":
        "reviewer_materials/MANUAL_FIRST_ASSESSMENT.md",
    "validation/dry_runs/TECHNICAL_DRY_RUN_EVIDENCE.md":
        "reviewer_materials/TECHNICAL_DRY_RUN_EVIDENCE.md",
}
PACKET_DIRECTORIES = ("src/datatrust",)
REQUIRED_PACKET_FILES = {
    "README.md",
    "pyproject.toml",
    "setup.py",
    "src/datatrust/__init__.py",
    "src/datatrust/cli.py",
    "src/datatrust/core.py",
    "src/datatrust/profiler.py",
    "src/datatrust/renderer.py",
    "src/datatrust/risks.py",
    "src/datatrust/scoring.py",
    "src/datatrust/templates/report.html",
    "reviewer_materials/TECHNICAL_REVIEWER_QUICKSTART.md",
    "reviewer_materials/MANUAL_FIRST_ASSESSMENT.md",
    "reviewer_materials/TECHNICAL_DRY_RUN_EVIDENCE.md",
    "PACKET_MANIFEST.json",
}
PROHIBITED_PARTS = {
    ".git",
    ".venv",
    ".vscode",
    "__pycache__",
    "comparison",
    "docs",
    "evidence",
    "examples",
    "handoffs",
    "reports",
    "results",
    "tests",
    "validation",
    "venv",
}
PROHIBITED_SUFFIXES = {".html", ".pyc", ".pyo"}
ALLOWED_HTML = {"src/datatrust/templates/report.html"}
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def aggregate_hash(files: dict[str, str]) -> str:
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(files.items()))
    return sha256_bytes(payload.encode("utf-8"))


def source_entries() -> dict[str, Path]:
    entries = {destination: ROOT / source for source, destination in PACKET_FILES.items()}
    for directory in PACKET_DIRECTORIES:
        for source in sorted((ROOT / directory).rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                entries[source.relative_to(ROOT).as_posix()] = source
    missing = [str(source) for source in entries.values() if not source.exists()]
    if missing:
        raise AssertionError(f"Reviewer packet source files are missing: {missing}")
    return dict(sorted(entries.items()))


def validate_packet_path(relative: str) -> None:
    path = Path(relative)
    if any(part.lower() in PROHIBITED_PARTS for part in path.parts):
        raise AssertionError(f"Prohibited reviewer packet path: {relative}")
    if path.suffix.lower() in PROHIBITED_SUFFIXES and relative not in ALLOWED_HTML:
        raise AssertionError(f"Prohibited reviewer packet file type: {relative}")


def write_deterministic_zip(packet_dir: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(path for path in packet_dir.rglob("*") if path.is_file()):
            relative = source.relative_to(packet_dir).as_posix()
            info = zipfile.ZipInfo(relative, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def create_packet(packet_id: str) -> Path:
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", packet_id):
        raise ValueError("Packet ID must contain only uppercase letters, numbers, '_' or '-'.")

    PACKET_ROOT.mkdir(parents=True, exist_ok=True)
    packet_dir = PACKET_ROOT / packet_id
    archive_path = PACKET_ROOT / f"{packet_id}.zip"
    manifest_path = PACKET_ROOT / f"{packet_id}.manifest.json"
    if packet_dir.exists() or archive_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Reviewer packet already exists and is immutable: {packet_id}")

    packet_dir.mkdir()
    for relative, source in source_entries().items():
        validate_packet_path(relative)
        destination = packet_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    files = {
        path.relative_to(packet_dir).as_posix(): sha256(path)
        for path in sorted(packet_dir.rglob("*"))
        if path.is_file()
    }
    packet_manifest = {
        "schema_version": 1,
        "packet_id": packet_id,
        "identity_method": "SHA-256 over sorted packet-relative paths and file hashes",
        "file_count_excluding_manifest": len(files),
        "aggregate_sha256_excluding_manifest": aggregate_hash(files),
        "files": files,
    }
    embedded_manifest = packet_dir / "PACKET_MANIFEST.json"
    embedded_manifest.write_text(
        json.dumps(packet_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_deterministic_zip(packet_dir, archive_path)

    external_manifest = {
        **packet_manifest,
        "archive_path": archive_path.relative_to(ROOT).as_posix(),
        "archive_sha256": sha256(archive_path),
    }
    manifest_path.write_text(
        json.dumps(external_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verify_packet(manifest_path)
    return manifest_path


def verify_packet(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_id = manifest["packet_id"]
    packet_dir = PACKET_ROOT / packet_id
    archive_path = ROOT / manifest["archive_path"]

    actual_paths = {
        path.relative_to(packet_dir).as_posix()
        for path in packet_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(REQUIRED_PACKET_FILES - actual_paths)
    if missing:
        raise AssertionError(f"Reviewer packet is missing required files: {missing}")
    for relative in sorted(actual_paths):
        validate_packet_path(relative)

    actual_files = {
        relative: sha256(packet_dir / relative)
        for relative in sorted(actual_paths - {"PACKET_MANIFEST.json"})
    }
    if actual_files != manifest["files"]:
        raise AssertionError("Reviewer packet file hashes do not match its manifest.")
    if aggregate_hash(actual_files) != manifest["aggregate_sha256_excluding_manifest"]:
        raise AssertionError("Reviewer packet aggregate SHA-256 does not match.")
    if not archive_path.exists() or sha256(archive_path) != manifest["archive_sha256"]:
        raise AssertionError("Reviewer packet archive is missing or its SHA-256 does not match.")

    with zipfile.ZipFile(archive_path) as archive:
        archive_paths = set(archive.namelist())
        if archive_paths != actual_paths:
            raise AssertionError("Reviewer packet archive contents differ from extracted packet.")
        for relative in archive_paths:
            validate_packet_path(relative)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify a clean reviewer packet.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--id", required=True, dest="packet_id")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "create":
        destination = create_packet(args.packet_id)
        print(f"Created and verified clean reviewer packet: {destination}")
    else:
        verify_packet(args.manifest)
        print(f"Clean reviewer packet verification passed: {args.manifest}")


if __name__ == "__main__":
    main()
