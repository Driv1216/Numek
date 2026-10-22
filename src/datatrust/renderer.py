from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
import os
import tempfile
import hashlib

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from datatrust.wording import count_phrase


def _report_time(value):
    """A report timestamp with its time zone stated: UTC when the canonical value carries an offset."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is None:
        return moment.strftime("%Y-%m-%d %H:%M:%S") + " (time zone not recorded)"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _legacy_time(value):
    """The legacy report's "Generated" value: a canonical time with an offset is stated in UTC; the legacy direct
    API (no time, or a plain local string) keeps its established bytes."""
    if value is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        aware = datetime.fromisoformat(str(value)).tzinfo is not None
    except ValueError:
        aware = False
    return _report_time(value) if aware else value


def _delimiter_label(value):
    from datatrust.ingestion import delimiter_name
    name = delimiter_name(value or ",")
    return name[:1].upper() + name[1:]


@lru_cache(maxsize=1)
def presentation_identity():
    """The DataTrust package version and a digest of the report templates: how a report was rendered.
    Recorded separately from the analytical methodology, so a presentation change never reads as a method change."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        package = version("datatrust")
    except PackageNotFoundError:
        package = "not recorded"
    digest = hashlib.sha256()
    for path in sorted((Path(__file__).parent / "templates").glob("*.html")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return {"package_version": package, "report_templates": digest.hexdigest()[:12]}


def _presentation_line():
    identity = presentation_identity()
    return f"DataTrust {identity['package_version']}, report templates {identity['report_templates']}"


def _report_filters(env):
    env.filters["report_time"] = _report_time
    env.filters.setdefault("report_label", _report_label)
    env.filters["delimiter_label"] = _delimiter_label
    env.globals["presentation"] = _presentation_line()


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
    _report_filters(env)
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
        generated_at=_legacy_time(generated_at),
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
    """Render only completed evidence; exports never trigger a new analysis. A source read with a separator other
    than a comma is named under the title; comma reports are unchanged, byte for byte."""
    return _with_separator_note(_render_analysis_result(result), result)


def _with_separator_note(html, result):
    note = _separator_note(result.to_dict())
    position = html.find("</h1>")
    if not note or position < 0:
        return html
    position += len("</h1>")
    return html[:position] + f'<p class="separator-note">CSV separator: {escape(note)}.</p>' + html[position:]


def _separator_note(value):
    from datatrust.contracts import _PARSE_OPTION_KEYS
    from datatrust.ingestion import delimiter_name
    found = set()
    def walk(item):
        if isinstance(item, dict):
            if _PARSE_OPTION_KEYS <= item.keys() and item.get("delimiter", ",") != ",":
                found.add(item["delimiter"])
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return ", ".join(sorted(delimiter_name(d) for d in found))


def _analysis_env():
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
    _report_filters(env)
    env.filters["regression_number"] = lambda value: "Unavailable" if value is None else (format(value, ".8g") if isinstance(value, float) else str(value))
    return env


def _with_provenance(html, result):
    """The legacy classification report keeps its established body; the provenance table is added before its
    last section closes, as the analysis disclosure is in the library report."""
    section = _analysis_env().from_string("<div class=\"analysis-disclosure\">{% include 'provenance.html' %}</div>").render(result=result.to_dict())
    position = html.rfind("</section>")
    return html[:position] + section + html[position:]


def _with_layers(html, result):
    """The legacy classification report keeps its established body; the guidance layers are inserted at its section
    boundaries: scope and open questions after the decision summary, preprocessing guidance before methodology, and
    the score explanation and thresholds before the appendix."""
    env, value = _analysis_env(), result.to_dict()
    part = lambda body: env.from_string("{% import 'guidance_layers.html' as L %}" + body).render(result=value)
    inserts = (('<section class="action-section">', '<section class="dt-scope">{{ L.style() }}{{ L.scope_box(result.guidance) }}</section>\n'),
               ('<section class="methodology-section">', '<section class="dt-context">{{ L.context_section(result.contextual) }}</section>\n'
                                                         '<section class="dt-guidance">{{ L.guidance_section(result.guidance) }}</section>\n'),
               ('<section class="appendix-section">', '<section class="dt-scoring"><h2>Score explanation and thresholds</h2>{{ L.scoring_section(result.guidance) }}'
                                                      '{{ L.policy_table(result.guidance, result.methodology_id) }}</section>\n'))
    for anchor, body in inserts:
        position = html.find(anchor)
        if position >= 0:
            html = html[:position] + part(body) + html[position:]
    return html


def _render_analysis_result(result):
    template_dir = Path(__file__).parent / "templates"
    env = _analysis_env()
    value = result.to_dict()
    if result.schema_version == '1.7':
        from datatrust.cross_presentation import report_view
        return env.get_template('cross_report.html').render(result=value, view=report_view(result))
    if result.schema_version == '1.6':
        from datatrust.image_presentation import report_view
        return env.get_template('image_report.html').render(result=value, view=report_view(result))
    if result.schema_version == '1.5':
        from datatrust.text_presentation import report_view
        return env.get_template('text_report.html').render(result=value, view=report_view(result))
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
        legacy = result.to_legacy_dict(); legacy.pop("parsing", None)  # recorded in the JSON; the legacy HTML takes its fixed fields
        html = _with_layers(render_html_report(**legacy, generated_at=result.generated_at), result)
        disclosure = env.get_template("analysis_disclosure.html").render(result=value)
        # Keep the established eight topics and analytical body intact.
        position = html.rfind("</section>")
        return html[:position] + disclosure + html[position:]
    # Reuse the existing report's presentation rules without changing its legacy bytes.
    style = re.search(r"<style>(.*?)</style>", (template_dir / "report.html").read_text(), re.S).group(1)
    return env.get_template("regression_report.html" if result.task.kind == "regression" else "unlabeled_report.html").render(result=value, style=Markup(style))


def write_analysis_json(result, path):
    protect_source(result.source_paths, [path])
    if result.schema_version in {'1.3','1.4','1.5','1.6','1.7'}:
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
    if result.schema_version in {'1.3','1.4','1.5','1.6','1.7'}:
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
        legacy = result.to_legacy_dict(); legacy.pop("parsing", None)
        content = _with_separator_note(_with_provenance(_with_layers(render_html_report(**legacy, generated_at=result.generated_at), result), result), result).encode("utf-8")
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
    if result.schema_version == '1.5':
        from dataclasses import replace
        from datatrust.text_presentation import report_view
        artifacts = replace(artifacts,qa_metadata=report_view(result)['qa'])
    if result.schema_version == '1.6':
        from dataclasses import replace
        from datatrust.image_presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result)['qa'])
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
