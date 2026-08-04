from pathlib import Path
from datatrust.profiler import profile_dataset
from datatrust.renderer import render_html_report
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
        html = render_html_report(
            result["profile"],
            result["scores"],
            result["risks"],
            result["findings"],
            result["context"],
        )

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")
        return str(destination)

    def analyze(self) -> dict:
        """Return the report data without rendering HTML."""
        profile = profile_dataset(self.dataset_path, self.target, self.task)
        scores = score_profile(profile)
        findings = build_findings(profile, scores)
        return {
            "profile": profile,
            "scores": scores,
            "risks": findings[:3],
            "findings": findings,
            "context": {
                "dataset_name": self.dataset_name or self.dataset_path.stem,
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
