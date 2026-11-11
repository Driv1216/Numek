"""Trusted local predictor execution; hardware evidence is separately qualified."""
from .contracts import PredictorSpec,ExecutionSpec,DeviceSpec,ExecutionLimits,ArtifactFile,OutputBinding
from .services import inspect_predictor,register_predictor,execute_predictor,qualify_predictor
from .result import ExecutionResult
from .adapters import register_host_predictor
from .bridge import as_evaluation_spec,as_reliability_spec
from .restatement import ExecutionRestatementSpec,restate_execution
from .legacy import convert_legacy_predictor
