import click

from datatrust import DataTrust


@click.group()
def main():
    """Generate local DataTrust reliability reports."""


@main.command()
@click.argument("dataset_path")
@click.option("--target", required=True, help="Target column name.")
@click.option("--task", default="classification", show_default=True, help="ML task type.")
@click.option("--out", "output_path", required=True, help="Output HTML report path.")
def audit(dataset_path: str, target: str, task: str, output_path: str):
    """Audit a CSV dataset and write an HTML report."""
    try:
        report_path = DataTrust(dataset_path, target=target, task=task).generate_report(output_path)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"DataTrust report written to {report_path}")


if __name__ == "__main__":
    main()

