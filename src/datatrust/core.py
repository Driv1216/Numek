from pathlib import Path
from typing import Optional

from datatrust.profiler import profile_dataset
from datatrust.renderer import render_html_report
from datatrust.risks import summarize_risks
from datatrust.scoring import score_profile


class DataTrust:
    """Generate local dataset reliability reports."""

    def __init__(self, dataset_path: str, target: str, task: str = "classification"):
        self.dataset_path = Path(dataset_path)
        self.target = target
        self.task = task

    def generate_report(self, output_path: str) -> str:
        profile = profile_dataset(self.dataset_path, self.target, self.task)
        scores = score_profile(profile)
        risks = summarize_risks(profile, scores)
        html = render_html_report(profile, scores, risks)

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")
        return str(destination)

    def analyze(self) -> dict:
        """Return the report data without rendering HTML."""
        profile = profile_dataset(self.dataset_path, self.target, self.task)
        scores = score_profile(profile)
        risks = summarize_risks(profile, scores)
        return {"profile": profile, "scores": scores, "risks": risks}

