import click

from datatrust import DataTrust
from datatrust.web import run_ui


@click.group()
def main():
    """Generate local DataTrust reliability reports."""


@main.command()
@click.argument("dataset_path")
@click.option("--target", required=True, help="Target column name.")
@click.option("--task", default="classification", show_default=True, help="ML task type.")
@click.option("--out", "output_path", required=True, help="Output HTML report path.")
@click.option("--name", "dataset_name", help="Optional dataset/report display name.")
@click.option("--purpose", help="Optional description of the prediction purpose.")
def audit(
    dataset_path: str,
    target: str,
    task: str,
    output_path: str,
    dataset_name: str,
    purpose: str,
):
    """Audit a CSV dataset and write an HTML report."""
    try:
        report_path = DataTrust(
            dataset_path,
            target=target,
            task=task,
            dataset_name=dataset_name,
            purpose=purpose,
        ).generate_report(output_path)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"DataTrust report written to {report_path}")


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
def ui(port: int, max_upload_mib: float, no_open: bool):
    """Start the local browser report generator."""
    click.echo(f"Starting DataTrust at http://127.0.0.1:{port}/")
    try:
        run_ui(port=port, max_upload_mib=max_upload_mib, open_browser=not no_open)
    except OSError as exc:
        raise click.ClickException(f"Local UI could not start: {exc}") from exc


if __name__ == "__main__":
    main()
