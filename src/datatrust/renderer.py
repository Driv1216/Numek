from datetime import datetime, timezone
from pathlib import Path
import re
import os
import tempfile
import hashlib

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from datatrust.wording import count_phrase
# Display formatting lives in report_format; these names stay importable from here for existing callers.
from datatrust.report_format import (  # noqa: F401
    _analysis_env, _delimiter_label, _regression_inspection_notice, _regression_population, _report_evidence_text,
    _report_label, _report_sentence, _report_time, _report_value, _separator_note, _soft_wrap_name, _with_layers,
    _with_provenance, _with_separator_note, register_filters,
)
from datatrust.report_identity import family_of


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


def presentation_identity(family=None):
    """How a report was rendered, recorded separately from the analytical methodology so a presentation change never
    reads as a method change. With a family (see report_identity.family_of) the value is that workflow's
    dependency-aware identity; `report_templates` then carries its presentation id. Without one it is the digest of
    every report template, the meaning this key had before per-workflow identity."""
    from datatrust.report_identity import all_templates_identity, identity
    if family is None:
        return all_templates_identity()
    value = identity(family)
    return {"package_version": value["package_version"], "report_templates": value["presentation_id"],
            "presentation_family": family, "print_policy": value["print_policy"]}


def _report_filters(env):
    """Report filters for page templates outside a report (the classic temporal investigate view)."""
    register_filters(env)


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


def render_analysis_result(result, *, print_profile="focused"):
    """Render only completed evidence; exports never trigger a new analysis. A source read with a separator other
    than a comma is named under the title; comma reports are unchanged, byte for byte. The print profile
    (report_print_v1: focused or complete) decides what the PDF prints of the tabular reports' per-column evidence."""
    return _with_separator_note(_render_analysis_result(result, print_profile), result)


def _interpretation(value, result):
    """interpretation_v1 for the report (Stage 6D): the same function the dashboards render, from the recorded result only."""
    from datatrust.interpretation import interpret
    return interpret(value, family_of(result))


def _render_analysis_result(result, print_profile="focused"):
    from datatrust.report_layout import PROFILES
    if print_profile not in PROFILES:
        raise ValueError(f"print_profile must be one of {', '.join(PROFILES)}.")
    env = _analysis_env(family_of(result))
    value = result.to_dict()
    if result.schema_version == '1.7':
        from datatrust.cross_presentation import report_view
        from datatrust.report_concepts import build_manifest
        view = report_view(result, print_profile)
        return env.get_template('cross_report.html').render(result=value, view=view, I=_interpretation(value, result), M=build_manifest('cross', value, view))
    if result.schema_version == '1.6':
        from datatrust.image_presentation import report_view
        from datatrust.report_concepts import build_manifest
        view = report_view(result, print_profile)
        return env.get_template('image_report.html').render(result=value, view=view, I=_interpretation(value, result), M=build_manifest('image', value, view))
    if result.schema_version == '1.5':
        from datatrust.text_presentation import report_view
        from datatrust.report_concepts import build_manifest
        view = report_view(result, print_profile)
        return env.get_template('text_report.html').render(result=value, view=view, I=_interpretation(value, result), M=build_manifest('text', value, view))
    if result.schema_version == '1.4':
        from datatrust.temporal_presentation import report_view
        from datatrust.report_concepts import build_manifest
        view = report_view(result, profile_name=print_profile)
        return env.get_template('temporal_report.html').render(result=value, view=view, I=_interpretation(value, result), M=build_manifest('temporal', value, view))
    if result.schema_version in ('1.3', '1.2'):
        from datatrust.report_concepts import build_manifest
        if result.schema_version == '1.3':
            from datatrust.m4_presentation import report_view
        else:
            from datatrust.presentation import report_view
        view = report_view(result, print_profile)
        manifest = build_manifest(family_of(result), value, view)
        return env.get_template('m4_report.html' if result.schema_version == '1.3' else 'm3_report.html').render(result=value, view=view, I=_interpretation(value, result), M=manifest)
    from datatrust.tabular_presentation import report_view as tabular_view
    from datatrust.report_concepts import build_manifest
    view = tabular_view(value, print_profile)
    manifest = build_manifest(family_of(result), value, view)
    if result.methodology_id == "classification_legacy_2026_08_13":
        # The current classification report; the frozen legacy report.html stays with render_html_report.
        return env.get_template("classification_report.html").render(result=value, view=view, I=_interpretation(value, result), M=manifest)
    return env.get_template("regression_report.html" if result.task.kind == "regression" else "unlabeled_report.html").render(result=value, view=view, I=_interpretation(value, result), M=manifest)


def write_analysis_json(result, path):
    protect_source(result.source_paths, [path])
    if result.schema_version in {'1.3','1.4','1.5','1.6','1.7'}:
        from datatrust.scalable import available
        if available(Path(path).parent) < result.execution['effective_limits']['free_disk_bytes'] + 256 * 1024**2:
            raise ValueError('Output filesystem lacks the 256 MiB export reservation plus configured free-space reserve.')
    _new_destination(path)
    return publish_bytes(path, result.json_text().encode("utf-8"))


COMPLETE_PRINT_WARNING_ROWS = 5000


class CompletePrintWarning(UserWarning):
    """The complete print profile is about to print a very large number of table rows."""


def _warn_complete_cost(content):
    """The complete profile prints every row, so PDF time and memory grow with the evidence (measured on 5,000
    columns: 564 pages, about 49 s and 2.9 GiB peak). Say so before converting; the focused profile is unaffected."""
    import warnings
    rows = content.count(b"<tr")
    if rows > COMPLETE_PRINT_WARNING_ROWS:
        warnings.warn(f"The complete print profile will print about {rows:,} table rows. PDF time and memory grow with "
                      "the rows printed (5,000 columns measured about 49 s and 2.9 GiB). The focused profile prints every "
                      "finding and flagged row, and the HTML report lists every row.", CompletePrintWarning, stacklevel=3)


def write_report_artifacts(result, path, *, format="html", html_path=None, json_path=None,
                           pdf_converter=None, legacy_html=False, print_profile="focused"):
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
        content = render_analysis_result(result, print_profile=print_profile).encode("utf-8")
    if pdf_path is not None and print_profile == "complete":
        _warn_complete_cost(content)
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
    if result.schema_version in {"1.0", "1.1"} and not legacy_html:
        from dataclasses import replace
        from datatrust.tabular_presentation import report_view as tabular_view
        artifacts = replace(artifacts, qa_metadata=tabular_view(result.to_dict(), print_profile)["qa"])
    if result.schema_version == "1.2":
        from dataclasses import replace
        from datatrust.presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result, print_profile)["qa"])
    if result.schema_version == "1.3":
        from dataclasses import replace
        from datatrust.m4_presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result, print_profile)["qa"])
    if result.schema_version == "1.4":
        from dataclasses import replace
        from datatrust.temporal_presentation import report_view
        artifacts = replace(artifacts,qa_metadata=report_view(result, profile_name=print_profile)["qa"])
    if result.schema_version == '1.5':
        from dataclasses import replace
        from datatrust.text_presentation import report_view
        artifacts = replace(artifacts,qa_metadata=report_view(result, print_profile)['qa'])
    if result.schema_version == '1.7':
        from dataclasses import replace
        from datatrust.cross_presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result, print_profile)['qa'])
    if result.schema_version == '1.6':
        from dataclasses import replace
        from datatrust.image_presentation import report_view
        artifacts = replace(artifacts, qa_metadata=report_view(result, print_profile)['qa'])
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
