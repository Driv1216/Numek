from pathlib import Path
import tempfile
from datatrust.web import create_app


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='cg1-browser-') as root:
        app=create_app(Path(root),data_roots=(Path('validation/cg1/data').resolve(),))
        try:app.run(host='127.0.0.1',port=8031,threaded=False,debug=False,use_reloader=False)
        finally:app.extensions['confidenceguard_store'].cleanup()
