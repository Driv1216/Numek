"""Thin command-line workspace client; no analytical implementations."""
from dataclasses import asdict
import json
from pathlib import Path
import click
from .contracts import EvaluationConfig, strict_json
from .history_contracts import WorkspaceConfig, PredictionBatchSpec, OutcomeRevisionSpec
from .workspace import ReliabilityWorkspace


def load(path): return strict_json(Path(path).read_bytes())
def emit(value): click.echo(json.dumps(value, indent=2, allow_nan=False))


def guarded(function):
    import functools
    @functools.wraps(function)
    def call(*args, **kwargs):
        try: return function(*args, **kwargs)
        except Exception as exc:
            if isinstance(exc, click.ClickException): raise
            raise click.ClickException(f'{getattr(exc, "code", "workspace_operation_failed")}: {exc}') from exc
    return call


def register(main):
    @main.group('workspace')
    @click.option('--path', required=True, type=click.Path(file_okay=False))
    @click.pass_context
    def workspace(ctx, path):
        """Explicit local evidence persistence and longitudinal assessments."""
        ctx.obj = Path(path).absolute()

    @workspace.command('init')
    @click.option('--enable-saving', is_flag=True)
    @click.option('--config', type=click.Path(exists=True, dir_okay=False))
    @click.pass_obj
    @guarded
    def initialize(path, enable_saving, config):
        settings = load(config) if config else {}
        if enable_saving: settings['saving'] = True
        emit(ReliabilityWorkspace.initialize(path, WorkspaceConfig.from_dict(settings)).status())

    @workspace.command('status')
    @click.pass_obj
    @guarded
    def status(path): emit(ReliabilityWorkspace(path).status())

    @workspace.command('models')
    @click.pass_obj
    @guarded
    def models(path): emit(ReliabilityWorkspace(path).models())

    @workspace.command('saving')
    @click.argument('choice', type=click.Choice(['on', 'off']))
    @click.pass_obj
    @guarded
    def saving(path, choice): emit(ReliabilityWorkspace(path).set_saving(choice == 'on'))

    def import_command(kind):
        @click.option('--spec', required=True, type=click.Path(exists=True, dir_okay=False))
        @click.option('--config', type=click.Path(exists=True, dir_okay=False))
        @click.option('--request-id')
        @click.pass_obj
        @guarded
        def command(path, spec, config, request_id):
            ws = ReliabilityWorkspace(path); source = Path(spec).absolute(); value = load(source)
            settings = EvaluationConfig.from_dict(load(config)) if config else EvaluationConfig()
            if kind == 'ingest':
                specification = PredictionBatchSpec.from_dict(value, base_directory=source.parent)
                emit(ws.ingest(specification, settings, request_id=request_id))
            elif kind == 'outcomes':
                value['source']['path'] = str(source.parent/value['source']['path']) if not Path(value['source']['path']).is_absolute() else value['source']['path']
                emit(ws.update_outcomes(OutcomeRevisionSpec.from_dict(value), settings, request_id=request_id))
            else: emit(ws.correct(value, request_id=request_id))
        workspace.command(kind)(command)
    for kind in ('ingest', 'outcomes', 'correct'): import_command(kind)

    @workspace.command('inspect')
    @click.option('--spec', required=True, type=click.Path(exists=True, dir_okay=False))
    @click.pass_obj
    @guarded
    def inspect(path, spec): emit(ReliabilityWorkspace(path).inspect(load(spec)))

    @workspace.command('analyze')
    @click.option('--spec', required=True, type=click.Path(exists=True, dir_okay=False))
    @click.option('--out', type=click.Path())
    @click.option('--format', 'fmt', type=click.Choice(['html', 'pdf']), default='html')
    @click.option('--audience', type=click.Choice(['shareable', 'local']), default='shareable')
    @click.pass_obj
    @guarded
    @click.option('--request-id')
    def analyze(path, spec, out, fmt, audience,request_id):
        result = ReliabilityWorkspace(path).analyze(load(spec),request_id=request_id)
        value = {'assessment_id': result.data['analysis_id']}
        if out: value['artifacts'] = asdict(result.generate_artifacts(out, format=fmt, audience=audience, json_path=str(Path(out).with_suffix('.json'))))
        emit(value)

    @workspace.command('restate')
    @click.option('--assessment', required=True)
    @click.option('--as-of')
    @click.option('--reason', required=True)
    @click.pass_obj
    @guarded
    @click.option('--request-id')
    def restate(path, assessment, as_of, reason,request_id):
        result = ReliabilityWorkspace(path).restate(assessment, as_of=as_of, reason=reason,request_id=request_id)
        emit({'assessment_id': result.data['analysis_id']})

    @workspace.command('assessments')
    @click.pass_obj
    @guarded
    def assessments(path): emit(ReliabilityWorkspace(path).assessments())

    @workspace.command('open')
    @click.option('--assessment', required=True)
    @click.option('--audience', type=click.Choice(['shareable', 'local']), default='shareable')
    @click.pass_obj
    @guarded
    def reopen(path, assessment, audience): emit(ReliabilityWorkspace(path).open(assessment).to_dict(audience=audience))

    @workspace.command('export')
    @click.option('--assessment', required=True)
    @click.option('--out', required=True, type=click.Path())
    @click.option('--format', 'fmt', type=click.Choice(['html', 'pdf']), default='html')
    @click.option('--audience', type=click.Choice(['shareable', 'local']), default='shareable')
    @click.pass_obj
    @guarded
    def export(path, assessment, out, fmt, audience):
        result = ReliabilityWorkspace(path).open(assessment)
        emit(asdict(result.generate_artifacts(out, format=fmt, audience=audience, json_path=str(Path(out).with_suffix('.json')))))

    @workspace.command('backup')
    @click.option('--out', required=True, type=click.Path())
    @click.pass_obj
    @guarded
    def backup(path, out): emit(ReliabilityWorkspace(path).backup(out))

    @workspace.command('restore')
    @click.option('--backup', required=True, type=click.Path(exists=True, file_okay=False))
    @click.pass_obj
    @guarded
    def restore(path, backup): emit(ReliabilityWorkspace.restore(backup, path).status())

    @workspace.command('recover')
    @click.pass_obj
    @guarded
    def recover(path): emit(ReliabilityWorkspace(path).recover())

    @workspace.command('deletion-preview')
    @click.option('--object-id', multiple=True)
    @click.option('--assessment', multiple=True)
    @click.option('--batch-id', multiple=True)
    @click.option('--purge', is_flag=True)
    @click.option('--out', required=True, type=click.Path())
    @click.pass_obj
    @guarded
    def deletion_preview(path, object_id, assessment, batch_id, purge, out):
        value = ReliabilityWorkspace(path).deletion_preview(object_ids=object_id, assessment_ids=assessment, batch_ids=batch_id, purge=purge)
        compat_path = Path(out)
        from .history_storage import private_file
        with private_file(compat_path) as stream: stream.write(json.dumps(value, indent=2).encode())
        emit(value)

    @workspace.command('delete')
    @click.option('--plan', required=True, type=click.Path(exists=True, dir_okay=False))
    @click.pass_obj
    @guarded
    def delete(path, plan): emit(ReliabilityWorkspace(path).delete(load(plan)))
