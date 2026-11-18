"""Report display formatting shared by every DataTrust report: filters, the Jinja environment and the classification
report's section insertions. Moved verbatim from renderer.py so that a report's presentation identity depends on what
formats it, not on artifact publication code. Nothing here computes evidence; values are only formatted for display.
"""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import base64
import hashlib
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from datatrust.wording import count_phrase


REPORT_SCRIPT = Path(__file__).parent / "templates" / "_report_script.js.html"


@lru_cache(maxsize=1)
def report_script():
    """The single executable script a report may carry, and its CSP source. Read as bytes, never through Jinja, so
    the hash always matches what is embedded."""
    text = REPORT_SCRIPT.read_text(encoding="utf-8")
    digest = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode()
    return text, f"'sha256-{digest}'"


def report_csp():
    """The report Content Security Policy (Stage 0 spike e): no network, data: images, inline styles, and only the
    report's own hashed script."""
    return f"default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src {report_script()[1]}"


def register_filters(env, family=None):
    """The filters every report template uses, and the provenance line naming how this family's report is rendered.
    Without a family the line names the digest of every template, as before per-workflow identity existed."""
    from datatrust.report_identity import presentation_line, legacy_presentation_line
    env.filters["report_time"] = _report_time
    env.filters.setdefault("report_label", _report_label)
    env.filters["delimiter_label"] = _delimiter_label
    env.filters["long_list"] = long_list
    env.filters.setdefault("soft_wrap_name", _soft_wrap_name)
    env.globals["presentation"] = presentation_line(family) if family else legacy_presentation_line()
    env.globals["report_script"] = Markup(report_script()[0])
    env.globals["report_csp"] = report_csp()
    from datatrust.report_identity import PRINT_POLICY_VERSION
    env.globals["print_policy"] = PRINT_POLICY_VERSION


LONG_LIST_MIN, LONG_LIST_KEEP = 20, 12
_LONG_LIST = re.compile(r'(?:[^,;:]{1,80}, ){%d,}[^,;:.]{1,80}' % (LONG_LIST_MIN - 1))


def long_list(text):
    """Recorded analysis text with a very long comma-separated list of names (a guardrail listing 400 columns, say).
    The screen keeps the text exactly as recorded. Print shows the first names and a disclosed count of the rest
    (R4 identity-only summary), so a recorded sentence cannot fill pages with names already listed in the report."""
    text = '' if text is None else str(text)
    parts, last = [], 0
    for match in _LONG_LIST.finditer(text):
        items = match.group(0).split(', ')
        if len(items) < LONG_LIST_MIN:
            continue
        parts.append(escape(text[last:match.start()]))
        parts.append(Markup('{}<span class="dt-screen-only">, {}</span><span class="dt-print-only"> … and {} more (every name '
                            'is listed on screen and in analysis.json)</span>').format(
            ', '.join(items[:LONG_LIST_KEEP]), ', '.join(items[LONG_LIST_KEEP:]), f'{len(items) - LONG_LIST_KEEP:,}'))
        last = match.end()
    parts.append(escape(text[last:]))
    return Markup('').join(parts)


def _report_time(value):
    """A report timestamp with its time zone stated: UTC when the canonical value carries an offset."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is None:
        return moment.strftime("%Y-%m-%d %H:%M:%S") + " (time zone not recorded)"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _delimiter_label(value):
    from datatrust.ingestion import delimiter_name
    name = delimiter_name(value or ",")
    return name[:1].upper() + name[1:]


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


def _soft_wrap_name(value: str) -> Markup:
    """Add safe wrap opportunities at semantic name boundaries."""
    parts = re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[_-])", str(value))
    return Markup("<wbr>".join(str(escape(part)) for part in parts))


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


def _analysis_env(family=None):
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
    register_filters(env, family)
    env.filters["regression_number"] = lambda value: "Unavailable" if value is None else (format(value, ".8g") if isinstance(value, float) else str(value))
    return env


def _with_provenance(html, result):
    """The legacy classification report keeps its established body; the provenance table is added before its
    last section closes, as the analysis disclosure is in the library report."""
    section = _analysis_env('classification').from_string("<div class=\"analysis-disclosure\">{% include 'provenance.html' %}</div>").render(result=result.to_dict())
    position = html.rfind("</section>")
    return html[:position] + section + html[position:]


def _with_layers(html, result):
    """The legacy classification report keeps its established body; the guidance layers are inserted at its section
    boundaries: scope and open questions after the decision summary, preprocessing guidance before methodology, and
    the score explanation and thresholds before the appendix."""
    env, value = _analysis_env('classification'), result.to_dict()
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
