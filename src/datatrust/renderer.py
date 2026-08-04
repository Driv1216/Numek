from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_html_report(
    profile: dict,
    scores: dict,
    risks: list,
    findings: list = None,
    context: dict = None,
) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
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
        target_chart=_target_chart(profile["target_distribution"]),
        missingness_chart=_missingness_chart(profile["columns"]),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


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
