# CG7 sequential methods: SM1 and SM2

**Implementation:** `src/confidenceguard/operations/monitoring/eprocess.py`.

**Qualification:**
- locked protocol `validation/cg7/sequential_protocol.json`;
- run once by `validation/cg7/sequential_qualification.py`;
- results in `validation/cg7/results/sequential_qualification.json`.

**Authority:** CG7 plan sections G.3 and G.4, as corrected by Addendum R2.4 (SM1 error accounting, no epochs) and R2.5 (SM2 normal-mixture confidence sequence). Where the plan body and the addendum differ, the addendum and this document govern.

Both methods operate on **units**: X_i ∈ [0, 1], a bounded per-unit statistic rescaled by its declared *true* bounds.
- **Admitted statistics:**
  - error indicators;
  - coverage misses;
  - Brier score: [0, 1] for binary, [0, 2] for multiclass;
  - abstention, failure and missing-field indicators;
  - region-membership indicators;
  - deferral indicators.
- **Refused:** log loss and unbounded squared error.
- **Out-of-bounds values:** a deterministic contract violation; the kernel refuses them.

---

## 1. SM1: bounded-mean e-CUSUM change detector with resets

### 1.1 Definition

**Grid.** For a null level m₀ ∈ (0, 1), use the fixed geometric grid

  λ_k = (0.5 / m₀) · 2^{−k},  k = 0, …, K − 1,  K = 12,

with weights w_k = 1/K.

**Factors.** Each unit contributes the factor

  f_i^{(k)} = 1 + λ_k (X_i − m₀).

This is at least 1 − λ_k m₀ ≥ 1/2, so every factor is positive.

**Detector.** Each component runs the CUSUM e-detector

  C_0^{(k)} = 0,  C_t^{(k)} = max(C_{t−1}^{(k)}, 1) · f_t^{(k)}.

The mixture is D_t = Σ_k w_k C_t^{(k)}.

**Alarm.** The detector alarms at the first t with D_t ≥ 1/α. It then **resets** every component to 0 and continues.

**Log space.** The recursion is computed in log space: L_t = max(L_{t−1}, 0) + log f_t, with L = −∞ encoding C = 0, and log D_t computed by log-sum-exp. Under the null, L stays bounded above by the alarm threshold plus one factor and below by log ½. The log-space recursion therefore has no overflow, underflow or drift over arbitrarily long streams (Q-E1c: 10⁸ units).

**Brute-force form.** Unrolling the recursion gives

  C_t^{(k)} = max_{s ∈ seg(t), s ≤ t} Π_{i=s}^{t} f_i^{(k)},

where seg(t) is the set of units since the last reset. Q-E1b checks the implementation against this form.

### 1.2 Null hypothesis

  H₀: E[X_i | F_{i−1}] ≤ m₀ for every included unit i,

where F_{i−1} is everything observed before unit i. m₀ = U_ref + δ:
- U_ref is a finite upper bound of the reference mean at level α_ref (section 3);
- δ ≥ 0 is a declared practical tolerance.

### 1.3 Theorem (R2.4)

Let U be a stopping time with respect to (F_i): the decision to process unit s is made before X_s is revealed, so {U ≥ s} ∈ F_{s−1}. Let N_U be the number of alarms among the first U units. Under H₀,

  **E[N_U] ≤ α · E[U].**

In particular, for a deterministic n, P(any false alarm within n units) ≤ E[N_n] ≤ nα.

### 1.4 Proof

**Step 1: started products are supermartingales.** For a start s and component k, define

  M_t^{(s,k)} = Π_{i=s}^{t} f_i^{(k)} for t ≥ s, with M_{s−1}^{(s,k)} = 1.

Under H₀:

  E[f_i^{(k)} | F_{i−1}] = 1 + λ_k (E[X_i | F_{i−1}] − m₀) ≤ 1,

and f_i^{(k)} > 0. So M^{(s,k)} is a nonnegative supermartingale from time s − 1. So is the mixture M^{(s)} = Σ_k w_k M^{(s,k)}, which equals 1 at s − 1.

**Step 2: the detector is dominated by a sum of started mixtures.** Within a segment (the units after a reset, up to and including the next alarm), the brute-force form gives

  C_t^{(k)} ≤ Σ_{s ∈ seg(t), s ≤ t} M_t^{(s,k)}.

Mixing over k:

  D_t ≤ Σ_{s ∈ seg(t), s ≤ t} M_t^{(s)}.

**Step 3: bound the alarm count.** An alarm at τ requires D_τ ≥ 1/α, so

  1{alarm at τ} ≤ α · Σ_{s ∈ seg(τ), s ≤ τ} M_τ^{(s)}.

For each s, let σ_s be the first alarm time at or after s. This is a stopping time, possibly +∞, and it is the end of the unique segment containing s. Every alarm closes its own segment, and every s belongs to exactly one segment. Summing over the alarms at or before U:

  N_U ≤ α · Σ_{s ≥ 1} 1{U ≥ s} · M^{(s)}_{σ_s ∧ U}.

**Step 4: take expectations.** Fix s.
- 1{U ≥ s} is F_{s−1}-measurable.
- For a nonnegative supermartingale started at 1 and any stopping time T ≥ s − 1, possibly unbounded, E[M_T^{(s)} | F_{s−1}] ≤ 1. This is optional stopping at T ∧ n, followed by Fatou's lemma as n → ∞, with M_∞ the almost-sure limit.

Hence

  E[1{U ≥ s} M^{(s)}_{σ_s ∧ U}] = E[1{U ≥ s} · E[M^{(s)}_{σ_s ∧ U} | F_{s−1}]] ≤ P(U ≥ s).

Summing over s (Tonelli's theorem):

  E[N_U] ≤ α Σ_s P(U ≥ s) = α E[U]. ∎

**Remarks.**
- The resets matter only through step 3: each start contributes to exactly one segment.
- No independence is assumed; only the conditional-mean condition is.
- **Average run length.** The bound implies ARL ≥ 1/α for the first alarm (Shin, Ramdas & Rinaldo, 2023, e-detectors). The theorem above is the stronger, reset-aware statement CG7 relies on.

### 1.5 Consequences used by the product (R2.4)

- **No epochs.** A detector version runs until its definition or reference changes.
- **Calendar time.** E[false alarms by time t] ≤ α · E[U(t)].
  - The console shows α · U(t) as the "bound evaluated at observed volume". This is an estimate of the right-hand side, **not** a realized-period guarantee.
  - Operators choose α as the target number of false alarms per period divided by the expected units per period.
- **Families and fleets.** Expected counts add by linearity, with no independence needed: Σ_d α_d E[U_d]. The same sum bounds P(any false alarm) in the family over the horizon.
- **Shared references.** Let B_r = {μ_ref ≤ U_ref} for each reference r in use, with P(B_rᶜ) ≤ α_ref,r.
  - The guarantee is conditional: with probability ≥ 1 − Σ_r α_ref,r, every detector using those references satisfies E[N] ≤ αE[U].
  - Reusing a reference does not spend α_ref again.
  - This requires the reference sample to be independent of the monitored stream. Entity overlap is measured and shown.
- **Predictable inclusion (validity).** Whether a unit is included may depend only on information available before its outcome value: maturity, availability metadata, `entity_first`, and contract validity of non-outcome fields.
  - Inclusion that depends on outcome values is forbidden.
  - Units with invalid outcome values are excluded and counted. The formal standing then requires the declared assumption that invalidity is unrelated to the statistic.
- **The estimand is the included-unit conditional risk.** Informative lateness or selective labelling changes what the claim is about, not its false-alarm validity. A low exclusion rate is never treated as validity evidence.
- **Comparability (interpretation).** The reference uses the identical inclusion rule. If inclusion rates differ from the reference beyond the declared tolerance, the alarm is reported as "formal for the included population; population definition has shifted relative to reference".
- **Dependence.** Positive dependence (repeated entities, common shocks) can break the conditional-mean condition while the marginal risk stays acceptable.
  - `entity_first` thinning is the default.
  - Common shocks are a declared assumption.
  - Q-E4 measures the inflation when these assumptions fail.

### 1.6 Interpretation (fixed wording)

> The matured observed-label sequence since {start} is inconsistent (expected false alarms ≤ α per included unit) with per-unit conditional risk never exceeding {m₀}. Risk exceeded that level at some point after approximately unit {onset}.

- The **onset** is the start of the run of the component with the largest statistic at the alarm. It is **descriptive**.
- The post-onset mean shown with an alarm is descriptive and selection-biased.
- An alarm does not establish:
  - an average risk;
  - a cause;
  - a probability that degradation occurred;
  - anything about unlabelled, immature, reserve-held or late-excluded units.

---

## 2. SM2: anytime-valid recovery test (normal-mixture confidence sequence)

### 2.1 Why the betting procedure in plan G.4 was withdrawn

The product Π(1 + λ(θ − X_i)) is a supermartingale only under the pointwise null μ_i ≥ θ for every i. Rejecting that null shows only that risk dipped below θ at some point, which is not recovery. SM2 instead bounds the **running average of conditional means**.

### 2.2 Derivation

**The increments.** Let μ_i = E[X_i | F_{i−1}] and S_n = Σ_{i≤n} (μ_i − X_i). Each increment has conditional mean 0 and lies in [μ_i − 1, μ_i], an interval of length 1. By the conditional Hoeffding lemma, for every real λ:

  E[exp(λ(μ_i − X_i)) | F_{i−1}] ≤ exp(λ²/8).

So L_n(λ) = exp(λ S_n − λ² n / 8) is a nonnegative supermartingale with L_0 = 1.

**The mixture.** Mix over λ ~ N(0, 1/ρ), with ρ > 0 fixed in advance. By Tonelli's theorem the mixture is again a nonnegative supermartingale, with closed form

  L_n = (ρ / (ρ + n/4))^{1/2} · exp(S_n² / (2(ρ + n/4))).

**Inversion.** Ville's inequality gives P(∃ n : L_n ≥ 1/α) ≤ α. Inverting L_n < 1/α, with probability at least 1 − α, **simultaneously for every n**:

  μ̄_n ≤ X̄_n + (1/n) · √( 2 (n/4 + ρ) · log( √((n/4 + ρ)/ρ) / α ) ),

where μ̄_n = (1/n) Σ_{i≤n} μ_i. The inversion actually bounds |S_n|; SM2 uses only the upper side, which is conservative.

**Checks:**
- **Q-E1d** checks the closed form against numerical integration of the mixture, and computes the exact false-claim probability at the boundary null.
- **Q-E3** checks false claims under constant, alternating and drifting conditional means whose running average stays at or above θ.

### 2.3 Claims

| Claim | Condition | Error |
|---|---|---|
| **R2** fixed threshold | the upper sequence is below θ (declared acceptable risk) at any check, with ≥ 30 included units | ≤ α_rec |
| **R3** non-inferiority | θ = L_ref + Δ, where L_ref is the finite **lower** bound of the reference mean under its registered design, and the reference is independent of the post-start stream | ≤ α_rec + α_ref |

**Validity and parameters.**
- Both claims are valid under any data-dependent checking schedule, because the confidence sequence holds at every n simultaneously.
- ρ is fixed before verification starts. The default is planned support / 4, which places the tightest point near the planned support. Any fixed ρ is valid.
- In R3, a wide reference makes the claim **harder**, which is the correct direction.

**Interpretation and outcomes.**
- R2 and R3 concern the **average conditional risk of included units since the verification start**, not the instantaneous current risk.
- SM1 keeps running on the same stream; an SM1 alarm after a claim is a recurrence.
- If the plan horizon is reached without a claim, the result is `recovery_not_established`.
- R1 (operational, outcome-free) and R4 (causal effect: not claimed) are not SM2 claims.

---

## 3. Finite reference bounds

All bounds are one-sided at level 1 − α_ref. They are valid only under the reference's **registered sampling design**. Otherwise the detector or claim is descriptive: m₀ is the reference point estimate plus δ, and no probability statement is made.

| Statistic | Upper bound (SM1 m₀ = U_ref + δ) | Lower bound (SM2 R3 L_ref) |
|---|---|---|
| Bernoulli, independent units | Clopper–Pearson `clopper_pearson(k, n, α, 'upper')` | `clopper_pearson(k, n, α, 'lower')` |
| Bounded mean, independent units in [a, b] | Hoeffding: x̄ + (b − a)√(log(1/α)/(2n)) | x̄ − (b − a)√(log(1/α)/(2n)) |
| Repeated entities with a declared true maximum M per entity | CG6 bounded-cluster ratio (`robustness.inference.cluster_ratio`, `bounded_cluster_ratio_hoeffding_v1`) | same, lower side |

**Rules:**
- A reference must be fixed by a rule that ends before monitoring starts. A reference chosen after observing current data is `adaptive` and descriptive.
- m₀ ≥ 1 is refused.

---

## 4. Detection planner

**Growth rate.** For a sustained shift to mean m₁ > m₀, component k's log statistic grows at the expected rate

  g_k(m₁) = E log(1 + λ_k (X − m₀)).

log(1 + λ(x − m₀)) is concave in x. Among distributions on [0, 1] with mean m₁, the Bernoulli(m₁) law is the largest in convex order, so it **minimizes** g_k. The Bernoulli rate is therefore conservative for any bounded statistic with that mean.

**Expected delay.** The alarm needs D ≥ 1/α. It is enough that a single component reaches K/α. The planner's expected delay in units is

  (log(1/α) + log K) / max_k g_k(m₁),

a first-passage approximation that ignores overshoot.

**What the planner reports:**
- the delay in units;
- the delay in days at the expected included-unit rate. This rate excludes reserve-held units under the default `covariate_policy = exclude`, and units still maturing.

**Power status.** If the delay exceeds the declared maximum useful delay, the detector is marked `insufficient_power` and does not count as coverage.

**Validation.** Q-E5 checks the planner (median delay within [0.5, 1.5] × the prediction in four scenarios). This qualifies the number shown to users, not detector validity.

**Label delay.** The planner's delay starts once units mature. A 90-day maturity adds 90 days before any outcome detector can alarm.

---

## 5. Qualification summary

The locked protocol has these panels:

| Panel | What it checks | Status |
|---|---|---|
| Q-E1a | Exact enumeration of SM1 with resets, all 2²⁰ paths | Gates |
| Q-E1b | SM1 recursion equals the brute-force definition, and CUSUM ≤ Shiryaev–Roberts | Gates |
| Q-E1c | Log-space stability over 10⁸ units | Gates |
| Q-E1d | Exact SM2 false-claim probability, and the closed form checked by integration | Gates |
| Q-E2 | SM1 null simulations (Bernoulli, Beta, Markov-modulated, entity-thinned) | Gates |
| Q-E3 | SM2 null simulations | Gates |
| Q-E4 | SM1 assumption-violation controls | Documented limits; never gates |
| Q-E5 | Planner validity | Gates |

**Stopping rule.**
- An implementation bug reruns that panel only, and the rerun is recorded.
- A correctly implemented failure is retained, and the affected formal standing falls back to descriptive.
- Results and the protocol digest are in the results file. `validation/cg7/IMPLEMENTATION_STATUS.md` records the outcome.

## References

- Shin, Ramdas & Rinaldo. *E-detectors: a nonparametric framework for sequential change detection.* NEJSDS, 2023 (arXiv:2203.03532).
- Howard, Ramdas, McAuliffe & Sekhon. *Time-uniform, nonparametric, nonasymptotic confidence sequences.* Annals of Statistics, 2021.
- Waudby-Smith & Ramdas. *Estimating means of bounded random variables by betting.* JRSSB, 2024 (context for §2.1).
- Ville, J. *Étude critique de la notion de collectif.* 1939.
