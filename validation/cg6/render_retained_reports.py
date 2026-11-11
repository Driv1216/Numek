"""Render the exact sealed report fixtures again after presentation corrections."""
from pathlib import Path
import json,hashlib
from confidenceguard import EvaluationResult
from unittest.mock import patch

root=Path(__file__).resolve().parent/'results/reports';final=root.parent/'reports-final-v2';final.mkdir(exist_ok=True);receipts=[]
for directory in sorted(p for p in root.iterdir() if p.is_dir() and p.name!='visual'):
    local=directory/'local.json'
    if not local.exists():continue
    value=json.loads(local.read_text());manifest=directory/'.confidenceguard-private'/value['analysis_id']/'manifest.json'
    result=EvaluationResult.from_dict(value,private=json.loads(manifest.read_text()))
    for audience in ('local','shareable'):
        destination=final/directory.name;destination.mkdir(exist_ok=True);target=destination/(audience+'.pdf')
        with patch('confidenceguard.execution.adapters.Adapter',side_effect=AssertionError('No model load during rendering')):
            result.generate_artifacts(target,format='pdf',json_path=target.with_suffix('.json'),audience=audience)
        receipts.append({'case':directory.name,'audience':audience,'pdf':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'binding':result.binding,'model_loading_during_export':False})
(final/'receipt.json').write_text(json.dumps({'reports':receipts,'visual_page_inspection':'pending','rerender_reason':'CG6-specific continuous sections and page-number footer; analytics and original sealed fixtures reused'},indent=2)+'\n')
