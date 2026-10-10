"""Temporary local browser verification runner; no production fixture behavior."""
from pathlib import Path
from datatrust.web import create_app
if __name__=='__main__':
    app=create_app(Path('/private/tmp/numek-m5-browser'),data_roots=[Path.cwd()])
    app.run(host='127.0.0.1',port=8766,debug=False,use_reloader=False)
