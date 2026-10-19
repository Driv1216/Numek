"""Thin command-line client for the independent ConfidenceGuard application services."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import click
from .contracts import EvaluationSpec,EvaluationConfig,DisclosureSpec,strict_json
from .method_contracts import parse_spec
from .engine import evaluate,inspect
from .result import EvaluationResult


def load(path):return strict_json(Path(path).read_text(encoding='utf-8'))
def specifications(path,config):
    p=Path(path).resolve();return parse_spec(load(p),base_directory=p.parent),EvaluationConfig.from_dict(load(config)) if config else EvaluationConfig()


@click.group()
def main():
    """Evaluate local prediction artifacts; no model execution or universal trust score."""


@main.command('inspect')
@click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
@click.option('--config',type=click.Path(exists=True,dir_okay=False))
def inspect_command(spec,config):
    try:
        s,c=specifications(spec,config);click.echo(json.dumps(inspect(s,c),indent=2,allow_nan=False))
    except Exception as exc:raise click.ClickException(f'{getattr(exc,"code","inspection_failed")}: {exc}') from exc


@main.command('evaluate')
@click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
@click.option('--config',type=click.Path(exists=True,dir_okay=False))
@click.option('--out',required=True,type=click.Path())
@click.option('--format','report_format',type=click.Choice(['html','pdf']),default='html')
@click.option('--html-out',type=click.Path())
@click.option('--json-out',type=click.Path())
@click.option('--audience',type=click.Choice(['shareable','local']),default='shareable')
@click.option('--disclosure',type=click.Path(exists=True,dir_okay=False))
def evaluate_command(spec,config,out,report_format,html_out,json_out,audience,disclosure):
    try:
        s,c=specifications(spec,config);r=evaluate(s,c)
        artifacts=r.generate_artifacts(out,format=report_format,html_path=html_out,json_path=json_out,audience=audience,disclosure=DisclosureSpec.from_dict(load(disclosure)) if disclosure else None)
        click.echo(json.dumps(asdict(artifacts),indent=2))
    except Exception as exc:
        if getattr(exc,'artifacts',None):click.echo(json.dumps(asdict(exc.artifacts),indent=2))
        raise click.ClickException(f'{getattr(exc,"code","evaluation_or_export_failed")}: {exc}') from exc


@main.command('evidence')
@click.option('--report',required=True,type=click.Path(exists=True,dir_okay=False))
@click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
@click.option('--reference',required=True)
@click.option('--allowed-root',multiple=True,required=True,type=click.Path(exists=True,file_okay=False))
@click.option('--reveal-values',is_flag=True)
def evidence_command(report,manifest,reference,allowed_root,reveal_values):
    try:
        result=EvaluationResult.from_dict(load(report),private=load(manifest))
        click.echo(json.dumps(result.resolve_evidence(reference,allowed_roots=allowed_root,reveal_values=reveal_values),indent=2))
    except Exception as exc:raise click.ClickException(f'{getattr(exc,"code","evidence_unavailable")}: {exc}') from exc


@main.command('ui')
@click.option('--port',default=8000,type=click.IntRange(1,65535))
@click.option('--data-root',multiple=True,type=click.Path(exists=True,file_okay=False))
def ui_command(port,data_root):
    """Start the loopback host; the workbench is at /confidenceguard."""
    from datatrust.web import create_app
    with tempfile.TemporaryDirectory(prefix='confidenceguard-ui-') as directory:
        app=create_app(Path(directory),data_roots=tuple(Path(p) for p in data_root) or (Path.cwd(),))
        click.echo(f'ConfidenceGuard: http://127.0.0.1:{port}/confidenceguard')
        try:app.run(host='127.0.0.1',port=port,debug=False,use_reloader=False,threaded=False)
        finally:
            for key,value in app.extensions.items():
                if key.endswith('_store') and hasattr(value,'cleanup'):value.cleanup()


from .method_cli import register as _register_methods
_register_methods(main)

if __name__=='__main__':main()
