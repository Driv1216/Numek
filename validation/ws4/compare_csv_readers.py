"""Core (pandas + whole-file check) against M4/M5 scalable ingestion, on files whose declared semantics both accept:
CSV with a header, a declared separator and UTF-8. Records accept/refuse and row counts; every difference is listed."""
import json, random, sys, warnings; warnings.simplefilter('ignore')
from pathlib import Path
if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]; sys.path[:0] = [str(root / 'src'), str(root)]
    from tests.test_csv_structure import generated
    from datatrust import DataTrust, DatasetSpec, TaskSpec, AnalysisConfig
    from datatrust.contracts import CsvParseOptions
    from datatrust.m4_contracts import AdvancedTabularOptions, ExecutionOptions
    from datatrust.m4_worker import analyze_scalable
    S = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/ws4-readers'); S.mkdir(parents=True, exist_ok=True)
    cases = {'blank_and_space_lines': (',', 'a,b\n1,2\n\n   \n3,4\n'), 'tab_only_line_in_tsv': ('\t', 'a\tb\n1\t2\n\t\n3\t4\n'),
             'mid_field_quote': (',', 'a,b\n1,x"y\n2,3\n'), 'quote_then_text': (',', 'a,b,c\n1,"x"y,3\n'), 'quoted_newline': (',', 'a,b\n1,"x\ny"\n2,3\n'),
             'bom': (',', '﻿a,b\n1,2\n'), 'trailing_separator': (',', 'a,b,\n1,2,\n'), 'crlf': (',', 'a,b\r\n1,2\r\n'), 'short_row': (',', 'a,b\n1,2\n3\n'),
             'unterminated_quote': (',', 'a,b\n1,"2\n'), 'duplicate_headers': (',', 'a,a\n1,2\n'), 'empty_header': (',', 'a,\n1,2\n')}
    rng = random.Random(4)
    for i in range(80):
        sep, text = generated(rng, rng.choice(['\n', '\r\n']))
        cases[f'generated_{i}'] = (sep, text)
    rows = []
    for name, (sep, text) in cases.items():
        p = S / f'{name}.csv'; p.write_bytes(text.encode())
        def core():
            try:
                r = DataTrust.from_spec(DatasetSpec(str(p)), TaskSpec('dataset_profile'), AnalysisConfig(parsing=CsvParseOptions(delimiter=sep))).analyze_result()
                return ('accepted', r.profile['row_count'])
            except Exception as e: return ('refused', type(e).__name__ + ': ' + str(e)[:80])
        def scalable():
            try:
                r = analyze_scalable(DatasetSpec(str(p)), TaskSpec('dataset_profile'), AnalysisConfig(parsing=CsvParseOptions(delimiter=sep), execution=ExecutionOptions(), advanced=AdvancedTabularOptions(dependencies=False, missingness=False)))
                return ('accepted', r.profile['row_count'])
            except Exception as e: return ('refused', type(e).__name__ + ': ' + str(e)[:80])
        a, b = core(), scalable()
        rows.append({'case': name, 'core': a, 'scalable': b, 'agree': a[0] == b[0] and (a[0] == 'refused' or a[1] == b[1])})
    differences = [r for r in rows if not r['agree']]
    summary = {'cases': len(rows), 'agree': len(rows) - len(differences), 'differences': differences}
    (S / 'readers.json').write_text(json.dumps(summary, indent=1)); print(json.dumps({'cases': summary['cases'], 'agree': summary['agree']}))
    for d in differences: print(d['case'], '| core', d['core'], '| scalable', d['scalable'])
