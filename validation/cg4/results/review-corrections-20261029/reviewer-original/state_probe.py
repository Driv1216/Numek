import json
from types import SimpleNamespace
import numpy as np
from confidenceguard.features import normalize
from confidenceguard.feature_contracts import FeatureField
from confidenceguard.discovery_rules import propose
from confidenceguard.investigation_contracts import InvestigationLimits
from confidenceguard.investigation_membership import seal,apply
field=FeatureField('x','x','integer');cells=[normalize('',field) for _ in range(60)]+[normalize('bad',field) for _ in range(60)]
objective=SimpleNamespace(spec=SimpleNamespace(direction='higher',metric='error_rate'),identity={})
proposals,status=propose({'context.x':cells},np.ones(120,bool),np.r_[np.zeros(60),np.ones(60)],objective,InvestigationLimits())
manual=seal('structured',{'clauses':[{'field':'context.x','kind':'integer','op':'state','value':'invalid'}]},features=['context.x'])
mask=apply(manual,{'context.x':cells},{})
print(json.dumps({'automatic_candidates':len(proposals),'search_status':status,'valid_exact_invalid_state_gate_members':int(mask['member'].sum()),'valid_exact_gate_available':int(mask['available'].sum())},indent=2))
