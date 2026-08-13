from pathlib import Path

import json

from validation.dry_runs.release_candidate import CANDIDATE_ROOT, DRY_RUN_ROOT, ROOT
from validation.dry_runs.reviewer_packet import PACKET_ROOT


REQUIRED_CONTENT = {
    "TECHNICAL_REVIEWER_QUICKSTART.md": (
        "within `15` minutes",
        "without assistance",
        "Privacy",
        "Python API Alternative",
        "Troubleshooting",
        "Windows PowerShell Timed Run",
        "macOS/Linux Timed Run",
        "Select Python Before Timing",
        "Record Environment And Installation Evidence",
        "Record Private Dataset Evidence",
        "Record The Generated Report Identity",
    ),
    "MANUAL_FIRST_ASSESSMENT.md": (
        "before seeing any DataTrust output",
        "Independent dataset risk band",
        "Precommitted Important Findings",
        "Review Confirmation",
    ),
    "TECHNICAL_DRY_RUN_EVIDENCE.md": (
        "Top-Risk Communication Check",
        "Operating system and exact version",
        "Selected Python command",
        "Post-install `pip freeze` output",
        "Private Dataset Evidence",
        "Objective Outcome",
    ),
    "NON_TECHNICAL_COMPREHENSION.md": (
        "only the frozen candidate's generated HTML report",
        "within 3 minutes",
        "Exact report alias",
        "Report alias matches the technical evidence form",
        "What does this report not prove?",
        "Objective Scoring",
    ),
    "FACILITATOR_INSTRUCTIONS.md": (
        "Do not answer setup",
        "same report alias",
        "Prohibited Anchoring",
        "Returning Evidence",
    ),
    "PASS_FAIL_RULES.md": (
        "There is no conditional pass",
        "Immediate Pause Rules",
        "Fix Classification And Rerun Scope",
    ),
    "PRACTITIONER_EVIDENCE_TEMPLATE.md": (
        "Run And Runtime Gate Evidence",
        "Finding Comparison",
        "Score Defensibility",
        "Gate-Level Outcome",
    ),
}


def verify_materials() -> None:
    for name, required_phrases in REQUIRED_CONTENT.items():
        path = DRY_RUN_ROOT / name
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"Missing dry-run preparation artifact: {path}")
        content = path.read_text(encoding="utf-8")
        missing = [phrase for phrase in required_phrases if phrase not in content]
        if missing:
            raise AssertionError(f"{path} is missing required content: {missing}")
        if "[x]" in content.lower():
            raise AssertionError(f"Dry-run template appears pre-completed: {path}")


def verify_candidate_records() -> None:
    manifests = sorted(CANDIDATE_ROOT.glob("*.json"))
    if not manifests:
        raise AssertionError("No dry-run release-candidate manifest exists.")
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {"candidate_id", "files", "schema_version"}
        missing = sorted(required - set(manifest))
        if missing:
            raise AssertionError(f"Historical candidate record is incomplete: {manifest_path}: {missing}")
    # RC_003 is now historical evidence. Active source documents may be updated
    # after the review process was superseded. Do not require historical
    # candidate hashes to match the current working tree.


def verify_packets() -> None:
    manifests = sorted(PACKET_ROOT.glob("*.manifest.json"))
    if not manifests:
        raise AssertionError("No clean reviewer packet manifest exists.")
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive_path = manifest.get("archive_path")
        if not archive_path:
            raise AssertionError(f"Historical packet record is incomplete: {manifest_path}")
        if not (ROOT / archive_path).exists():
            raise AssertionError(f"Historical packet archive is missing: {archive_path}")


def verify_all() -> None:
    verify_materials()
    verify_packets()
    verify_candidate_records()


if __name__ == "__main__":
    verify_all()
    print("Historical dry-run archive verification passed.")
