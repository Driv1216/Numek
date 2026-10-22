"""ConfidenceGuard prediction reliability workbench; separate from DataTrust analytics."""
from .contracts import (EvaluationSpec,EvaluationConfig,EvaluationError,TaskDefinition,SourceSpec,
    ModelIdentity,PredictionRunSpec,ProbabilitySpec,ScoreSpec,DecisionSpec,PredictionIntervalSpec,
    OutcomeSnapshotSpec,OutcomeSpec,ContextSnapshotSpec,CohortSpec,DecisionPolicySpec,
    ComparisonSpec,DisclosureSpec,SamplingSpec,ClockSpec)
from .result import EvaluationResult
from .engine import ConfidenceGuard,evaluate,inspect

__version__='0.1.0'
from .method_contracts import (ReliabilitySpec, MethodStudySpec, ApplicationSpec, MethodSpec,
    RoleSpec, RolePartition, RepresentationSpec, QuantileField, SampleSpec, SelectionSpec,
    SeparationSpec, InferenceSpec, MethodLimits)
from .fitted import FittedMethod
from .methods import fit_methods, apply_methods, study
ConfidenceGuard.fit_methods=staticmethod(fit_methods)
ConfidenceGuard.apply_methods=staticmethod(apply_methods)
ConfidenceGuard.study=staticmethod(study)
from .history_contracts import (WorkspaceConfig, PredictionBatchSpec, HistoricalRunBinding, OutcomeRevisionSpec,
    HistoricalCorrectionSpec, HistoricalWindow, HistoricalComparison, LongitudinalSpec, LongitudinalInferenceSpec,
    HistoricalEvidenceManifest)
from .history_result import LongitudinalResult
from .workspace import ReliabilityWorkspace
from .longitudinal import make_windows
ConfidenceGuard.workspace=ReliabilityWorkspace
