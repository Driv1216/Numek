"""Format fidelity spikes (evaluation only, not product code): what each format preserves, loses or makes ambiguous.
Usage: python validation/ws4/format_spikes.py WORKDIR TALL_CSV   (TALL_CSV: a 1M-row file from run_scalability.py data)"""
import json, sys, time, warnings, datetime as dt; warnings.simplefilter('ignore')
from pathlib import Path
S = Path(sys.argv[1]); S.mkdir(parents=True, exist_ok=True)
import pandas as pd, numpy as np, duckdb, pyarrow as pa, pyarrow.parquet as pq, openpyxl, psutil
out = {}
bank = pd.read_csv(Path(__file__).resolve().parents[1] / 'data/prepared/bank_marketing.csv')
tall = Path(sys.argv[2])

# Parquet: types, nulls, logical types, nesting, read cost.
df = pd.DataFrame({'code': ['007', '010', None], 'when': pd.to_datetime(['2024-01-02', None, '2024-03-04']), 'amount': pd.array([1, None, 3], dtype='Int64'),
                   'price': [pa.scalar(1.10).as_py(), 2.25, None], 'tags': [['a', 'b'], [], None], 'flag': [True, None, False]})
pq.write_table(pa.Table.from_pandas(df), S / 'typed.parquet')
back = duckdb.sql(f"SELECT * FROM read_parquet('{S}/typed.parquet')").df()
out['parquet_types'] = {c: str(t) for c, t in duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{S}/typed.parquet')").fetchall() and [(r[0], r[1]) for r in duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{S}/typed.parquet')").fetchall()]}
out['parquet_leading_zeros_kept'] = back['code'].tolist()[:2] == ['007', '010']
out['parquet_nulls'] = int(back.isna().sum().sum())
t = pd.read_csv(tall); pq.write_table(pa.Table.from_pandas(t), S / 'tall.parquet')
for name, fn in {'csv_pandas': lambda: pd.read_csv(tall), 'parquet_pandas': lambda: pd.read_parquet(S / 'tall.parquet'),
                 'csv_duckdb': lambda: duckdb.sql(f"SELECT count(*) FROM read_csv('{tall}')").fetchall(), 'parquet_duckdb': lambda: duckdb.sql(f"SELECT count(*) FROM read_parquet('{S}/tall.parquet')").fetchall()}.items():
    s = time.perf_counter(); fn(); out[f'read_{name}_s'] = round(time.perf_counter() - s, 3)
out['bytes_csv'] = tall.stat().st_size; out['bytes_parquet'] = (S / 'tall.parquet').stat().st_size

# Excel: what a typical business workbook does to values.
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Summary'; ws['A1'] = 'Quarterly export (draft)'
ws.append([]); ws.append(['id', 'opened', 'amount', 'total', 'region'])
for i in range(5):
    ws.append([f'00{i}', dt.date(2024, 1, i + 1), 10 * i, f'=C{4 + i}*2', 'North' if i < 3 else None])
ws.merge_cells('E4:E6'); ws2 = wb.create_sheet('Data'); ws2.append(['x', 'y']); ws2.append([1, 2])
wb.save(S / 'book.xlsx')
default = pd.read_excel(S / 'book.xlsx')
header3 = pd.read_excel(S / 'book.xlsx', header=2)
values = openpyxl.load_workbook(S / 'book.xlsx', data_only=True)['Summary']
out['excel'] = {'sheets': openpyxl.load_workbook(S / 'book.xlsx').sheetnames, 'default_header_row': list(default.columns)[:3],
                'with_header_row_3': list(header3.columns), 'leading_zero_ids': header3['id'].tolist()[:3], 'dates_dtype': str(header3['opened'].dtype),
                'formula_values_without_excel_recalculation': [values[f'D{r}'].value for r in range(4, 7)], 'merged_region_values': header3['region'].tolist()}
big = pd.DataFrame(np.random.default_rng(1).normal(size=(100_000, 10))); big.to_excel(S / 'big.xlsx', index=False)
proc = psutil.Process(); before = proc.memory_info().rss
s = time.perf_counter(); pd.read_excel(S / 'big.xlsx'); out['excel_read_100k_x10_s'] = round(time.perf_counter() - s, 2); out['excel_rss_growth_mb'] = round((proc.memory_info().rss - before) / 2**20)
big.to_csv(S / 'big.csv', index=False); s = time.perf_counter(); pd.read_csv(S / 'big.csv'); out['csv_read_100k_x10_s'] = round(time.perf_counter() - s, 3)

# JSON / JSONL: nesting and heterogeneous records.
recs = [{'id': 1, 'user': {'age': 31, 'city': 'Oslo'}, 'items': [1, 2], 'y': 'yes'}, {'id': 2, 'user': {'age': '40'}, 'y': 'no', 'extra': True}, {'id': '3', 'y': None}]
(S / 'r.jsonl').write_text('\n'.join(json.dumps(r) for r in recs))
out['jsonl_duckdb_schema'] = [(r[0], r[1]) for r in duckdb.sql(f"DESCRIBE SELECT * FROM read_json_auto('{S}/r.jsonl')").fetchall()]
out['jsonl_pandas_columns'] = list(pd.read_json(S / 'r.jsonl', lines=True).columns)
out['json_normalize_columns'] = list(pd.json_normalize(recs).columns)

# Markdown tables: no standard parser in dependencies; the ambiguities a parser must settle.
md = "| id | note |\n|:--|--:|\n| 1 | a \\| b |\n| 2 | **bold** |\n| 3 |\n"
out['markdown'] = {'escaped_pipe_and_short_row': md.count('\n'), 'parser_available_locally': False}
print(json.dumps(out, indent=1, default=str))
(S / 'spikes.json').write_text(json.dumps(out, indent=1, default=str))
