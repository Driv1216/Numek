from datetime import datetime
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape


def render_html_report(
    profile: dict,
    scores: dict,
    risks: list,
    findings: list = None,
    context: dict = None,
    narrative: dict = None,
) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["soft_wrap_name"] = _soft_wrap_name
    template = env.get_template("report.html")
    safe_context = context or {
        "dataset_name": Path(profile["dataset_path"]).stem,
        "purpose": None,
        "source_filename": Path(profile["dataset_path"]).name,
    }
    return template.render(
        profile=profile,
        scores=scores,
        risks=risks,
        findings=findings or risks,
        context=safe_context,
        display_names={
            "dataset": _soft_wrap_name(safe_context["dataset_name"]),
            "source": _soft_wrap_name(safe_context["source_filename"]),
            "target": _soft_wrap_name(profile["target"]),
        },
        narrative=narrative or {},
        target_chart=_target_chart(profile["target_distribution"]),
        missingness_chart=_missingness_chart(profile["columns"]),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def write_html_report(result: dict, output_path: str) -> str:
    """Render one completed analysis result to a standalone HTML report."""
    html = render_html_report(
        result["profile"],
        result["scores"],
        result["risks"],
        result["findings"],
        result["context"],
        result["narrative"],
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return str(destination)


def _target_chart(distribution: list) -> list:
    visible = [dict(item) for item in distribution[:20]]
    remainder = distribution[20:]
    if remainder:
        visible.append(
            {
                "label": f"Other ({len(remainder)} classes)",
                "count": sum(item["count"] for item in remainder),
                "percentage": round(sum(item["percentage"] for item in remainder), 2),
            }
        )
    return visible


def _missingness_chart(columns: list) -> list:
    affected = [
        dict(column)
        for column in columns
        if column["role"] == "feature" and column["missing_count"] > 0
    ]
    affected.sort(key=lambda column: (-column["missing_rate"], column["name"]))
    return affected[:15]


def _soft_wrap_name(value: str) -> Markup:
    """Add safe wrap opportunities at semantic name boundaries."""
    parts = re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[_-])", str(value))
    return Markup("<wbr>".join(str(escape(part)) for part in parts))
