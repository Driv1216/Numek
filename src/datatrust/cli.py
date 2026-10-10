import click
import json
from pathlib import Path

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
from datatrust.renderer import write_html_report
from datatrust.web import run_ui


@click.group()
def main():
    """Generate local DataTrust reliability reports."""


@main.command()
@click.argument("dataset_path")
@click.option("--target", multiple=True, help="Required classification/regression target; omitted for unlabeled profiling.")
@click.option("--task", type=click.Choice(["classification", "regression", "unlabeled", "multilabel_classification", "clustering", "anomaly_detection"]), default="classification", show_default=True)
@click.option("--out", "output_path", required=True, help="Output HTML or PDF report path.")
@click.option("--format", "report_format", type=click.Choice(["html", "pdf"]), default="html", show_default=True)
@click.option("--html-out", help="Explicit canonical HTML destination for PDF output.")
@click.option("--json-out", help="Optional strict JSON result destination.")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), help="JSON parsing, inspection, and operational safeguards.")
@click.option("--task-spec", "task_spec_path", type=click.Path(exists=True, dir_okay=False), help="JSON task, targets, roles, and group keys.")
@click.option("--name", "dataset_name", help="Optional dataset/report display name.")
@click.option("--purpose", help="Optional description of the prediction purpose.")
def audit(
    dataset_path: str,
    target: str,
    task: str,
    output_path: str,
    dataset_name: str,
    purpose: str,
    report_format: str,
    html_out: str,
    json_out: str,
    config_path: str,
    task_spec_path: str,
):
    """Audit a CSV dataset and write a discoverable report bundle."""
    try:
        config = _load_config(config_path)
        spec = DatasetSpec(dataset_path, dataset_name=dataset_name, purpose=purpose)
        if task_spec_path:
            from click.core import ParameterSource
            if target or click.get_current_context().get_parameter_source("task") != ParameterSource.DEFAULT:
                raise ValueError("--task-spec conflicts with explicit --task or --target flags.")
            task_spec = TaskSpec.from_dict(json.loads(Path(task_spec_path).read_text(encoding="utf-8")))
        else:
            task_spec = TaskSpec("dataset_profile" if task == "unlabeled" else task, targets=target)
        audit = DataTrust.from_spec(spec, task_spec, config)
        result = audit.analyze_result()
        if result.methodology_id == "classification_legacy_2026_08_13" and not task_spec_path and report_format == "html" and not config_path and not json_out and not html_out:
            # Established explicit HTML behavior remains available through the CLI.
            report_path = write_html_report(result.to_legacy_dict(), output_path)
            click.echo(f"DataTrust report written to {report_path}")
        else:
            _print_artifacts(result.generate_artifacts(output_path, format=report_format, html_path=html_out, json_path=json_out))
    except MemoryError as exc:
        raise click.ClickException("The dataset could not be analyzed with available memory. Try a smaller input or tighter limits.") from exc
    except Exception as exc:
        if getattr(exc, "artifacts", None):
            _print_artifacts(exc.artifacts)
        raise click.ClickException(str(exc)) from exc
    for warning in result.parsing_warnings:
        click.echo(f"Parsing review: {warning['code']}: {warning['interpretation']}")
    if result.coverage.get("relationship_search", {}).get("status") == "bounded":
        click.echo("Relationship search coverage is bounded by configured pool/work limits. Unsearched relationships remain unknown; see the search ledger.")
    if result.execution["status"] == "partial":
        click.echo("Analysis incomplete: review unavailable checks in the report.", err=True)
        raise click.exceptions.Exit(2)


def _load_config(path):
    if path is None:
        return None
    return AnalysisConfig.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@main.command()
@click.option('--spec', 'spec_path', required=True, type=click.Path(exists=True, dir_okay=False))
@click.option('--config', 'config_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--out', 'output_path', required=True)
@click.option('--format', 'report_format', type=click.Choice(['html','pdf']), default='html')
@click.option('--html-out')
@click.option('--json-out')
def compare(spec_path, config_path, output_path, report_format, html_out, json_out):
    """Compare declared split or version CSV sources from a local manifest."""
    from datatrust import ComparisonSpec, ComparisonConfig
    try:
        path = Path(spec_path).resolve()
        spec = ComparisonSpec.from_dict(json.loads(path.read_text(encoding='utf-8')), base_directory=path.parent)
        config = ComparisonConfig.from_dict(json.loads(Path(config_path).read_text(encoding='utf-8'))) if config_path else ComparisonConfig()
        result = DataTrust.compare(spec, config)
        _print_artifacts(result.generate_artifacts(output_path, format=report_format, html_path=html_out, json_path=json_out))
    except Exception as exc:
        if getattr(exc, 'artifacts', None): _print_artifacts(exc.artifacts)
        raise click.ClickException(str(exc)) from exc
    if result.execution['status'] == 'partial': raise click.exceptions.Exit(2)


@main.command()
@click.option('--spec','spec_path',required=True,type=click.Path(exists=True,dir_okay=False))
@click.option('--config','config_path',type=click.Path(exists=True,dir_okay=False))
@click.option('--out','output_path',required=True)
@click.option('--format','report_format',type=click.Choice(['html','pdf']),default='html')
@click.option('--html-out')
@click.option('--json-out')
def temporal(spec_path,config_path,output_path,report_format,html_out,json_out):
    """Audit local CSV/Parquet temporal sources from an explicit manifest."""
    from datatrust import TemporalAuditSpec,TemporalAnalysisConfig
    try:
        path=Path(spec_path).resolve()
        spec=TemporalAuditSpec.from_dict(json.loads(path.read_text(encoding='utf-8')),base_directory=path.parent)
        config=TemporalAnalysisConfig.from_dict(json.loads(Path(config_path).read_text(encoding='utf-8'))) if config_path else TemporalAnalysisConfig()
        result=DataTrust.audit_temporal(spec,config)
        _print_artifacts(result.generate_artifacts(output_path,format=report_format,html_path=html_out,json_path=json_out))
    except Exception as exc:
        if getattr(exc,'artifacts',None):_print_artifacts(exc.artifacts)
        raise click.ClickException(str(exc)) from exc
    if result.execution['status']=='partial':raise click.exceptions.Exit(2)


def _print_artifacts(artifacts):
    for label in ("html", "pdf", "json"):
        path = getattr(artifacts, f"{label}_path")
        if path:
            suffix = " (reused)" if label == "html" and artifacts.reused_html else ""
            click.echo(f"{label.upper()} report: {path}{suffix}")


@main.command()
@click.option(
    "--port",
    default=8000,
    show_default=True,
    type=click.IntRange(1, 65535),
    help="Loopback port for the local UI.",
)
@click.option(
    "--max-upload-mib",
    default=100.0,
    show_default=True,
    type=click.FloatRange(min=0.01),
    help="Maximum CSV upload size in MiB.",
)
@click.option("--no-open", is_flag=True, help="Do not open the default browser automatically.")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), help="Default operational and inspection settings for local UI runs.")
@click.option('--data-root', 'data_roots', multiple=True, type=click.Path(exists=True, file_okay=False), help='Allowed local CSV root; repeat for additional roots. Defaults to launch directory.')
def ui(port: int, max_upload_mib: float, no_open: bool, config_path: str, data_roots: tuple):
    """Start the local browser report generator."""
    click.echo(f"Starting DataTrust at http://127.0.0.1:{port}/")
    try:
        kwargs = {"port": port, "max_upload_mib": max_upload_mib, "open_browser": not no_open}
        if config_path:
            kwargs["analysis_config"] = _load_config(config_path)
        if data_roots: kwargs['data_roots'] = data_roots
        run_ui(**kwargs)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Local UI could not start: {exc}") from exc


if __name__ == "__main__":
    main()
