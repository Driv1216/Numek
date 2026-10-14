"""Development-only loopback browser walkthrough host."""
import tempfile
from pathlib import Path
from datatrust.web import create_app
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='numek-m6-browser-') as workspace:
        app=create_app(Path(workspace),data_roots=(Path.cwd(),))
        try:app.run(host='127.0.0.1',port=8036,use_reloader=False)
        finally:
            app.extensions['datatrust_m6_store'].cleanup()
            app.extensions['datatrust_m4_store'].cleanup()
            app.extensions['datatrust_m5_store'].cleanup()
