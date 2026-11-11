import os
from pathlib import Path
import shutil
import subprocess
import pytest


def test_actual_browser_composers_require_explicit_finite_numbers():
    node=os.environ.get('NUMEK_TEST_NODE') or shutil.which('node')
    if not node:pytest.skip('Node is required for the browser JavaScript component check; Python contracts remain separately tested.')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/cg4/browser_numeric_controls.cjs'),str(root/'src/confidenceguard/static/investigation-client.js')],
        capture_output=True,text=True,timeout=20,check=True)
    assert 'Actual composer handlers passed' in result.stdout
