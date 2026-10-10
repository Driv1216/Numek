"""Local UI verification runner; optional failure fixture is test-only."""
import argparse
from dataclasses import replace
from datatrust.web import run_ui


def enable_partial_fixture():
    import datatrust.m4_web as web
    from datatrust.contracts import CheckOutcome,ExecutionStatus
    original=web.analyze_scalable
    def partial(*args,**kwargs):
        result=original(*args,**kwargs)
        result=replace(result,execution=dict(result.execution,status='partial'),checks=list(result.checks),coverage={**result.coverage,'diagnostics':dict(result.coverage['diagnostics'])})
        result.checks.append(CheckOutcome('controlled_optional_failure',execution=ExecutionStatus.FAILED,reason='Controlled isolated verification fixture.'))
        result.coverage['diagnostics']['controlled_optional_failure']={'status':'failed','population':'controlled optional scope','reason':'Test-only fixture; no runtime fault-injection setting is shipped.'}
        return result
    web.analyze_scalable=partial


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial-fixture',action='store_true');args=parser.parse_args()
    if args.partial_fixture:enable_partial_fixture()
    run_ui(port=8765,open_browser=False)
