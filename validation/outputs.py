"""Where a DataTrust milestone validator writes its regenerated artifacts and ledgers.

Verifying must never rewrite committed evidence. By default each validator mirrors its folder into one temporary
directory, writes everything there and removes it at exit; committed evidence is only read, to compare or reuse.

`--refresh` on the command line, or DATATRUST_VALIDATION_REFRESH=1, writes to the committed locations instead. That is
the deliberate re-baselining step, reviewed and committed like any other change. DATATRUST_VALIDATION_KEEP=1 keeps the
temporary directory for inspection and prints where it is.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
_TEMPORARY = None


def refreshing():
    return '--refresh' in sys.argv[1:] or os.environ.get('DATATRUST_VALIDATION_REFRESH') == '1'


def output_root(root):
    """The folder a validator rooted at `root` writes into: `root` itself when refreshing, otherwise its mirror in a
    temporary directory, so relative paths recorded in ledgers stay the same either way."""
    root = Path(root).resolve()
    if refreshing():
        return root
    global _TEMPORARY
    if _TEMPORARY is None:
        _TEMPORARY = Path(tempfile.mkdtemp(prefix='datatrust-verify-'))
        if os.environ.get('DATATRUST_VALIDATION_KEEP') == '1':
            print(f'Validation outputs kept in {_TEMPORARY}', flush=True)
        else:
            atexit.register(shutil.rmtree, _TEMPORARY, True)
    mirror = _TEMPORARY / root.relative_to(REPOSITORY)
    mirror.mkdir(parents=True, exist_ok=True)
    return mirror
