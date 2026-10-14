"""Local authored acceptance server; no production shortcuts or fault settings."""
from pathlib import Path
from datatrust.web import create_app
from validation.m9.fixtures import financial

ROOT=Path(__file__).parent.absolute()


if __name__=='__main__':
    data=ROOT/'data/browser_financial';financial(data)
    app=create_app(ROOT/'results/browser_workspace',data_roots=(ROOT/'data',))
    app.jinja_env.auto_reload=True
    try: app.run(host='127.0.0.1',port=9049,debug=False,use_reloader=False)
    finally:
        for name in ('datatrust_m4_store','datatrust_m5_store','datatrust_m6_store','datatrust_m7_store','datatrust_m9_store'):
            if app.extensions.get(name): app.extensions[name].cleanup()
