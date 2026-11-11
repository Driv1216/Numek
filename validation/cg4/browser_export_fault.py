"""One-shot loopback verification host with a deliberately failing PDF converter.

No product fault switch or execution framework. Reopen synthetic evidence through
the normal browser, then exercise the real supervisor/export/job/download flow.
"""
import argparse
from pathlib import Path
import tempfile

from confidenceguard import compat,transport

ORIGINAL_EXPORT=transport._export


def forced_export(result,path,format,audience,disclosure,*,progress=None):
    original=compat.pdf
    def unavailable(*args):raise RuntimeError('Synthetic PDF renderer failure for CG4 verification.')
    compat.pdf=unavailable
    try:return ORIGINAL_EXPORT(result,path,format,audience,disclosure,progress=progress)
    finally:compat.pdf=original


def main():
    from datatrust.web import create_app
    from flask import request
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8046)
    parser.add_argument('--data-root',required=True);args=parser.parse_args()
    root=Path(args.data_root).resolve();expected=Path(__file__).resolve().parents[2]/'validation/cg4/browser_inputs_v2.nosync'
    # The helper lives in a captured source tree; the caller's synthetic root
    # may be in the original checkout. Its fixed basename identifies this fixture.
    if not root.is_dir() or root.name!=expected.name:raise ValueError('Use the owned CG4 synthetic browser fixture root.')
    transport._export=forced_export
    with tempfile.TemporaryDirectory(prefix='numek-cg4-export-fault-',dir='/private/tmp') as directory:
        app=create_app(Path(directory),data_roots=(root,))
        @app.after_request
        def label(response):
            if request.path=='/confidenceguard' and response.mimetype=='text/html':
                response.direct_passthrough=False
                response.set_data(response.get_data().replace(b'<h1>ConfidenceGuard</h1>',
                    b'<p role="status">CG4 verification host: PDF renderer deliberately fails.</p><h1>ConfidenceGuard</h1>'))
            return response
        print(f'Synthetic CG4 export-fault verification: http://127.0.0.1:{args.port}/confidenceguard',flush=True)
        try:app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=False)
        finally:
            for key,value in app.extensions.items():
                if key.endswith('_store') and hasattr(value,'cleanup'):value.cleanup()


if __name__=='__main__':main()
