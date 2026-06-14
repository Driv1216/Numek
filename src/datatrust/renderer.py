from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_html_report(profile: dict, scores: dict, risks: list) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")
    return template.render(
        profile=profile,
        scores=scores,
        risks=risks,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

