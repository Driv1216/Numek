import importlib.util
from pathlib import Path
import sys
import pytest


def transition():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_campaign_resume',directory/'resume_objective_campaign.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.allowlist_only_transition
    finally:sys.path.pop(0)


def test_additive_control_allowlist_preserves_executable_body():
    check=transition();old="SCRIPTS=('original.py',)\ndef run(): return 4\n"
    assert check(old,"SCRIPTS=('original.py','extra.py')\ndef run(): return 4\n")==['extra.py']
    for changed in ["SCRIPTS=('extra.py',)\ndef run(): return 4\n",
                    "SCRIPTS=('original.py','extra.py')\ndef run(): return 5\n",
                    "SCRIPTS=load()\ndef run(): return 4\n"]:
        with pytest.raises((RuntimeError,ValueError)):check(old,changed)
