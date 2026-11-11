"""CG5 CLI adapter. Analytics and publication remain shared public services."""
import json
from pathlib import Path
import click

from .contracts import EvaluationError,EvaluationConfig,strict_json
from .result import EvaluationResult
from .policy_contracts import PolicyStudySpec,PolicyApplicationSpec,FrozenPolicyFamily
from . import compat


def load(path): return strict_json(Path(path).read_text())
def emit(value): click.echo(json.dumps(value,indent=2,allow_nan=False))


def open_result(result,manifest):
    return EvaluationResult.from_dict(load(result),private=load(manifest) if manifest else None)


def register(main):
    @main.group('policy')
    def group():
        """Select, replay and independently assess typed decision policies."""

    def execute_command(kind):
        @group.command(kind)
        @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--fingerprint')
        @click.option('--out',type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--json-out',type=click.Path())
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def command(spec,config,fingerprint,out,fmt,json_out,audience):
            from .policies import inspect_policy_study,optimize_policies,replay_policy
            from .policy_history import analyze_policy_history
            try:
                path=Path(spec); value=load(path)
                cls=PolicyStudySpec if kind in {'inspect','optimize'} else PolicyApplicationSpec
                value=cls.from_dict(value)
                from dataclasses import replace
                from .policy_contracts import PolicyInputSpec
                value=replace(value,input=PolicyInputSpec.from_dict(value.input.to_dict(),base_directory=path.parent))
                options=load(config) if config else None
                if kind=='inspect': emit(inspect_policy_study(value,options)); return
                operation={'optimize':optimize_policies,'replay':replay_policy,'history':analyze_policy_history}[kind]
                kwargs={'expected_fingerprint':fingerprint} if kind!='history' else {}
                result=operation(value,options,**kwargs)
                if out:
                    artifacts=result.generate_artifacts(out,format=fmt,json_path=json_out or str(Path(out).with_suffix('.json')),audience=audience)
                    emit(artifacts.__dict__)
                else: emit(result.to_dict(audience=audience))
            except Exception as exc:
                if getattr(exc,'artifacts',None): click.echo(json.dumps(exc.artifacts.__dict__),err=True)
                raise click.ClickException(str(exc)) from exc
        return command
    for kind in ('inspect','optimize','replay','history'): execute_command(kind)

    @group.command('freeze')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--assessment',type=click.Path(exists=True,dir_okay=False))
    @click.option('--policy-digest',multiple=True)
    @click.option('--out',required=True,type=click.Path())
    def freeze(result,manifest,assessment,policy_digest,out):
        from .policy_assessment import freeze_policy_family
        try:
            frozen=freeze_policy_family(open_result(result,manifest),policy_digest or None,assessment=load(assessment) if assessment else None)
            compat.protect([result,manifest]+([assessment] if assessment else []),[out]); compat.destination(out)
            compat.publish(out,json.dumps(frozen.to_dict(),sort_keys=True,indent=2).encode())
            emit({'path':str(Path(out).absolute()),'assessment_family_digest':frozen.family_digest,'protected':True})
        except Exception as exc: raise click.ClickException(str(exc)) from exc

    @group.command('preview-assessment')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--assessment',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--planned-e-size',required=True,type=click.IntRange(min=1))
    @click.option('--half-width',type=click.FloatRange(min=0,min_open=True))
    def preview(result,manifest,assessment,planned_e_size,half_width):
        from .policy_assessment import preview_policy_assessment
        try: emit(preview_policy_assessment(open_result(result,manifest),load(assessment),planned_e_size=planned_e_size,requested_half_width=half_width))
        except Exception as exc: raise click.ClickException(str(exc)) from exc

    def assessment_command(kind):
        @group.command(kind)
        @click.option('--family',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--input-spec',type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--fingerprint')
        @click.option('--out',type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def command(family,input_spec,config,fingerprint,out,fmt,audience):
            from .policy_assessment import inspect_policy_assessment,assess_policies
            try:
                frozen=FrozenPolicyFamily.from_dict(load(family)); options=load(config) if config else None
                from .policy_contracts import PolicyInputSpec
                kwargs={'assessment_input':PolicyInputSpec.from_dict(load(input_spec),base_directory=Path(input_spec).parent)} if input_spec else {}
                if kind=='inspect-assessment': emit(inspect_policy_assessment(frozen,options,**kwargs)); return
                result=assess_policies(frozen,options,expected_fingerprint=fingerprint,**kwargs)
                if out: emit(result.generate_artifacts(out,format=fmt,json_path=str(Path(out).with_suffix('.json')),audience=audience).__dict__)
                else: emit(result.to_dict(audience=audience))
            except Exception as exc:
                if getattr(exc,'artifacts',None): click.echo(json.dumps(exc.artifacts.__dict__),err=True)
                raise click.ClickException(str(exc)) from exc
    for kind in ('inspect-assessment','assess'): assessment_command(kind)

    def revisit_command(kind):
        @group.command(kind)
        @click.option('--workspace',required=True,type=click.Path(exists=True,file_okay=False))
        @click.option('--assessment-id',required=True)
        @click.option('--look-id')
        @click.option('--as-of')
        @click.option('--reason')
        @click.option('--fingerprint')
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--out',type=click.Path())
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def command(workspace,assessment_id,look_id,as_of,reason,fingerprint,config,out,audience):
            from .workspace import ReliabilityWorkspace
            try:
                ws=ReliabilityWorkspace(workspace);options=load(config) if config else None
                if kind=='inspect-look':emit(ws.inspect_policy_restatement(assessment_id,look_id,options));return
                if kind=='assess-look':result=ws.restate_policy_assessment(assessment_id,look_id,options,expected_fingerprint=fingerprint)
                else:result=ws.restate_policy_history(assessment_id,as_of=as_of,reason=reason,config=options)
                if out:emit(result.generate_artifacts(out,json_path=str(Path(out).with_suffix('.json')),audience=audience).__dict__)
                else:emit(result.to_dict(audience=audience))
            except Exception as exc:raise click.ClickException(str(exc)) from exc
    for kind in ('inspect-look','assess-look','restate-history'):revisit_command(kind)

    @group.command('open')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
    @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
    def reopen(result,manifest,audience):
        try: emit(open_result(result,manifest).to_dict(audience=audience))
        except Exception as exc: raise click.ClickException(str(exc)) from exc

    @group.command('export')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
    @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
    @click.option('--policy-digest',help='Explicit protected executable export; requires local audience and manifest.')
    def export(result,manifest,out,fmt,audience,policy_digest):
        try:
            opened=open_result(result,manifest)
            if policy_digest:
                if audience!='local' or not manifest: raise EvaluationError('Executable export requires explicit local audience and protected evidence.')
                from .policies import export_frozen_policy
                frozen=export_frozen_policy(opened,policy_digest)
                compat.protect(list(opened.source_paths)+[result,manifest],[out]);compat.destination(out);compat.publish(out,json.dumps(frozen.to_dict(),sort_keys=True,indent=2).encode())
                emit({'path':str(Path(out).absolute()),'protected':True});return
            emit(opened.generate_artifacts(out,format=fmt,json_path=str(Path(out).with_suffix('.json')),audience=audience).__dict__)
        except Exception as exc: raise click.ClickException(str(exc)) from exc

    @group.command('evidence')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--reference',required=True)
    @click.option('--root',multiple=True,required=True,type=click.Path(exists=True))
    @click.option('--reveal-values',is_flag=True)
    def evidence(result,manifest,reference,root,reveal_values):
        try: emit(open_result(result,manifest).resolve_evidence(reference,allowed_roots=root,reveal_values=reveal_values))
        except Exception as exc: raise click.ClickException(str(exc)) from exc
