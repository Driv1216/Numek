"""Thin CG6 CLI; path resolution is confined to local operator input."""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import click

from ..contracts import strict_json,EvaluationError
from ..result import EvaluationResult
from .services import inspect_predictor,register_predictor,execute_predictor,qualify_predictor


def load(path):return strict_json(Path(path).read_bytes())


def relative(value,base):
    if isinstance(value,dict):
        return {k:str((base/v).resolve()) if k in {'path','tensor_file','keys_source'} and isinstance(v,str) and not Path(v).is_absolute() else relative(v,base) for k,v in value.items()}
    if isinstance(value,list):return [relative(v,base) for v in value]
    return value


def register(main):
    from ..auxiliary.services import fit_auxiliary,apply_auxiliary,assess_auxiliary
    from ..robustness.services import inspect_robustness,run_robustness,freeze_robustness,assess_robustness,stress_policy
    from .bridge import as_reliability_spec
    groups={}
    for title in ('predictor','auxiliary','robustness'):
        group=click.Group(title,help='Local '+title+' operations through the ConfidenceGuard engine.');main.add_command(group);groups[title]=group
    operations={'predictor':{'inspect':inspect_predictor,'register':register_predictor,'execute':execute_predictor,'qualify':qualify_predictor},
                'auxiliary':{'fit':fit_auxiliary,'apply':apply_auxiliary,'assess':assess_auxiliary},
                'robustness':{'inspect':inspect_robustness,'run':run_robustness,'assess':assess_robustness,'policy-stress':stress_policy}}
    def command(group,title,operation):
        @group.command(title)
        @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--artifact',type=click.Path(exists=True,dir_okay=False))
        @click.option('--reference',type=click.Path(exists=True,dir_okay=False))
        @click.option('--fingerprint')
        @click.option('--workspace',type=click.Path(exists=True,file_okay=False))
        @click.option('--request-id')
        @click.option('--out',type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--json-out',type=click.Path())
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def invoke(spec,config,artifact,reference,fingerprint,workspace,request_id,out,fmt,json_out,audience):
            try:
                path=Path(spec).absolute();s=relative(load(path),path.parent);c=load(config) if config else None
                kwargs={'workspace':workspace,'request_id':request_id,'expected_fingerprint':fingerprint}
                if title=='inspect':kwargs.pop('workspace');kwargs.pop('request_id')
                if artifact:
                    if group.name!='auxiliary' or title not in {'apply','assess'}:raise EvaluationError('An auxiliary artifact applies only to auxiliary application/assessment.')
                    result=operation(s,relative(load(artifact),Path(artifact).absolute().parent),c,**kwargs)
                else:
                    if group.name=='auxiliary' and title in {'apply','assess'}:raise EvaluationError('--artifact is required.')
                    if reference:
                        if group.name!='predictor' or title!='qualify':raise EvaluationError('Reference outputs apply only to predictor qualification.')
                        kwargs['reference']=load(reference)
                    result=operation(s,c,**kwargs)
                if isinstance(result,dict):click.echo(json.dumps(result,indent=2,allow_nan=False));return
                if out:click.echo(json.dumps(asdict(result.generate_artifacts(out,format=fmt,json_path=json_out or str(Path(out).with_suffix('.json')),audience=audience)),indent=2))
                else:click.echo(json.dumps(result.to_dict(audience=audience),indent=2,allow_nan=False))
            except Exception as exc:raise click.ClickException(f'{getattr(exc,"code","cg6_operation_failed")}: {exc}') from exc
    for title,items in operations.items():
        for name,operation in items.items():command(groups[title],name,operation)
    def revisit(group):
        @group.command('open')
        @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def opened(result,manifest,audience):
            try:click.echo(json.dumps(EvaluationResult.from_dict(load(result),private=load(manifest) if manifest else None).to_dict(audience=audience),indent=2))
            except Exception as exc:raise click.ClickException(str(exc)) from exc
        @group.command('export')
        @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
        @click.option('--out',required=True,type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def exported(result,manifest,out,fmt,audience):
            try:
                r=EvaluationResult.from_dict(load(result),private=load(manifest) if manifest else None)
                click.echo(json.dumps(asdict(r.generate_artifacts(out,format=fmt,json_path=str(Path(out).with_suffix('.json')),audience=audience)),indent=2))
            except Exception as exc:raise click.ClickException(str(exc)) from exc
    for group in groups.values():revisit(group)

    @groups['predictor'].command('restate')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.option('--workspace',type=click.Path(exists=True,file_okay=False))
    @click.option('--out',required=True,type=click.Path())
    def restate(result,manifest,spec,config,workspace,out):
        from .restatement import restate_execution
        try:
            parent=EvaluationResult.from_dict(load(result),private=load(manifest));path=Path(spec).absolute()
            revised=restate_execution(parent,relative(load(path),path.parent),load(config) if config else None,workspace=workspace)
            click.echo(json.dumps(asdict(revised.generate_artifacts(out,format='html',json_path=str(Path(out).with_suffix('.json')),audience='local')),indent=2))
        except Exception as exc:raise click.ClickException(str(exc)) from exc

    @groups['predictor'].command('convert-legacy')
    @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--trust-sha256',required=True,help='Explicit trust in these exact executable pickle/joblib bytes.')
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    def convert(spec,trust_sha256,config,out):
        from .legacy import convert_legacy_predictor
        try:
            path=Path(spec).absolute();result=convert_legacy_predictor(relative(load(path),path.parent),trusted_sha256=trust_sha256,config=load(config) if config else None)
            click.echo(json.dumps(asdict(result.generate_artifacts(out,format='html',json_path=str(Path(out).with_suffix('.json')),audience='local')),indent=2))
        except Exception as exc:raise click.ClickException(str(exc)) from exc

    @groups['auxiliary'].command('export-artifact')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    def export_artifact(result,manifest,out):
        from .. import compat
        r=EvaluationResult.from_dict(load(result),private=load(manifest));artifact=r.private['auxiliary_artifacts'][0]
        compat.protect(r.source_paths,[out]);compat.destination(out);compat.publish(out,json.dumps(artifact,indent=2).encode())
        click.echo(json.dumps({'path':out,'protected':True,'model_bytes_referenced':True}))

    @groups['robustness'].command('freeze')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--protocol',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    def freeze(result,manifest,protocol,out):
        from .. import compat
        try:
            r=EvaluationResult.from_dict(load(result),private=load(manifest));frozen=freeze_robustness(r,**load(protocol))
            compat.protect(r.source_paths,[out]);compat.destination(out);compat.publish(out,json.dumps(frozen.to_dict(),indent=2).encode())
            click.echo(json.dumps({'path':out,'content_digest':frozen.content_digest,'protected':True}))
        except Exception as exc:raise click.ClickException(str(exc)) from exc

    @groups['predictor'].command('bridge')
    @click.option('--result',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--scope',default='original')
    @click.option('--directory',required=True,type=click.Path())
    def bridge(result,manifest,scope,directory):
        try:
            r=EvaluationResult.from_dict(load(result),private=load(manifest));spec=as_reliability_spec(r,scope=scope,directory=directory)
            click.echo(json.dumps(spec.to_dict(),indent=2))
        except Exception as exc:raise click.ClickException(str(exc)) from exc
