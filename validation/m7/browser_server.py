"""Temporary loopback app for real browser verification against pinned validation data."""
from pathlib import Path
import tempfile
from datatrust.web import create_app

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='numek-m7-browser-') as root:
        app=create_app(Path(root),data_roots=(Path(__file__).parent.absolute(),))
        try: app.run(host='127.0.0.1',port=8017,use_reloader=False)
        finally: app.extensions['datatrust_m7_store'].cleanup()
