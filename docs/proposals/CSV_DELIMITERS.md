# Proposal: CSV separators other than commas

**Status:** approved and implemented (2026-10-19), with the recommended answers: a detected separator is applied and shown with a change control, M7 manifests stay comma-only, and classification JSON records a separator other than a comma.

## Why

Many real CSV files are not comma-separated. UCI's Bank Marketing file uses semicolons, and so do files exported by Excel in many European locales. Tab-separated exports are common too.

Today DataTrust reads every CSV as comma-separated. Given a semicolon file, it sees one column per row and offers no real outcome to choose. The app now explains this and asks for a comma copy, but DataTrust should simply read the file.

## Goal

- DataTrust reads CSV files separated by commas, semicolons, tabs or vertical bars.
- The separator in use is always visible before you confirm, and it is recorded in the canonical outputs.
- For comma files, every result, report, fingerprint and saved analysis stays byte-for-byte identical to today.

## What the current code does

| Path | Used by | How it reads CSV today |
|---|---|---|
| `ingestion.read_csv` | Core: classification, regression, unlabeled, M3 | `pandas.read_csv` with its default comma |
| `ingestion.inspect_source_tokens` | Core parsing review | `csv.reader`, comma |
| `profiler._read` | Classification target inspection | `read_csv` with no parse options |
| `scalable` source staging | M4, and M5 through scalable relations | `csv.reader` and `pandas.read_csv(chunksize=…)`, both comma |
| `TextSourceSpec.delimiter` | M6 | Already supports any single character |
| `CrossRepresentationInputSpec.delimiter` | M9 | Already in the contract; the guided form doesn't expose it |
| `image_sources` manifests | M7 | `csv.DictReader`, comma |

**Where parsing is recorded**
- The parsing fingerprint is computed from an `effective` record that includes `"delimiter": ","`.
- `parsing_options_dict` serializes `CsvParseOptions`, the parse-options object, into the canonical JSON and the confirmation seals.
- Exception: the classification JSON (`to_legacy_dict`) leaves parsing out entirely.

## Design

### 1. Contract

- Add `delimiter: str = ","` to `CsvParseOptions`. It is keyword-only, so existing positional uses are unaffected.
- **Allowed values:** any single character that isn't a quote, a carriage return or a line feed. This matches M6's existing rule.
- **The app offers four:** comma, semicolon, tab and vertical bar.
- **Serialization:** `parsing_options_dict` omits `delimiter` when it is `,`, the same way it already omits an empty `column_missing_policies`. For comma files, the canonical JSON, the seals and the history entries therefore don't change.
- **Older inputs:** older `AnalysisConfig` JSON and older saved specs carry no `delimiter`, and keep loading as comma.

### 2. Reading

Every reader takes the separator from the declared `CsvParseOptions`:
- **Core:** `read_csv` passes `sep=`; `inspect_source_tokens` passes `delimiter=`; `effective["delimiter"]` records the declared value.
- **Classification target inspection:** receives the job's parse options instead of reading with none.
- **Scalable staging (M4, M5):** passes the separator to both its `csv.reader` and its chunked `pandas.read_csv`.

**What doesn't change:**
- Quoting and the header rule.
- The rule that a row's width must match the header: rows are never padded or dropped.
- Missing-value policies and column types.

The separator only decides where one cell ends and the next begins.

**Error messages** name the declared separator. For example: "CSV could not be parsed as a semicolon-separated file with a header."

### 3. Detection and confirmation

When a file is uploaded or added as a source, DataTrust tries the header and the first complete records with each of the four separators. A separator is **detected** only when all three of these hold:
1. Reading with commas gives a single column.
2. Exactly one other separator gives at least two columns.
3. That separator gives the same width on every sampled record.

In every other case DataTrust keeps commas, as it does today, and detects nothing. That includes a comma file that has semicolons inside quoted cells.

**Recommended behavior:** a detected separator is applied immediately and shown prominently. The analysis still waits for your confirmation.
- **Configure:** shows "Separator: Semicolon (detected)" with a selector to change it. Changing it reads the file again.
- **Confirm:** states the separator in effect.
- **The seal:** the confirmation seal covers the parse options, so changing the separator after confirming makes the confirmation stale.

**The alternative** is to never apply a detected separator automatically, show a suggestion instead, and have you pick it yourself. Question 1 below covers this choice.

### 4. Recording

| Output | What changes |
|---|---|
| Regression, unlabeled and M3 JSON | `parsing.options.delimiter`, only when it isn't a comma, plus the existing fingerprint (which now covers it) |
| M4 and M5 JSON | Each source's parsing record carries the separator when it isn't a comma |
| Classification JSON | Gains `parsing: {"delimiter": ";"}` only when the file isn't comma-separated. Comma files keep today's exact JSON. See question 3. |
| HTML and PDF reports | One line in the existing parsing or overview section, "Separator: semicolon", shown only when the file isn't comma-separated |
| Saved analyses | No change; they already store the canonical artifacts |

### 5. App (DataTrust frontend)

- **Upload step, core and M3:** a separator choice beside the file drop, with options Detect automatically (the default), Comma, Semicolon, Tab and Vertical bar. Configure shows the separator in effect and lets you change it.
- **M4 and M5:** a separator choice on each added source, with the same options. The value is stored with that source.
- **M9:** the guided "Add a source" form gets the separator field its contract already has.
- **M6:** unchanged; it already has the field.
- **M7:** image manifests stay comma-only in this change (question 2).
- **The separator notice:** the warning added last round now appears only when you choose Comma explicitly and the file still arrives as one column.

### 6. API and CLI

- **API:**
  - `POST /core/jobs` accepts `delimiter` (`auto`, `,`, `;`, `\t` or `|`).
  - `POST /core/job/configure` accepts `delimiter` to read the file again.
  - The M4 and M5 source endpoints accept `delimiter` for each source.
  - Values outside the allowed set get a 422 with the contract's message.
- **CLI:** `datatrust audit … --delimiter ';'`. The `parsing.delimiter` key in `--config` JSON works too.
- **Old pages:** the retired classic pages and their parity tests are unchanged; they keep commas.

### 7. Explicitly out of scope

- **Decimal commas** (`1,5`). In semicolon files from European locales, numbers often use a comma as the decimal mark. This change doesn't interpret them: such a column is read as text. If you declare it numeric, it fails loudly with the existing "contains invalid numeric values" error and is never silently coerced. A decimal-mark option would be a separate proposal.
- Detecting quote characters and encodings.
- Excel files (`.xlsx`).

## Verification

Proportionate, per the repository verification skill:

1. **Contract tests:** allowed and refused separators, omission when the separator is a comma, and loading older configs.
2. **Unchanged for comma files:** the existing suites pass unmodified, and the parity script stays identical. The canonical JSON, HTML and fingerprints of the validation datasets don't change.
3. **Equivalence:** a semicolon copy and a tab copy of the same data produce the same findings and scores as the comma original. Only the source digest and the recorded separator differ. Checked for classification on Bank Marketing (expected 69.0 · Elevated), regression on Bike, unlabeled, one M3 mode, M4 splits and M5.
4. **Detection tests:** a semicolon file, a tab file, a comma file with quoted semicolons (stays comma), a legitimate single-column file (stays comma), and ambiguous files (stay comma).
5. **API and browser:** one run of your `bank-full.csv` straight from Downloads (detected, analysed, saved, reopened), plus one M4 run with mixed separators.

## Questions for you

1. **Detection:** should DataTrust apply a detected separator immediately and show it (recommended), or only suggest it and wait for you to choose?
2. **M7 image manifests:** leave them comma-only for now (recommended), or include them too?
3. **Classification JSON:** record a non-comma separator there (recommended, so the report says how the file was read), or keep classification JSON frozen and record it in the HTML only?
