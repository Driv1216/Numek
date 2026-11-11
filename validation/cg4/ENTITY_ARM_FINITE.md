# Finite component inference for a narrow entity design

Status: implemented and checked within the recorded qualification envelope; not
general cluster inference or completion of CG4.

The failed complete-entity bootstrap profiles remain disabled. A separate caller-
selected `independent_entity_arms` design can reuse the established finite kernels
when each frozen comparison arm contains at most one potential observation per
entity. It must be chosen before H outcomes; it is never an automatic fallback.

Assume IID complete entities, independent of the frozen D/S hypothesis. Dependence
between observations of the same entity is unrestricted. For arm a, let I_ia
indicate that entity i contributes an eligible observation. Because there is at
most one potential observation, an included entity contributes one scalar Y_ia.
The pairs (I_ia, Y_ia) are IID across entities. Conditional on the observed arm size,
the included values are IID from Y_a given I_a=1. Hence the original Bernoulli
Clopper–Pearson or predeclared bounded-contribution Hoeffding interval applies to
that arm. Each arm's native event-weighted mean equals its included-entity mean.

For Bernoulli confusion cells and frozen-bin calibration contributions, the same
argument applies to the existing component intervals. Registered monotone interval
composition remains unchanged. Components and arms may overlap or be dependent:
Bonferroni only uses their marginal error bounds. With frozen m hypotheses and
c_h components for hypothesis h, allocation alpha/(m*c_h) still bounds simultaneous
noncoverage by alpha. No bootstrap, new numerical estimator or independence between
arms is inferred. This does not register native ranking/nonadditive intervals or
unbounded means.

The conditional denominator is the frozen objective's denominator. For example,
FNR additionally conditions on actual positives, while precision conditions on
predicted positives. Selective labels still define an observed-label estimand.
Their observation mechanism is not corrected by the entity design.

## Outcome-independent structural check

Require explicit entity keys and whole-entity D/S/H assignment. Count potential
records in the frozen membership-available population before applying outcome
validity, maturity or class-conditional filters:

- Complement: member records and applicable nonmember records, separately.
- Overall: member records and all applicable records, separately.
- Ceiling: member records only.
- Paired predictors: member records for each predictor's comparison arm.
- Reference/current periods: member records in each frozen period, separately.

Refuse any affected claim if an entity can contribute more than one record in an
arm. Missing labels cannot hide duplicate potential records. A declaration of
complete extraction/IID entities remains an external assumption: the check covers
admitted records and cannot prove unobserved records do not exist. Common shocks,
unknown required independence and prior exposure retain their existing refusals.

The stronger design is deliberately explicit. General `independent_entities`
does not silently acquire finite-row inference, even if a particular observed
label-filtered sample looks unique. Randomly dropping observations to one per
entity would change the event-weighted estimand and is not implemented. Existing
frozen hypotheses and their method choices remain immutable.
The population design must guarantee the potential-record constraint, not merely
pass an observed H check by chance. This mode cannot be selected after inspecting
H to rescue a general cluster design. Its stated error bound is conditional on
the frozen D/S claim and the true declared sampling design; it is not a guarantee
conditional on arbitrary outcome-dependent admission or selective reporting.

Required evidence: independent interval references, valid/invalid arm mappings,
missing-label and mixed-family refusal tests, a historical product journey,
null/coverage diagnostics with dependent observations inside IID entities, and
retained common-shock negative controls. No workspace-wide or causal guarantee.

## Recorded evidence and limits

Source `7d74efcb284f5bae24f4aef4359eef898f9ace83b179014a8059b537bcf246c1`
passed 271 CG4 tests. Nine product checks passed on Python 3.12; those checks plus
three qualification-tool checks passed on 3.14. Tests cover native CP/Hoeffding
references, selective-label duplicates, each comparator's arm mapping, mixed-family
refusal without changing allocation, and a retained historical assessment.

The fixed [qualification profile and raw evidence](results/finite-entity-arm-qualification-v93)
contain 30,000 null trials and 2,000 partial-null/power trials with overlapping
families of 1/10/32. None of the predeclared Holm-adjusted excess-error diagnostics
rejected. All 2,000 strong-effect gate-zero claims confirmed (one-sided 95% lower
power bound .99850). The 136 scalar product/public-SciPy references agreed to
9.992e-16. These are finite synthetic profiles; mathematical coverage still requires
the design assumptions above. This does not qualify discovery or general clusters.

Negative controls deliberately bypassed those assumptions: a global common shock
produced 200/200 noncovering families and 94 false-confirmation families; duplicated
rows produced 74/200 and 40/200 respectively. Both remain in the evidence. A
[descriptive audit of all power-panel gates](results/verification/finite-entity-arm-power-detail-v95.json)
also shows substantial conservatism: effects .225 and .1875 against delta .15
confirmed in 1,022/2,000 and 36/2,000 trials respectively. Strong-effect power must
not be extrapolated to near-threshold effects.

The browser journey used explicitly known-exposed synthetic evidence and correctly
refused inference despite valid arm structure. Shareable HTML/JSON and the two-page
PDF retained that refusal and design qualification while withholding private
declarations. See the [verification inventory](results/verification/entity-arm-v97-manifest.json).
