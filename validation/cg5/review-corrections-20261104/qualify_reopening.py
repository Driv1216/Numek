"""CLI and owned API projections of the completed historical correction record."""
from pathlib import Path
import argparse
import json

from click.testing import CliRunner
from datatrust.web import create_app
from confidenceguard import ReliabilityWorkspace
from confidenceguard.cli import main as cli
from confidenceguard.result import EvaluationResult


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reports',required=True)
    root=Path(parser.parse_args().reports).resolve()
    result_path=root/'history/local.json';raw=json.loads(result_path.read_text());aid=raw['analysis_id']
    manifest=root/'history/.confidenceguard-private'/aid/'manifest.json'
    opened=EvaluationResult.from_dict(raw,private=json.loads(manifest.read_text()))
    workspace=ReliabilityWorkspace(root/'historical-data/workspace')
    workspace.save_assessment(opened)
    command=CliRunner().invoke(cli,['policy','open','--result',str(result_path),'--manifest',str(manifest),'--audience','local'])
    assert command.exit_code==0,command.output
    assert json.loads(command.output)['policy']['constraint_ledger']==opened.data['policy']['constraint_ledger']
    app=create_app(root/'api-host',data_roots=(root,),confidenceguard_workspace=workspace.path,confidenceguard_launch_token='synthetic-correction')
    app.testing=True;client=app.test_client();base='/api/confidenceguard/v1'
    try:
        client.get('/confidenceguard?launch=synthetic-correction')
        headers={'X-CSRF-Token':client.get(base+'/session').json['data']['csrf_token']}
        assert client.post(base+'/workspace/policies/'+aid+'/open',headers=headers,json={}).status_code==200
        ledger=client.get(base+'/results/'+aid+'/policy/constraint-ledger').json['data']
        worst=client.get(base+'/results/'+aid+'/policy/worst-windows').json['data']
        assert ledger['items']==opened.data['policy']['constraint_ledger']
        assert worst['items']==opened.data['policy']['worst_window_evidence']
        assert client.get(base+'/results/'+aid+'/policy/constraint-ledger?audience=shareable').json['data']['items']==[]
        assert app.test_client().get(base+'/results/'+aid+'/policy/constraint-ledger').status_code==404
    finally: app.extensions['confidenceguard_store'].cleanup()
    receipt={'passed':True,'analytical_rerun':False,'cli_ledger_matches':True,'owned_api_ledger_matches':True,
             'owned_api_worst_windows_match':True,'shareable_withholding_preserved':True,'cross_session_access_refused':True,
             'constraint_rows':len(ledger['items'])}
    (root.parent/'reopening.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
