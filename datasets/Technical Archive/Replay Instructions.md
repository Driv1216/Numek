# Replay instructions

Use **Dataset and Findings.md** in the chosen dataset folder. Open the recommended report first and identify the input names and recorded purpose. For a simple CSV workflow, use those files in DataTrust and select the same target, field roles, and declarations. The active configuration in **Technical Evidence** records those settings.

For an exact replay, pass the local configuration to the corresponding public DataTrust entry point and use a fresh output directory. The JSON envelope is already paired with the source. The examples assume you have the matching DataTrust extras installed. Keep model-assisted benchmarks separate from ordinary analysis.

## Exact tabular replay

From the Numek repository, use this example with the configuration for your chosen dataset. It passes the declared task, roles, parsing and analysis options directly to DataTrust.

```sh
python -c '
import json, sys
from pathlib import Path
from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
config = json.loads(Path(sys.argv[1]).read_text())
dataset = config["dataset"]
if isinstance(dataset, str):
    dataset = {"path": dataset}
result = DataTrust.from_spec(
    DatasetSpec(**dataset),
    TaskSpec.from_dict(config["task"]),
    AnalysisConfig.from_dict(config["analysis"]),
).analyze_result()
print(result.to_dict()["profile"]["row_count"])
' 'datasets/Regression/Simple - Real Estate Valuation/Technical Evidence/Configuration - Property valuation and price coverage.json'
```

## Other workflows

Load `spec` and `analysis` or `options` using each workflow's contract classes. If using the CLI, save those two objects as separate JSON files and pass them with `--spec` and `--config`. Give the new result a separate output path under the dataset's Technical Evidence folder.

| Workflow | Product entry point | Contract types |
|---|---|---|
| Dataset comparison | `DataTrust.compare` | `ComparisonSpec`, `ComparisonConfig` |
| Time series | `datatrust temporal` or `DataTrust.audit_temporal` | `TemporalAuditSpec`, `TemporalAnalysisConfig` |
| Text | `datatrust text` or `DataTrust.audit_text` | `TextAuditSpec`, `TextAnalysisConfig` |
| Images | `datatrust images` or `DataTrust.audit_images` | `ImageAuditSpec`, `ImageAnalysisConfig` |
| Linked records and documents | `datatrust cross-representation` or `DataTrust.audit_cross_representation` | `CrossRepresentationAuditSpec`, `CrossRepresentationAnalysisConfig` |

For a published private reference, a historical manifest still binds its original identity. Generate a new native report and matching analysis JSON from the saved configuration to obtain a fresh protected manifest. Disclosure files from the prior evidence remain available in the archive. See `datatrust text-evidence --help` and `datatrust image-evidence --help` for selecting an explicitly authorized excerpt or overlay.

The original campaign notes refer to legacy paths and describe the original harness. Use the new active configurations for direct replays. The two optional model benchmarks remain frozen evaluation evidence.
