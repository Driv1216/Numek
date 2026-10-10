from datetime import datetime
from pathlib import Path
import re
import os
import tempfile
import hashlib

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from datatrust.wording import count_phrase


def render_html_report(
    profile: dict,
    scores: dict,
    risks: list,
    findings: list = None,
    context: dict = None,
    narrative: dict = None,
    *,
    generated_at: str = None,
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
        generated_at=generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def write_html_report(result: dict, output_path: str) -> str:
    """Render one completed analysis result to a standalone HTML report."""
    protect_source(result["profile"]["dataset_path"], [output_path])
    destination = Path(output_path)
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError(f"Report destination is not an ordinary file: {destination}")
    html = render_html_report(
        result["profile"],
        result["scores"],
        result["risks"],
        result["findings"],
        result["context"],
        result["narrative"],
    )
    return publish_bytes(destination, html.encode("utf-8"), replace_existing=True)


class ArtifactCollisionError(ValueError):
    """A destination is occupied or aliases another input/output."""


def _collision(path):
    return ArtifactCollisionError(
        f"Artifact destination is occupied: {path}. Choose another output stem or explicit HTML destination."
    )


def protect_source(source, destinations):
    sources = [Path(p) for p in source] if isinstance(source, (tuple, list)) else [Path(source)]
    paths = [Path(path) for path in destinations if path is not None]
    for index, path in enumerate(paths):
        if any(path.resolve() == source.resolve() or (path.exists() and source.exists() and os.path.samefile(path, source)) for source in sources):
            raise ArtifactCollisionError(f"Artifact destination aliases the original source: {path}.")
        for other in paths[:index]:
            if path.resolve() == other.resolve() or (path.exists() and other.exists() and os.path.samefile(path, other)):
                raise ArtifactCollisionError(f"Artifact destinations must be distinct: {path} and {other}.")


def publish_bytes(path, content, *, replace_existing=False):
    """Publish without replacement, including a destination created after preflight.

    The unique staging file and hard-link publication live on the same filesystem.
    No cleanup operation ever removes the destination or an unowned temporary file.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".datatrust-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            if replace_existing:
                # Legacy explicit HTML replaces a directory entry, never writes
                # through a late hard-link/symlink alias into the original data.
                if destination.is_symlink() or (destination.exists() and not destination.is_file()):
                    raise _collision(destination)
                os.replace(temporary, destination)
            else:
                os.link(temporary, destination)
        except FileExistsError as exc:
            raise _collision(destination) from exc
    finally:
        temporary.unlink(missing_ok=True)
    return str(destination)


def _html_state(path, content):
    path = Path(path)
    _validate_parent(path)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise _collision(path)
    if path.exists():
        if path.read_bytes() != content:
            raise _collision(path)
        return True
    return False


def _new_destination(path):
    path = Path(path)
    _validate_parent(path)
    if path.exists() or path.is_symlink():
        raise _collision(path)


def _validate_parent(path):
    for parent in Path(path).parents:
        if parent.exists() or parent.is_symlink():
            if not parent.is_dir():
                raise ArtifactCollisionError(f"Artifact parent is not a directory: {parent}. Choose another output path.")
            break


def _report_label(value):
    """Display internal labels without changing their serialized identifiers."""
    labels = {
        "pandas_default": "Pandas default missing tokens",
        "empty_only": "Empty strings only",
        "custom": "Explicit custom tokens",
        "eof": "End of source",
        "pandas_in_memory": "Pandas in memory",
        "insufficient_finite_observations": "Fewer than four finite observations",
        "zero_iqr": "The interquartile range is zero",
        "finite_1.5_iqr": "Finite-value 1.5-IQR fences",
        "finite_descriptive": "Finite-value descriptive statistics",
        "max_source_bytes": "Maximum source size",
        "max_frame_bytes": "Maximum loaded frame size",
        "max_rows": "Maximum rows",
        "max_columns": "Maximum columns",
        "max_seconds": "Cooperative elapsed-time limit",
    }
    return labels.get(str(value), str(value).replace("_", " "))


def _report_value(value, *, empty="None configured"):
    """Readable nested metadata; escaping remains the template's responsibility."""
    if value is None:
        return "Not set"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, dict):
        return "; ".join(f"{_report_label(k).capitalize()}: {_report_value(v)}" for k, v in value.items()) or empty
    if isinstance(value, (tuple, list)):
        return "; ".join(_report_value(v) for v in value) or empty
    return str(value)


def _report_evidence_text(value):
    # Findings remain unchanged in API/JSON; correct count wording only at display.
    value = re.sub(r"(?<![\d.])1 rows repeat\b", "1 row repeats", value)
    return re.sub(
        r"(?<![\d.])1 (observed values|values|repeated rows|participating rows|missing cells|groups)\b",
        lambda m: "1 " + m[1][:-1], value,
    )


def _report_sentence(value):
    """Join display prose with exactly one terminal period, leaving JSON untouched."""
    text = str(value or "").strip().rstrip(". ")
    return text + "." if text else ""


def _regression_population(value):
    """Describe finding populations without exposing internal metadata field names."""
    name = value.get("name", "")
    denominator = value.get("denominator")
    count = f"{denominator:,}" if denominator is not None else None
    descriptions = {
        "all parsed rows": f"Based on all {count} parsed {'row' if denominator == 1 else 'rows'}",
        "all complete parsed rows, including the target and nulls":
            f"Based on all {count} parsed {'row' if denominator == 1 else 'rows'}, including target and missing values",
        "finite targets": f"Based on {count} finite target {'value' if denominator == 1 else 'values'}",
        "feature columns": f"Based on {count} feature {'column' if denominator == 1 else 'columns'}",
        "parsed feature cells": f"Based on {count} parsed feature {'cell' if denominator == 1 else 'cells'}",
        "finite values by affected feature": "Each affected feature is assessed on its finite values",
        "fully verified relationship overlap scopes": "Based on fully verified row overlaps",
    }
    # Known counted scopes always have a denominator. Do not manufacture one if absent.
    description = descriptions.get(name) if count is not None or name in {
        "finite values by affected feature", "fully verified relationship overlap scopes"
    } else None
    description = description or ("Based on " + _report_label(name) if name else "")
    detail = value.get("detail", "")
    if name == "finite values by affected feature":
        detail = "Counts of infinite values use all parsed rows"
    elif name == "fully verified relationship overlap scopes":
        detail = "Each relationship reports its own overlap and coverage of finite targets"
    return " ".join(_report_sentence(part) for part in (description, detail) if part)


def _regression_inspection_notice(warning):
    """Humanize planned source-token bounds only; unexpected failures stay warnings."""
    reason = warning.get("inspected_population", {}).get("stopping_reason")
    limits = {
        "record_limit": "record limit",
        "cell_limit": "comparable-cell limit",
        "byte_limit": "byte limit",
        "byte_limit_incomplete_record": "byte limit before the next complete record",
    }
    if warning.get("code") != "inspection_incomplete" or reason not in limits:
        return None
    return {
        "title": "Source-token inspection coverage",
        "text": f"Source-token inspection stopped at its configured {limits[reason]}. "
                "This is expected coverage disclosure, not an analysis failure. "
                "Parsing review covers only the inspected source tokens; "
                "absence of warnings within that scope does not establish losslessness.",
    }


def render_analysis_result(result):
    """Render only completed evidence; exports never trigger a new analysis."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)),
                      autoescape=select_autoescape(["html", "xml"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["soft_wrap_name"] = _soft_wrap_name
    env.filters["report_label"] = _report_label
    env.filters["report_value"] = _report_value
    env.filters["report_evidence_text"] = _report_evidence_text
    env.filters["report_sentence"] = _report_sentence
    env.filters["regression_population"] = _regression_population
    env.filters["regression_inspection_notice"] = _regression_inspection_notice
    env.filters["count_phrase"] = count_phrase
    env.filters["regression_number"] = lambda value: "Unavailable" if value is None else (format(value, ".8g") if isinstance(value, float) else str(value))
    value = result.to_dict()
    if result.schema_version == '1.4':
        from datatrust.temporal_presentation import report_view
        return env.get_template('temporal_report.html').render(result=value,view=report_view(result))
    if result.schema_version == '1.3':
        from datatrust.m4_presentation import report_view
        return env.get_template('m4_report.html').render(result=value, view=report_view(result))
    if result.schema_version == "1.2":
        from datatrust.presentation import report_view
        return env.get_template("m3_report.html").render(result=value, view=report_view(result))
    if result.methodology_id == "classification_legacy_2026_08_13":
        legacy = result.to_legacy_dict()
        html = render_html_report(**legacy, generated_at=result.generated_at)
        disclosure = env.get_template("analysis_disclosure.html").render(result=value)
        # Keep the established eight topics and analytical body intact.
        position = html.rfind("</section>")
        return html[:position] + disclosure + html[position:]
    # Reuse the existing report's presentation rules without changing its legacy bytes.
    style = re.search(r"<style>(.*?)</style>", (template_dir / "report.html").read_text(), re.S).group(1)
    return env.get_template("regression_report.html" if result.task.kind == "regression" else "unlabeled_report.html").render(result=value, style=Markup(style))


def write_analysis_json(result, path):
    protect_source(result.source_paths, [path])
    if result.schema_version in {'1.3','1.4'}:
        from datatrust.scalable import available
        if available(Path(path).parent) < result.execution['effective_limits']['free_disk_bytes'] + 256 * 1024**2:
            raise ValueError('Output filesystem lacks the 256 MiB export reservation plus configured free-space reserve.')
    _new_destination(path)
    return publish_bytes(path, result.json_text().encode("utf-8"))


def write_report_artifacts(result, path, *, format="html", html_path=None, json_path=None,
                           pdf_converter=None, legacy_html=False):
    """Create a discoverable report bundle without implicit overwrite permission."""
    from datatrust.contracts import ReportArtifacts
    from datatrust.pdf import PDFRenderError, render_pdf_report
    if format not in {"html", "pdf"}:
        raise ValueError("Report format must be html or pdf.")
    if format == "html" and html_path is not None:
        raise ValueError("html_path is only supported for PDF output.")
    pdf_path = Path(path) if format == "pdf" else None
    canonical = Path(html_path) if html_path is not None else (Path(path).with_suffix(".html") if pdf_path else Path(path))
    protect_source(result.source_paths, [canonical, pdf_path, json_path])
    if result.schema_version in {'1.3','1.4'}:
        from datatrust.scalable import available
        reserve = result.execution['effective_limits']['free_disk_bytes']
        seen = set()
        for output in (canonical, pdf_path, json_path):
            if output is None: continue
            parent = Path(output).parent.resolve()
            while not parent.exists(): parent = parent.parent
            device = parent.stat().st_dev
            if device not in seen and available(parent) < reserve + 256 * 1024**2:
                raise ValueError('Output filesystem lacks the 256 MiB export reservation plus configured free-space reserve.')
            seen.add(device)
    if legacy_html:
        content = render_html_report(**result.to_legacy_dict(), generated_at=datetime.fromisoformat(result.generated_at).strftime("%Y-%m-%d %H:%M:%S")).encode("utf-8")
    else:
        content = render_analysis_result(result).encode("utf-8")
    reused = _html_state(canonical, content)
    for output in (pdf_path, json_path):
        if output is not None:
            _new_destination(output)
    if not reused:
        try:
            publish_bytes(canonical, content)
        except ArtifactCollisionError as exc:
            # A concurrent creator may have published the same canonical bytes.
            if not _html_state(canonical, content):
                raise exc
            reused = True
    artifacts = ReportArtifacts(html_path=str(canonical), reused_html=reused)
    try:
        if json_path is not None:
            publish_bytes(json_path, result.json_text().encode("utf-8"))
            artifacts = ReportArtifacts(str(canonical), json_path=str(json_path), reused_html=reused)
        if pdf_path is not None:
            (pdf_converter or render_pdf_report)(canonical, pdf_path, expected_html_sha256=hashlib.sha256(content).hexdigest())
            artifacts = ReportArtifacts(str(canonical), str(pdf_path), str(json_path) if json_path else None, reused)
    except Exception as exc:
        exc.artifacts = artifacts
        if isinstance(exc, PDFRenderError):
            exc.args = (f"{exc} HTML report retained at {canonical}.",)
        raise
    if result.schema_version == "1.2":
        from dataclasses import replace
        from datatrust.presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result)["qa"])
    if result.schema_version == "1.4":
        from dataclasses import replace
        from datatrust.temporal_presentation import report_view
        artifacts = replace(artifacts,qa_metadata=report_view(result)["qa"])
    return artifacts


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
