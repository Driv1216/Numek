"""Thin CG4 commands; Python services own every analytical decision."""
from dataclasses import asdict
import json
from pathlib import Path
import click
from .contracts import EvaluationConfig,EvaluationError
from .history_cli import load,emit,guarded
from .investigation_contracts import InvestigationSpec,FrozenHypothesisSet
from .investigation_result import InvestigationResult
from .investigation import inspect_investigation,investigate,freeze_hypotheses,configuration
from .confirmation import inspect_confirmation,confirm_investigation
from . import compat


def settings(path):return configuration(load(path) if path else None)
def specification(path):return InvestigationSpec.from_dict(load(path),base_directory=Path(path).absolute().parent)
def protected(report,manifest):return InvestigationResult.from_dict(load(report),private=load(manifest))


def register(main):
    @main.group('investigation')
    def group():
        """Discover on D, select on S, freeze, then assess independently on H."""

    def preparation(kind):
        @group.command(kind)
        @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--workspace',type=click.Path(exists=True,file_okay=False))
        @click.option('--out',type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        @click.option('--fingerprint')
        @guarded
        def run(spec,config,workspace,out,fmt,audience,fingerprint):
            s=specification(spec);c=settings(config)
            if kind=='inspect':emit(inspect_investigation(s,c));return
            if out is None:raise EvaluationError('Discovery requires --out for its canonical report and evidence bundle.')
            if workspace:
                from .workspace import ReliabilityWorkspace
                result=ReliabilityWorkspace(workspace).investigate(s,c,expected_fingerprint=fingerprint)
            else:result=investigate(s,c,expected_fingerprint=fingerprint)
            emit(asdict(result.generate_artifacts(out,format=fmt,audience=audience,json_path=Path(out).with_suffix('.json'))))
        return run
    preparation('inspect');preparation('discover')

    @group.command('freeze')
    @click.option('--report',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--candidate',multiple=True)
    @click.option('--confirmation',type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    @guarded
    def freeze(report,manifest,candidate,confirmation,out):
        frozen=freeze_hypotheses(protected(report,manifest),candidate or None,confirmation=load(confirmation) if confirmation else None)
        compat.publish(out,json.dumps(frozen.to_dict(),ensure_ascii=True,sort_keys=True,indent=2).encode())
        emit({'path':str(Path(out).absolute()),'family_digest':frozen.family_digest,'hypotheses':len(frozen.data['hypotheses'])})

    def confirmation_command(kind):
        @group.command(kind)
        @click.option('--hypotheses',required=True,type=click.Path(exists=True,dir_okay=False))
        @click.option('--input-spec',type=click.Path(exists=True,dir_okay=False))
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--workspace',type=click.Path(exists=True,file_okay=False))
        @click.option('--fingerprint')
        @click.option('--out',type=click.Path())
        @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
        @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
        @guarded
        def run(hypotheses,input_spec,config,workspace,fingerprint,out,fmt,audience):
            frozen=FrozenHypothesisSet.from_dict(load(hypotheses));s=specification(input_spec) if input_spec else None;c=settings(config) if config else None
            if kind=='inspect-confirmation':emit(inspect_confirmation(frozen,c,confirmation_input=s,workspace=workspace));return
            if out is None:raise EvaluationError('Confirmation requires --out.')
            kwargs={'confirmation_input':s,'expected_fingerprint':fingerprint}
            if workspace:
                from .workspace import ReliabilityWorkspace
                result=ReliabilityWorkspace(workspace).confirm_investigation(frozen,c,**kwargs)
            else:result=confirm_investigation(frozen,c,**kwargs)
            emit(asdict(result.generate_artifacts(out,format=fmt,audience=audience,json_path=Path(out).with_suffix('.json'))))
        return run
    confirmation_command('inspect-confirmation');confirmation_command('confirm')

    @group.command('open')
    @click.option('--report',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
    @guarded
    def reopen(report,manifest):
        result=InvestigationResult.from_dict(load(report),private=load(manifest) if manifest else None)
        emit(result.to_dict(audience='local' if manifest else 'shareable'))

    @group.command('export')
    @click.option('--report',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',type=click.Path(exists=True,dir_okay=False))
    @click.option('--out',required=True,type=click.Path())
    @click.option('--format','fmt',type=click.Choice(['html','pdf']),default='html')
    @click.option('--audience',type=click.Choice(['local','shareable']),default='shareable')
    @guarded
    def export(report,manifest,out,fmt,audience):
        result=InvestigationResult.from_dict(load(report),private=load(manifest) if manifest else None)
        emit(asdict(result.generate_artifacts(out,format=fmt,audience=audience,json_path=Path(out).with_suffix('.json'))))

    @group.command('evidence')
    @click.option('--report',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--manifest',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--reference',required=True)
    @click.option('--allowed-root',multiple=True,required=True,type=click.Path(exists=True,file_okay=False))
    @click.option('--reveal-values',is_flag=True)
    @guarded
    def evidence(report,manifest,reference,allowed_root,reveal_values):emit(protected(report,manifest).resolve_evidence(reference,allowed_roots=allowed_root,reveal_values=reveal_values))

    workspace=main.commands['workspace']
    @workspace.command('migrate')
    @click.option('--backup',type=click.Path(),default=None,help='Post-cutover backup destination (own P-LOCAL cluster).')
    @click.pass_obj
    @guarded
    def migrate(path,backup):
        """Migrate a catalog v2 workspace onto the NUMEK platform (validated, resumable)."""
        from .workspace import ReliabilityWorkspace
        emit(ReliabilityWorkspace.migrate(path,backup))
    @workspace.command('migrate-status')
    @click.pass_obj
    @guarded
    def migrate_status(path):
        from .migration import migration_status
        emit(migration_status(path))
    @workspace.command('migrate-abandon')
    @click.pass_obj
    @guarded
    def migrate_abandon(path):
        """Before cutover only: drop the platform copy and restore catalog v2."""
        from .migration import abandon_workspace
        emit(abandon_workspace(path))
    @workspace.command('evidence-tracking')
    @click.argument('choice',type=click.Choice(['status','on','off']),default='status')
    @click.pass_obj
    @guarded
    def tracking(path,choice):
        from .workspace import ReliabilityWorkspace
        emit(ReliabilityWorkspace(path).evidence_tracking(None if choice=='status' else choice=='on'))
    @workspace.command('enrich-features')
    @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.pass_obj
    @guarded
    def enrich(path,spec,config):
        from .workspace import ReliabilityWorkspace
        value=load(spec);value['source']['path']=str((Path(spec).absolute().parent/value['source']['path']).absolute())
        emit(ReliabilityWorkspace(path).enrich_features(value,settings(config)))
    @workspace.command('prepare-representations')
    @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.pass_obj
    @guarded
    def representations(path,spec,config):
        from .workspace import ReliabilityWorkspace
        from .history_contracts import PredictionBatchSpec
        emit(ReliabilityWorkspace(path).prepare_representations(PredictionBatchSpec.from_dict(load(spec),base_directory=Path(spec).absolute().parent),settings(config)))
    @workspace.command('investigations')
    @click.pass_obj
    @guarded
    def retained(path):
        from .workspace import ReliabilityWorkspace
        emit(ReliabilityWorkspace(path).investigations())

    @workspace.command('replay-investigation')
    @click.option('--assessment',required=True)
    @click.option('--spec',required=True,type=click.Path(exists=True,dir_okay=False))
    @click.option('--reason',required=True)
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.pass_obj
    @guarded
    def replay(path,assessment,spec,reason,config):
        from .workspace import ReliabilityWorkspace
        result=ReliabilityWorkspace(path).replay_investigation(assessment,specification(spec),settings(config) if config else None,reason=reason)
        emit({'assessment_id':result.data['analysis_id'],'inference':'descriptive_only'})

    @workspace.command('annotate-investigation')
    @click.option('--assessment',required=True)
    @click.option('--text',required=True)
    @click.option('--reference',multiple=True)
    @click.pass_obj
    @guarded
    def annotate(path,assessment,text,reference):
        from .workspace import ReliabilityWorkspace
        result=ReliabilityWorkspace(path).annotate_investigation(assessment,text,references=reference)
        emit({'assessment_id':result.data['analysis_id'],'visibility':'private'})

    @workspace.command('retry-confirmation')
    @click.option('--assessment',required=True)
    @click.option('--replicates',required=True,type=click.IntRange(min=1))
    @click.option('--config',type=click.Path(exists=True,dir_okay=False))
    @click.pass_obj
    @guarded
    def retry(path,assessment,replicates,config):
        from .workspace import ReliabilityWorkspace
        result=ReliabilityWorkspace(path).retry_confirmation(assessment,replicates=replicates,config=settings(config) if config else None)
        emit({'assessment_id':result.data['analysis_id'],'fresh_independent_evidence':False})

    def scheduled(kind):
        @workspace.command(kind)
        @click.option('--assessment',required=True)
        @click.option('--look-id',required=True)
        @click.option('--config',type=click.Path(exists=True,dir_okay=False))
        @click.option('--fingerprint')
        @click.pass_obj
        @guarded
        def run(path,assessment,look_id,config,fingerprint):
            from .workspace import ReliabilityWorkspace
            ws=ReliabilityWorkspace(path);c=settings(config) if config else None
            if kind=='inspect-confirmation-restatement':emit(ws.inspect_restatement_confirmation(assessment,look_id,c));return
            result=ws.restate_confirmation(assessment,look_id,c,expected_fingerprint=fingerprint)
            emit({'assessment_id':result.data['analysis_id'],'predeclared_look':look_id,'fresh_independent_evidence':False})
    scheduled('inspect-confirmation-restatement');scheduled('restate-confirmation')
