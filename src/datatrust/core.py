import re
from pathlib import Path

from datatrust.narrative import build_narrative
from datatrust.profiler import profile_dataset
from datatrust.renderer import write_html_report
from datatrust.risks import build_findings
from datatrust.scoring import score_profile


class DataTrust:
    """Generate local dataset reliability reports."""

    def __init__(
        self,
        dataset_path: str,
        target: str,
        task: str = "classification",
        *,
        dataset_name: str = None,
        purpose: str = None,
        source_filename: str = None,
    ):
        self.dataset_path = Path(dataset_path)
        self.target = target
        self.task = task
        self.dataset_name = _clean_context_value(
            dataset_name, "Dataset name", maximum_length=120
        )
        self.purpose = _clean_context_value(purpose, "Purpose", maximum_length=1000)
        cleaned_source = _clean_context_value(
            source_filename, "Source filename", maximum_length=255
        )
        self.source_filename = (
            Path(cleaned_source.replace("\\", "/")).name if cleaned_source else None
        )

    def generate_report(self, output_path: str) -> str:
        result = self.analyze()
        return write_html_report(result, output_path)

    def analyze(self) -> dict:
        """Return the report data without rendering HTML."""
        profile = profile_dataset(self.dataset_path, self.target, self.task)
        scores = score_profile(profile)
        findings = build_findings(profile, scores)
        context_name = self.dataset_name
        if not context_name:
            context_name = _humanize_fallback_name(
                Path(self.source_filename or self.dataset_path.name).stem
            )
        return {
            "profile": profile,
            "scores": scores,
            "risks": findings[:3],
            "findings": findings,
            "narrative": build_narrative(profile, scores, findings[:3], findings),
            "context": {
                "dataset_name": context_name,
                "purpose": self.purpose,
                "source_filename": self.source_filename or self.dataset_path.name,
            },
        }


def _clean_context_value(value, label: str, maximum_length: int):
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum_length:
        raise ValueError(f"{label} must be {maximum_length} characters or fewer.")
    return cleaned


def _humanize_fallback_name(value: str) -> str:
    """Turn a filename stem into a readable title without changing custom names."""
    chunks = [chunk for chunk in re.split(r"[_\-\s]+", str(value)) if chunk]
    words = []
    for chunk in chunks:
        if re.match(r"^[a-z][A-Z]", chunk):
            parts = [chunk]
        else:
            separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", chunk)
            separated = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", separated)
            parts = separated.split()
        for part in parts:
            words.append(part.capitalize() if part.islower() else part)
    return " ".join(words) or str(value)
