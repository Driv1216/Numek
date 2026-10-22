"""Single private DataTrust infrastructure boundary. Accepted engines stay unchanged."""
from dataclasses import fields
from types import SimpleNamespace
from .contracts import EvaluationError


def options(config):
    from datatrust.m4_contracts import ExecutionOptions
    return ExecutionOptions(**{f.name:getattr(config,f.name) for f in fields(ExecutionOptions) if hasattr(config,f.name)})


def supervise(operation,arguments,config,*,progress=None,cancel=None):
    from datatrust.worker import run_supervised
    from datatrust.contracts import AnalysisError
    try:return run_supervised(operation,arguments,options(config),progress=progress,cancel=cancel)
    except AnalysisError as exc:
        error=EvaluationError('Evaluation stopped; inspect the execution code and configured limits.',exc.code,exc.stage)
        error.execution=getattr(exc,'execution',{})
        raise error from exc


def workspace(config,estimate,progress):
    from datatrust.scalable import Workspace
    return Workspace(options(config),[],progress,phase_plan={'estimated_peak_workspace_bytes':estimate,'kind':'confidenceguard_projected_predictions'})


def capture(path,roots,**kwargs):
    from datatrust.image_assets import capture as implementation
    return implementation(path,roots,**kwargs)


def secure_open(path,roots):
    from datatrust.image_assets import secure_open as implementation
    return implementation(path,roots)


def frames(path,source,config):
    from datatrust.text_normalization import frames as implementation
    from datatrust.text_contracts import TextSourceSpec,TextWorkLimits
    return implementation(path,TextSourceSpec(path,source.format,source.encoding,source.delimiter),options(config),TextWorkLimits())


def parquet(path):
    from datatrust.temporal_normalization import parquet_preflight
    return parquet_preflight(path,SimpleNamespace(parquet_metadata_bytes=16*1024**2))


def clock(value,spec):
    if spec is None:return None,'undeclared'
    from datatrust.temporal_contracts import ClockSpec
    from datatrust.temporal_normalization import parse_clock
    if hasattr(value,'isoformat'):value=value.isoformat()
    tick,state,_,_=parse_clock(value,ClockSpec(**spec.to_dict()))
    return tick,state


def publish(path,content):
    from datatrust.renderer import publish_bytes
    return publish_bytes(path,content)


def protect(sources,destinations):
    from datatrust.renderer import protect_source
    return protect_source(sources,destinations)


def destination(path):
    from datatrust.renderer import _new_destination
    return _new_destination(path)


def protected_directory(path):
    from datatrust.text_private import protected_directory as implementation
    return implementation(path)


def pdf(html,path,expected):
    from datatrust.pdf import render_pdf_report
    return render_pdf_report(html,path,expected_html_sha256=expected)


def insert_rows(con, table, records):
    """Bounded explicit registration, with external access still disabled.

    This is an insertion optimization, never a DataFrame analytical path. Object
    dtype preserves lexical strings; HUGEINT values are explicitly cast from
    exact decimal strings rather than passing through a float inference step.
    """
    if not records:return
    import pandas as pd
    import re
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',table):raise EvaluationError('Invalid internal relation.')
    schema=con.execute(f'DESCRIBE {table}').fetchall()
    huge=[i for i,column in enumerate(schema) if column[1]=='HUGEINT']
    values=[tuple(str(v) if i in huge and v is not None else v for i,v in enumerate(row)) for row in records] if huge else records
    frame=pd.DataFrame(values,columns=[v[0] for v in schema],dtype=object)
    con.register('cg_bounded_insert',frame)
    try:con.execute(f'INSERT INTO {table} SELECT * FROM cg_bounded_insert')
    finally:con.unregister('cg_bounded_insert')
