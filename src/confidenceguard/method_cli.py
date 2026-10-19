"""Thin CG2 commands over the same public application services."""
from dataclasses import asdict,replace
import json
from pathlib import Path
import click
from .contracts import EvaluationError
from .method_contracts import ReliabilitySpec,MethodLimits
from .fitted import FittedMethod,bounded_json


def collection(value,limits=None,*,with_membership=False):
    limits=limits or MethodLimits()
    if isinstance(value,(str,bytes)):value=bounded_json(value,limits)
    if isinstance(value,dict) and value.get('schema_version')=='confidenceguard.fitted_collection/1.0':
        if set(value)-{'schema_version','methods','membership_sidecars'} or not isinstance(value['methods'],list):raise EvaluationError('Invalid fitted collection.')
        values=value['methods']
    else:values=[value]
    if not values or len(values)>limits.variants:raise EvaluationError('Fitted collection admission exceeded.')
    result=[FittedMethod.from_dict(v,limits=limits).to_dict() for v in values]
    if len({v['id'] for v in result})!=len(result):raise EvaluationError('Duplicate fitted method identities.')
    sidecars=value.get('membership_sidecars',[]) if isinstance(value,dict) and value.get('schema_version')=='confidenceguard.fitted_collection/1.0' else []
    if not isinstance(sidecars,list):raise EvaluationError('Invalid membership sidecar collection.')
    from .membership import validate
    for sidecar in sidecars:validate(sidecar,limits)
    return (result,sidecars) if with_membership else result


def register(main):
    def command(kind):
        @main.command(kind)
        @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--methods',type=click.Path(exists=True,dir_okay=False),help='Protected fitted method/collection; no executable serialization.')
        @click.option('--predictions-out',type=click.Path(),help='Protected JSONL application output (apply only).')
        @click.option('--out',required=True,type=click.Path())
        @click.option('--format','report_format',type=click.Choice(['html','pdf']),default='html')
        @click.option('--json-out',type=click.Path())
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        def run(spec,config,methods,predictions_out,out,report_format,json_out,audience):
            from .cli import specifications
            from .methods import fit_methods,apply_methods,study
            try:
                s,c=specifications(spec,config)
                if not isinstance(s,ReliabilitySpec):raise EvaluationError('Use a CG2 study/application specification.')
                if methods:
                    with Path(methods).open('rb') as f:raw=f.read(s.limits.method_bytes+1)
                    fitted,sidecars=collection(raw,s.limits,with_membership=True)
                    s=replace(s,fitted_methods=tuple(fitted),membership_sidecars=tuple(sidecars))
                if predictions_out:
                    if kind!='apply':raise EvaluationError('predictions-out applies only to apply.')
                    s=replace(s,output_path=str(Path(predictions_out).absolute()))
                result={'fit':fit_methods,'apply':apply_methods,'study':study}[kind](s,c)
                artifacts=result.generate_artifacts(out,format=report_format,json_path=json_out,audience=audience)
                output=asdict(artifacts)
                if result.private.get('application_export'):output['application']=result.private['application_export']
                click.echo(json.dumps(output,indent=2,allow_nan=False))
            except Exception as exc:
                if getattr(exc,'artifacts',None):click.echo(json.dumps(asdict(exc.artifacts),indent=2))
                raise click.ClickException(f'{getattr(exc,"code","method_operation_failed")}: {exc}') from exc
        return run
    for kind in ('fit','apply','study'):command(kind)
