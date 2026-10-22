"""CSV loading and bounded, non-destructive source interpretation review."""

import codecs
import csv
import hashlib
import io
import json
import re
import warnings
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pandas as pd

from datatrust.contracts import AnalysisError, CsvParseOptions, omit_default_delimiter


@dataclass
class DatasetHandle:
    data: pd.DataFrame
    source: dict
    parsing: dict
    parsing_warnings: list
    frame_bytes: int


def source_signature(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def source_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "vertical bar"}


def delimiter_name(delimiter):
    return DELIMITER_NAMES.get(delimiter, repr(delimiter))


CANDIDATE_DELIMITERS = (",", ";", "\t", "|")


def delimiter_candidates(path, encoding="utf-8"):
    """The candidate separators that read a bounded sample as at least two columns of one width: the header and
    every sampled complete record, under strict CSV quoting."""
    from datatrust.contracts import FidelityInspectionLimits
    limits = FidelityInspectionLimits(max_bytes=65536, max_records=50, max_cells=20000)
    found = []
    for delimiter in CANDIDATE_DELIMITERS:
        try:
            sample = inspect_source_tokens(path, encoding, limits, delimiter)
        except (OSError, UnicodeError, csv.Error, ValueError):
            continue
        if sample["headers"] is None or len(sample["headers"]) < 2:
            continue
        width = len(sample["headers"])
        if sample["records"] and all(r["width"] == width for r in sample["records"]):
            found.append(delimiter)
    return found


def detect_delimiter(path, encoding="utf-8"):
    """The separator a CSV evidently uses: the one candidate that fits (see delimiter_candidates), or comma when
    none does (a genuine single column, or a file no candidate reads cleanly). None when two or more fit: the
    reading is ambiguous and the separator must be chosen explicitly. Never a guess."""
    found = delimiter_candidates(path, encoding)
    if len(found) > 1:
        return None
    return found[0] if found else ","


def ambiguous_delimiter_message(path, encoding="utf-8"):
    names = [delimiter_name(d) for d in delimiter_candidates(path, encoding)]
    return (f"This file reads consistently with more than one separator ({' and '.join(names)}). "
            "Choose its separator explicitly; nothing was analysed.")


def resolve_delimiter(path, choice, encoding="utf-8"):
    """A declared separator, or "auto": the detected one. Raises ValueError when detection is ambiguous."""
    if choice != "auto":
        return choice
    found = detect_delimiter(path, encoding)
    if found is None:
        raise ValueError(ambiguous_delimiter_message(path, encoding))
    return found


STRUCTURE_VALIDATION = "complete_source_width_v1"
STRUCTURE_CHECKPOINT_RECORDS = 100_000


def validate_csv_structure(path, options=None, *, max_rows=None, checkpoint=None):
    """Every logical record of the whole source has its header's width, read with the selected encoding and
    separator. Rows are never padded, dropped or re-interpreted as an index.

    Matches pandas.read_csv defaults: double-quote quoting with doubled quotes, quoted separators and line breaks,
    a leading byte-order mark, and skip_blank_lines (a line of only spaces and tabs, other than the separator
    itself, is blank). Streaming: memory holds one logical record. Stops after max_rows + 1 data records, where
    the established row limit takes over, and calls checkpoint periodically so the analysis deadline applies.
    Returns the number of data records validated."""
    import sys
    options = options or CsvParseOptions()
    delimiter = options.delimiter
    blank_chars = " \t\r\n".replace(delimiter, "") if delimiter in " \t" else " \t\r\n"
    name = delimiter_name(delimiter)
    buffer = []

    def lines(handle):
        for line in handle:
            buffer.append(line)
            yield line

    previous_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)  # pandas bounds no field length; resource limits apply to the source.
    try:
        with Path(path).open(encoding=options.encoding, errors="strict", newline="") as handle:
            reader = csv.reader(lines(handle), delimiter=delimiter)
            width = None
            count = 0
            mismatch = None
            for row in reader:
                text = "".join(buffer)
                buffer.clear()
                if width is None and text.startswith("﻿"):
                    text = text[1:]
                    if row and row[0].startswith("﻿"):
                        row[0] = row[0][1:]
                if not row or (all(not field.strip(blank_chars) for field in row) and not text.strip(blank_chars)):
                    continue
                if width is None:
                    width = len(row)
                    continue
                count += 1
                if len(row) != width:
                    if count == 1 and len(row) == width + 1:
                        mismatch = (count, reader.line_num, len(row))  # Possibly an implicit index: keep looking.
                    elif mismatch is None or len(row) != width + 1:
                        raise _width_error(count, reader.line_num, len(row), width, name)
                elif mismatch is not None:
                    raise _width_error(*mismatch, width, name)
                if max_rows is not None and count > max_rows:
                    break
                if checkpoint is not None and count % STRUCTURE_CHECKPOINT_RECORDS == 0:
                    checkpoint("CSV structure validation")
            if mismatch is not None:
                raise AnalysisError(
                    f"Every record has {width + 1} fields but the header has {width}, so the first field would "
                    "silently become a row index. Add a header name for the first column, or check the separator "
                    f"({name}). Nothing was analysed.", code="csv_structure", stage="CSV structure validation")
            return count
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use a text encoding that pandas can read (UTF-8 recommended).") from exc
    except csv.Error as exc:
        raise ValueError(f"CSV could not be parsed as a {name}-delimited file with a header.") from exc
    finally:
        csv.field_size_limit(previous_limit)


def _width_error(record, line, found, width, name):
    return AnalysisError(
        f"CSV record {record} (ending on line {line}) has {found} field{'s' if found != 1 else ''}; the header has "
        f"{width}. Records are never padded or dropped. Check the separator ({name}) and quoting, or repair that "
        "record. Nothing was analysed.", code="csv_structure", stage="CSV structure validation")


def verify_source(path, source, stage="source verification"):
    try:
        unchanged = (source_signature(path) == source["signature"] and source_digest(path) == source["sha256"])
    except OSError:
        unchanged = False
    if not unchanged:
        raise AnalysisError("Source changed during analysis; no mixed-snapshot result was produced.", code="source_changed", stage=stage)


def read_csv(dataset_path, *, usecols=None, nrows=None, options=None):
    """Keep the established default pandas call and product error translations."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if not path.is_file():
        raise ValueError(f"Dataset path is not a file: {path}")
    if options is not None and options.column_missing_policies:
        raise ValueError("Per-column missing policies require scalable execution.")
    kwargs = {"usecols": usecols, "nrows": nrows}
    if options is not None and options != CsvParseOptions():
        kwargs["encoding"] = options.encoding
        if options.delimiter != ",":
            kwargs["sep"] = options.delimiter
        if options.missing_policy != "pandas_default":
            kwargs["keep_default_na"] = False
            kwargs["na_values"] = [""] if options.missing_policy == "empty_only" else list(options.na_values)
        # Read numeric overrides as strings first, then require conversion.
        kwargs["dtype"] = {name: "string" for name in options.column_types}
    try:
        data = pd.read_csv(path, **kwargs)
        if options is not None:
            unknown = set(options.column_types) - set(data.columns)
            if unknown:
                raise ValueError("Unknown column type overrides: " + ", ".join(sorted(unknown)))
            for name, kind in options.column_types.items():
                if kind == "numeric":
                    try:
                        data[name] = pd.to_numeric(data[name], errors="raise")
                    except (ValueError, TypeError) as exc:
                        raise ValueError(f"Column '{name}' contains invalid numeric values; no values were coerced to missing.") from exc
        return data
    except pd.errors.EmptyDataError as exc:
        raise ValueError("Dataset is empty and cannot be analyzed.") from exc
    except pd.errors.ParserError as exc:
        name = delimiter_name(options.delimiter if options is not None else ",")
        raise ValueError(f"CSV could not be parsed as a {name}-delimited file with a header.") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use a text encoding that pandas can read (UTF-8 recommended).") from exc
    except PermissionError as exc:
        raise ValueError(f"Dataset cannot be read: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Dataset could not be read: {exc}") from exc


def inspect_source_tokens(path, encoding, limits, delimiter=","):
    """Only complete logical records are retained; counts describe a prefix."""
    result = {"headers": None, "records": [], "bytes_inspected": 0, "records_inspected": 0,
              "cells_retained": 0, "complete": False, "stopping_reason": "eof"}
    try:
        size = Path(path).stat().st_size
        with Path(path).open("rb") as handle:
            raw = handle.read(limits.max_bytes)
        result["bytes_inspected"] = len(raw)
        truncated = len(raw) < size
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        text = decoder.decode(raw, final=not truncated)
        if text.startswith("\ufeff"):
            text = text[1:]
        lines = io.StringIO(text, newline="").readlines()
        reader = csv.reader(io.StringIO(text, newline=""), strict=True, delimiter=delimiter)
        previous_line = 0
        for tokens in reader:
            record_text = "".join(lines[previous_line:reader.line_num])
            previous_line = reader.line_num
            if truncated and reader.line_num == len(lines) and not text.endswith(("\n", "\r")):
                result["stopping_reason"] = "byte_limit_incomplete_record"
                return result
            if not record_text.strip(" \t\r\n"):
                continue  # Match default skip_blank_lines without skipping quoted whitespace.
            if result["headers"] is None:
                result["headers"] = tokens
                continue
            if result["records_inspected"] >= limits.max_records:
                result["stopping_reason"] = "record_limit"
                return result
            remaining = limits.max_cells - result["cells_retained"]
            if remaining <= 0:
                result["stopping_reason"] = "cell_limit"
                return result
            retained = tokens[:remaining]
            result["records"].append({"row": result["records_inspected"] + 1,
                                       "width": len(tokens), "tokens": retained})
            result["records_inspected"] += 1
            result["cells_retained"] += len(retained)
            if len(retained) < len(tokens):
                result["stopping_reason"] = "cell_limit"
                return result
            if result["records_inspected"] >= limits.max_records or result["cells_retained"] >= limits.max_cells:
                result["complete"] = reader.line_num == len(lines) and not truncated
                result["stopping_reason"] = ("eof" if result["complete"] else
                    "record_limit" if result["records_inspected"] >= limits.max_records else "cell_limit")
                return result
        result["complete"] = not truncated
        result["stopping_reason"] = "byte_limit" if truncated else "eof"
    except (UnicodeError, csv.Error, LookupError, OSError) as exc:
        # Optional review must never change classification parser acceptance.
        result["stopping_reason"] = "inspection_unavailable"
        result["limitation"] = type(exc).__name__ + ": bounded source inspection could not continue."
    return result


def review_tokens(sample, data, options, source_hash, fingerprint):
    headers = sample["headers"]
    mapping = []
    review = []
    counts = {}
    comparable = 0
    alignment = headers is not None and len(headers) == len(data.columns) and data.index.equals(pd.RangeIndex(len(data)))
    if sample["complete"] and sample["records_inspected"] != len(data):
        alignment = False

    def warn(code, column, description, *, count=1, row_refs=None, setting="inference", position=None):
        review.append({"code": code, "column": column, "header_position": position,
                       "interpretation": description, "observed_count": count,
                       "row_refs": row_refs or [], "setting": setting,
                       "evidence_type": "interpretation_review_warning",
                       "recommendation": "Confirm this interpretation matches the source meaning; use an explicit parsing override where appropriate.",
                       "scope": "bounded source inspection; counts are not dataset-wide incidence"})

    if headers is not None:
        header_counts = Counter(headers)
        for index, original in enumerate(headers):
            resolved = str(data.columns[index]) if index < len(data.columns) else None
            mapping.append({"position": index + 1, "original": original, "resolved": resolved})
            if not original:
                warn("empty_header", resolved, "An empty header was assigned a parser-generated name.", setting="pandas_header_default", position=index + 1)
            elif header_counts[original] > 1:
                warn("duplicate_header", resolved, "A repeated source header requires position-based disambiguation; resolved names may differ.", setting="pandas_header_default", position=index + 1)

    if alignment:
        for record in sample["records"]:
            if record["row"] > len(data) or record["width"] != len(headers):
                alignment = False
                break
        if alignment:
            for record in sample["records"]:
                for index, token in enumerate(record["tokens"]):
                    column = str(data.columns[index])
                    value = data.iloc[record["row"] - 1, index]
                    comparable += 1
                    code = None
                    if token and pd.isna(value):
                        code = "nonempty_token_as_missing"
                    elif (re.fullmatch(r"[ \t]*[+-]?0\d+(?:\.\d*)?(?:[eE][+-]?\d+)?[ \t]*", token)
                          and pd.api.types.is_number(value) and not pd.api.types.is_bool_dtype(data[column])):
                        code = "leading_zero_numeric_conversion"
                    if code:
                        key = (code, column)
                        item = counts.setdefault(key, {"count": 0, "refs": []})
                        item["count"] += 1
                        if len(item["refs"]) < 5:
                            item["refs"].append({"source_sha256": source_hash, "parsing_fingerprint": fingerprint,
                                                 "parsed_row": record["row"]})
            for (code, column), item in counts.items():
                description = ("Nonempty source tokens became missing values under the selected missing-value policy."
                               if code == "nonempty_token_as_missing" else
                               "Source tokens with leading zeros became numbers, losing their original textual representation.")
                setting = options.missing_policy if code == "nonempty_token_as_missing" else options.column_types.get(column, "inference")
                warn(code, column, description, count=item["count"], row_refs=item["refs"], setting=setting)
    if not alignment:
        warn("token_alignment_ambiguous", None, "Source-token positions could not be aligned confidently; no token conversions were inferred.", count=0)
    if not sample["complete"]:
        warn("inspection_incomplete", None, "Inspection stopped at " + sample["stopping_reason"] + "; absence of warnings does not establish losslessness.", count=0)
    scope = {k: v for k, v in sample.items() if k not in {"records", "headers"}}
    scope.update({"comparable_cells": comparable, "alignment_confirmed": alignment,
                  "counts_are_dataset_incidence": False})
    for warning in review:
        warning["inspected_population"] = dict(scope)
    return mapping, review, scope


def load_dataset(dataset, task, config, limits, checkpoint, *, preview_rows=None, prepare=None):
    path = Path(dataset.path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if not path.is_file():
        raise ValueError(f"Dataset path is not a file: {path}")
    if prepare is not None:
        task, config, limits = prepare(list(read_csv(path, nrows=0, options=config.parsing).columns))
    before = source_signature(path)
    source_bytes = before[2]
    if limits.max_source_bytes is not None and source_bytes > limits.max_source_bytes:
        raise AnalysisError("Source exceeds max_source_bytes before parsing.", code="resource_limit", stage="source")
    checkpoint("source inspection")
    try:
        digest = source_digest(path)
    except PermissionError as exc:
        raise ValueError(f"Dataset cannot be read: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Dataset could not be read: {exc}") from exc
    inspection_limits = config.fidelity_inspection
    if preview_rows is not None:
        inspection_limits = replace(inspection_limits, max_records=min(inspection_limits.max_records, preview_rows))
    # Comma files keep the established call exactly; another separator is passed through.
    sample = (inspect_source_tokens(path, config.parsing.encoding, inspection_limits) if config.parsing.delimiter == ","
              else inspect_source_tokens(path, config.parsing.encoding, inspection_limits, config.parsing.delimiter))
    if limits.max_columns is not None:
        # Header-only pandas parsing is authoritative if bounded review could not obtain it.
        width = len(sample["headers"]) if sample["headers"] is not None else len(read_csv(path, nrows=0, options=config.parsing).columns)
        if width > limits.max_columns:
            raise AnalysisError("Header exceeds max_columns before data parsing.", code="resource_limit", stage="header")
    checkpoint("CSV structure validation")
    validated = validate_csv_structure(path, config.parsing, max_rows=limits.max_rows, checkpoint=checkpoint)
    checkpoint("CSV loading")
    nrows = limits.max_rows + 1 if limits.max_rows is not None else None
    if preview_rows is not None:
        nrows = min(nrows, preview_rows) if nrows is not None else preview_rows
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", pd.errors.ParserWarning)
        data = read_csv(path, nrows=nrows, options=config.parsing)
    if limits.max_rows is not None and len(data) > limits.max_rows:
        raise AnalysisError("Dataset exceeds max_rows; the bounded read is not a complete analysis.", code="resource_limit", stage="CSV loading")
    if preview_rows is None and len(data) != validated:
        # Two independent readings must agree; a disagreement (seen with lone carriage-return line endings and
        # quoted line breaks) means the records cannot be trusted to be what the file holds.
        raise AnalysisError(f"The CSV reader found {len(data)} records but structural validation found {validated}, so "
                            "the file's line endings or quoting are read inconsistently. Re-save it with standard line "
                            "endings (LF or CRLF). Nothing was analysed.", code="csv_structure", stage="CSV structure validation")
    if len(data) == 0:
        # Classification target validation keeps its established ordering in the profiler.
        if task.kind != "classification":
            raise ValueError("Dataset is empty and cannot be analyzed.")
    if task.kind != "classification" and not data.index.equals(pd.RangeIndex(len(data))):
        raise ValueError("CSV produced an implicit index; repair mismatched record/header widths before profiling.")
    frame_bytes = int(data.memory_usage(index=True, deep=True).sum())
    if limits.max_frame_bytes is not None and frame_bytes > limits.max_frame_bytes:
        raise AnalysisError("Loaded DataFrame exceeds max_frame_bytes. This post-load safeguard is not a peak-memory guarantee.", code="resource_limit", stage="materialization")
    effective = {"options": parsing_options_dict(config.parsing), "pandas_version": pd.__version__, "parser": "pandas.read_csv",
                 "delimiter": config.parsing.delimiter, "header": "infer", "skip_blank_lines": True,
                 "dtypes": {str(name): str(dtype) for name, dtype in data.dtypes.items()},
                 "provisional_types": preview_rows is not None}
    fingerprint = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
    mapping, review, scope = review_tokens(sample, data, config.parsing, digest, fingerprint)
    for warning in caught:
        review.append({"code": "parser_warning", "column": None, "observed_count": 0,
                       "interpretation": "The CSV parser issued a structural warning; review source record widths.",
                       "evidence_type": "interpretation_review_warning", "setting": "pandas_default",
                       "inspected_population": scope, "row_refs": [],
                       "recommendation": "Review the source format; parser warnings do not establish a data defect."})
    # Recorded after the fingerprint: valid files keep the fingerprints and seals they had before validation.
    effective.update({"structure_validation": STRUCTURE_VALIDATION, "header_mapping": mapping, "fidelity_inspection": scope,
                      "inspection_limits": asdict(config.fidelity_inspection), "fingerprint": fingerprint,
                      "inference_caution": "NA-like tokens may become missing; numeric-looking codes may lose leading zeros. No source values were rewritten."})
    checkpoint("materialization")
    source = {"sha256": digest, "signature": before, "bytes": source_bytes}
    verify_source(path, source)
    return DatasetHandle(data, source, effective, review, frame_bytes)


def inspect_unlabeled_dataset(dataset, config=None, *, regression_guidance=False):
    from datatrust.contracts import AnalysisConfig, ExecutionLimits, TaskSpec
    from time import monotonic
    config = config or AnalysisConfig()
    limits = config.limits or ExecutionLimits.unlabeled_defaults()
    start = monotonic()

    def checkpoint(stage):
        if limits.max_seconds is not None and monotonic() - start > limits.max_seconds:
            raise AnalysisError(f"Cooperative elapsed-time safeguard reached after {stage}.", code="resource_limit", stage=stage)

    handle = load_dataset(dataset, TaskSpec("dataset_profile"), config, limits, checkpoint, preview_rows=10)
    preview = [{str(k): "" if pd.isna(v) else str(v) for k, v in row.items()}
               for row in handle.data.to_dict(orient="records")]
    target_options = []
    if regression_guidance:
        from datatrust.target_guidance import assess_regression_target
        target_options = [assess_regression_target(handle.data[c], c) for c in handle.data.columns]
        verify_source(dataset.path, handle.source)
    return {"row_count": None, "preview_row_count": len(preview), "column_count": len(handle.data.columns),
            "columns": list(handle.data.columns), "preview": preview, "target_options": target_options,
            "parsing": handle.parsing, "parsing_warnings": handle.parsing_warnings, "limits": asdict(limits)}


def inspect_regression_dataset(dataset, config=None):
    return inspect_unlabeled_dataset(dataset, config, regression_guidance=True)


def inspect_regression_target(dataset, target, config=None):
    """Full confirmation through shared safeguarded ingestion, no saved frame."""
    from datatrust.contracts import AnalysisConfig, RegressionOptions, TaskSpec, ExecutionLimits
    from datatrust.regression import validate_target, target_evidence, constraint_evidence
    from datatrust.target_guidance import assess_regression_target
    from time import monotonic
    config = config or AnalysisConfig()
    options = config.regression or RegressionOptions()
    start = monotonic()
    limits = config.limits or ExecutionLimits.unlabeled_defaults()
    def checkpoint(stage):
        if limits.max_seconds is not None and monotonic() - start > limits.max_seconds:
            raise AnalysisError(f'Cooperative elapsed-time safeguard reached after {stage}.', code='resource_limit', stage=stage)
    handle = load_dataset(dataset, TaskSpec('regression', target), config, limits, checkpoint)
    validate_target(handle.data, target, options)
    info = {'target':target, 'statistics':target_evidence(handle.data[target], options.expectations),
            'constraints':constraint_evidence(handle.data[target], options.expectations),
            'suitability':assess_regression_target(handle.data[target], target, options.expectations.kind),
            'source_sha256':handle.source['sha256'], 'parsing_fingerprint':handle.parsing['fingerprint']}
    checkpoint('target confirmation')
    verify_source(dataset.path, handle.source)
    return info


def parsing_options_dict(options):
    value = omit_default_delimiter(asdict(options))
    if not value["column_missing_policies"]:
        value.pop("column_missing_policies")
    return value
