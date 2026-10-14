# M6 Text Reliability Intelligence

Implemented on 2026-10-11. Schema `1.5`, methodology `text_reliability_v1`.
M1–M5 APIs, report dispatch and historical evidence remain compatible. M5's
understanding gate is accepted. M6 has no universal score, cloud inference,
correctness certificate, automatic cleaning or general multimodal loader.

## Use the capability

```python
from datatrust import (
    DataTrust, TextAuditSpec, TextInputSpec, TextSourceSpec, TextFieldSpec,
    TextAnnotationSpec, TextAnalysisConfig,
)

spec = TextAuditSpec((TextInputSpec(
    "corpus", TextSourceSpec("/absolute/data/messages.csv", format="csv"),
    fields=(TextFieldSpec("text", "message", required=True),),
    id_selector="id", split_selector="split",
    annotations=(TextAnnotationSpec("text", "label", expectation="required"),),
),), allowed_roots=("/absolute/data",))
result = DataTrust.audit_text(spec, TextAnalysisConfig())
artifacts = result.generate_artifacts("/absolute/out/report.pdf", format="pdf",
                                      json_path="/absolute/out/analysis.json")
# The private manifest is separate from the report.
reference = next(iter(result.private["locators"]))
location = result.resolve_evidence(reference, allowed_roots=("/absolute/data",))
```

The supervised API must run under the usual `if __name__ == "__main__":` guard
in standalone multiprocessing scripts. Contracts have strict `from_dict()` and
`to_dict()` methods. `TextAuditSpec.from_dict(..., base_directory=...)` resolves
relative source paths and allowed roots against the specification directory.

```sh
datatrust text --spec text-spec.json --config text-config.json \
  --out report.pdf --format pdf --json-out analysis.json
datatrust text-evidence --manifest .datatrust-private/AUDIT_ID/manifest.json \
  --report analysis.json --ref evidence_REFERENCE --data-root /absolute/data
```

`--show-content` explicitly reveals a bounded excerpt. Report excerpt disclosure
uses `--excerpt-ref` and `--data-root`; the private default has zero excerpts.
`datatrust ui` exposes `/text`: task → sources/assets → mappings and semantics →
models/work limits → confirmation → run/cancel → evidence and downloads.
Every accepted structure is configurable with guided controls. JSON import is
optional. Source uploads and manifests survive worker cleanup in session-owned
storage; shutdown removes that owned storage.

## Accepted data and declarations

CSV preserves lexical cells, headers and literal `NA`. JSONL uses physical
UTF-8 lines with object roots. Selectors are column names or JSON Pointers, never
expressions. CSV nested collections require explicit `json_columns`.

- Corpus, classification/multilabel and paired generation use mapped fields,
  declared task inputs/outputs, identifiers, source roles and split selectors.
- Token annotations declare tokens, labels and optional BIO/BIOES/BILOU semantics.
  String tokens use earliest monotone literal alignment; supplied offset tokens
  are checked directly. Alignment does not establish a linguistic tokenization.
- Span/QA annotations declare half-open offsets and optional literal span text.
  Supplied span labels are checked lexically. Empty/no-entity annotations are
  valid where declarations permit them. QA answerability is explicitly mapped.
- Associated annotation tables declare `content_source` and
  `content_id_selector`; only unique lexical identities join.
- Conversations accept nested messages or flat conversation/order mappings,
  explicit roles, tool references and completion/closure requirements. Parallel
  calls and nonalternating roles are permitted. Tools are never executed.
- Retrieval sources declare document/chunk/query/judgment/reference semantics.
  Extractive chunks verify literal parent spans and interval-union coverage;
  transformed chunks do not acquire an extractive alignment claim. Unknown
  judgments are not negatives. Duplicate IDs block dependent joins.
- Local `.txt` references and PNG/JPEG associations use `AssetSpec`, checksum
  declarations and allowed roots. Images receive compatibility/provenance checks,
  not image or caption understanding.

Physical occurrences, explicit logical IDs and representation equality are
separate. Raw text is preserved. Raw and NFC equality are separate facts;
casefold/whitespace views require explicit selection. Offsets always address
original decoded text: code points, UTF-8 bytes, UTF-16 units or supplied-token
indices. Splitting a character is invalid. Normalization never remaps spans.
Unicode 16 scripts/graphemes are pinned; unknown-to-version code points are not
invalid text. Scripts do not establish language.

## Evidence, coverage and bounded search

Required checks cover every framed record and valid applicable mapped item under
hard limits: framing, content states/lengths/Unicode, exact equality, supplied
annotations, conversation requirements and retrieval integrity/coverage.
Malformed JSONL lines and invalid mapped/nested items remain counted with locators;
usable siblings survive. Broken CSV framing/decoding/width, invalid declarations,
source mutation, cancellation and required-resource limits fail the whole audit.
All-invalid input can complete framing evidence, with dependent scope blocked.

Vocabulary, repeated nonblank lines, near duplicates, passages, language and
semantic neighbors have disclosed selected populations and work ledgers. Invalid
records are never silently removed. Selected vocabulary is a lower bound; lexical
effects describe examined populations. `lexical_complete` fails if declared
complete lexical work cannot fit. Selection uses frozen input hashes, seed and
source/split/field/kind/length strata. `comparison_side_reserved_split_stratified_v2`
round-robins comparisons in four priority tiers: requested evaluation comparisons,
other evaluation–training/document/chunk comparisons, other requested comparisons,
then within-source work. Missing sides are reserved together before a comparison
spends its first units. A budget of one cannot represent two new sides; coverage
reports that shortfall or an unavailable side. Existing selected sides may be reused
by another comparison; allocation counts distinguish new units from final side
populations. Disk-backed queues retain bounded metadata batches, not corpus text.
Identical inputs/declarations/seed reproduce selection. Language and embedding
parents use the same scheduler with their own eligibility and unit bounds.
Selection reservations do not guarantee both sides survive later signature,
tokenizer or inference work limits. Near-search coverage separately records indexed
unique units on each comparison side; model coverage records actual tokenized and
embedded parents by declared source role.

Five-grapheme set Jaccard ≥0.80 is a review criterion. MinHash only emits candidates;
actual shingles verify intersection/union, so hash collisions cannot prove a pair.
The fixed calibration grid selected **20 bands × 7 rows, cap 1,024 per bucket**:
≥99% observed recall in each recorded ordinary stratum, with lower charged work
under the prescribed selection rule. This does not promise corpus-wide 99% recall.
Forced saturation retained about 3.06% of oracle positive pairs, accurately disclosed.
Evaluation pair scheduling precedes remaining pairs; exact content is collapsed
for search and occurrence/split multiplicities are restored in retained findings.
Small eligible scopes use an all-pairs oracle when the same work budget permits.

Winnowing separately finds and verifies literal passages, including containment
that low whole-document Jaccard misses. Related chunks, shared prompts and templates
need context. Near-pair similarity is not transitive. Bounded zero findings do not
establish absence. Private references expose shared prefixes/differing raw context
without silently removing boilerplate or remapping normalized offsets.

## Offline models and resource safeguards

Optional imports are isolated. Install `.[text-language]` or
`.[text-embeddings]` only when needed. Lingua 2.1.1 runs with an explicit language
set and bounded source windows; margins are not calibrated probabilities.
E5-small uses revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, publisher-verified
local safetensors/tokenizer files and a SHA256 `datatrust-model.json` manifest.
See the development-only model acquisition script in `validation/m6/` for the
required manifest shape. Production loading is local-only, with downloads and
remote code disabled. CPU float32, pinned runtimes, deterministic settings,
attention-mask mean pooling and L2 normalization are recorded.

`token_windows_v1` proposes 448 content tokens with 64-token overlap, snaps outward
to original grapheme boundaries, retokenizes the actual prefixed source slice and
shrinks deterministically below 512 total tokens. It never decodes token IDs into
source text or silently truncates. Retrieval documents/chunks use `passage: `;
queries and symmetric similarity use `query: `. `exclude_long` is explicit.
Window allocation takes the first window across selected parents, then the last,
then evenly spaced interiors, with ≤16 per parent and ≤2,000 total. A constrained
global budget or tokenizer-work exhaustion can leave a long parent with only its
first window. Both endpoints are claimed only when actually embedded. Coverage
records selected, tokenized and embedded parents by source/declared role, incomplete
and unembedded parents, endpoint shortfalls, and retained allocated/embedded indices.
Original source intervals and interval-union coverage remain explicit; unknown
window counts remain unknown.
Every tokenization/repair/inference call is charged: input bytes are reserved first;
emitted-token work is charged on return, including a final rejected whole call.
Tokenizer vocabulary follows that same accounting and stops on the first rejected
call; accepted vocabulary counts remain separate from attempted emitted-token work.
Exact blockwise cosine comparisons use a two-million pair budget and top five
neighbors. A segment match does not establish whole-document equivalence.

DuckDB disk relations and the existing supervised worker enforce 2 GiB engine
memory, 6 GiB sampled RSS, two threads, 30 minutes, 64 GiB workspace, 2 GiB disk
reserve and 32 MiB public result defaults. Text/asset/annotation/search/model work
limits are separate, explicit and configurable. Hard required limits fail;
optional work stops at whole-unit boundaries with honest coverage. Unexpected
optional-stage failure fails the job, publishing no partial completed evidence.
This deliberately uses the whole audit as the atomic publication boundary
(`whole_audit_atomic_fail_closed`), a stricter interpretation of the planned
optional-stage rollback contract. A native model or database exception may leave
the connection, collector or private locators untrustworthy; required-only publication
would claim successful recovery without proving it. Failure terminates publication
and deletes the owned workspace, so no half-built index/findings can be reused.
Previously completed exports survive. Expected budget stops and declared alignment
exclusions remain successful bounded evidence. There is no partial-success result
for an unexpected fault; the caller receives a structured failure and must rerun.
Monitoring is not an OS quota and can overshoot between samples.

## Private exports and evidence lifecycle

HTML/PDF/JSON exclude raw text, vocabulary/labels/identifiers, tool arguments and
private paths by default. Audit-scoped opaque references bind to a separate strict
manifest containing frozen declarations, source hashes and exact locators, not
an automatic corpus copy. New exports are 0600; new private directories are 0700.
A current caller supplies allowed roots. Resolution verifies report/manifest binding,
source integrity before/after reading and exact located content; changed/deleted
sources become unavailable. There is no nearby-row or text-match repair.

At most 20 explicitly resolved excerpts, 240 displayed characters each and 4,800
per export are permitted. Controls are exposed, markup escaped and bidi isolated.
PDF resource access cannot fetch corpus assets. Analysis and disclosure identities
are separate; permissive artifacts cannot satisfy a private-default request.
Collision protection includes inputs, assets, models, manifests and export variants.
Cleanup removes only owned matching artifacts, preserving conflicts and historical
files. Digest binding is integrity evidence, not authentication against replacing
both report and manifest. Aggregates are private information, not anonymized data.

Executive actions group equivalent review instructions (including raw/NFC duplicate
review) while keeping each representation's technical evidence and counts separate.
Counts are never summed into an invented duplicate total. The report states the
observed population, declared violations to review, contextual candidates and
examined/unanswered scope. Topics flow continuously across pages; strict JSON retains
the full bounded technical evidence and coverage.

## Verification and measured limitations

The authoritative repository Verification skill governed coherent units, narrow
foundational checks and final closure. New evidence is under `validation/m6/results/`;
public/prepared/model bytes are pinned by manifests and excluded from Git. The
runtime lock records the validated local environment, not a universal platform lock.

Validation covers SMS, UD English/Hindi, SQuAD v2, OpenAssistant, SciFact and an
explicit four-image/sixteen-association fixture. Transformations, licenses, hashes,
subsets and negative controls are recorded. Natural-data checks establish population
accounting and execution, not universal methodology validity or annotation truth.
The closure ledger records browser/PDF inspection, tests, historical reuse and
capacity measurements. Narrow 100 MiB/1 GiB text workloads, expanded annotation,
asset-heavy and model-enabled workloads disclose exact populations and bounded
search settings. They are descriptive local measurements, not capacity guarantees.

The independent-review correction pass passed **400 tests in 33.51 seconds**,
including fourteen new regression cases and actual offline-model checks. Five
representative reports were reprojected from unchanged completed evidence and all
39 pages visually inspected. Historical analysis retains its original selection
version; focused tests establish the new allocation behavior. No expensive capacity
or LSH calibration campaign was repeated. See the [correction record](../validation/m6/REVIEW_CORRECTIONS.md)
and [machine-readable ledger](../validation/m6/results/review_corrections/closure.json).
