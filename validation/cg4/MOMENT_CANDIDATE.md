# Fixed-time variance-bound prototype

**Validation only; not a registered or qualified CG4 confirmation method.** This
does not repair the failed generic/component BCa or bootstrap-t profiles. It adds
a stronger external assumption and cannot be silently selected for an old claim.

For IID complete units, assume a finite population variance upper bound v>0 is
justified before H. For a fixed positive lambda and the signed logarithmic Catoni
influence function psi, its exponential envelope gives

`E exp(±psi(lambda*(X-mu))) <= 1 + lambda^2*v/2`.

Independence, `1+x <= exp(x)` and Markov's inequality imply a two-sided confidence
set obtained by inverting

`abs(sum psi(lambda*(Xi-mu))) <= n*lambda^2*v/2 + log(2/a)`.

The prototype uses `lambda=sqrt(2*log(2/a)/(n*v))`, fixed from n, v and the
allocation. This is a fixed-n consequence of the influence envelope in Wang and
Ramdas, equations 29–32 and Lemma 8; it adds no confidence-sequence, sequential
reuse, monitoring or optional-stopping capability. Primary references:
[Wang and Ramdas](https://arxiv.org/abs/2202.01250),
[Catoni](https://doi.org/10.1214/11-AIHP454).

Event-weighted rates use four scalar means of complete-unit contributions:
comparator numerator/denominator and member numerator/denominator. Each receives
`alpha/(m*4)`; a fixed ceiling uses two components. Bonferroni needs no independence
between components, gates or hypotheses. Divide the component interval boxes only
when denominator lower bounds are positive; otherwise refuse. Monotone and
absolute-value transformations propagate the whole box. Authoritative CG reducers
still determine the reported metric; robust score inversion defines an interval,
not a replacement metric or diagnostic training target.

Bounds concern unconditional unit contributions, including membership zeroes.
For Bernoulli(.5) membership independent of a conditional loss with mean mu and
variance s2, numerator variance is `.5*s2 + .25*mu^2`, denominator variance `.25`.
Cluster bounds concern entire entity sums, including size variation and dependence
within entities. An observed sample variance, observed range, D/S fitted proxy or
conditional-loss variance alone is not the required population bound. Unknown or
false bounds give no guarantee. Temporal/common-shock dependence remains outside
the prototype. No mechanism here verifies upstream declarations.

Numerical centering is algebraic translation of the same fixed score; it does not
choose lambda from outcomes. Stable logarithms, bracketing, bounded root work,
outward endpoints and a conservative floating-point allowance are implemented.
That allowance is engineering qualification, not certified interval arithmetic.
Nonfinite inputs, unresolved roots, insufficient work and denominator ambiguity
remain explicit refusals. Independent high-precision envelopes, uncentered SciPy
roots and explicit ratio-corner references passed eight focused checks.

`qualify_moment.py` freezes ten 1,000-seed scenarios, allocations for m=1/10/32,
and separate deliberately invalid variance/dependence controls. Every row, refusal,
width, diagnostic and source identity is retained. These experiments can expose
implementation or usefulness problems; passing cannot prove unknown population
assumptions. Full joint-family, useful-power, resource and full-pipeline evidence
and explicit frozen assumption contracts remain necessary before any product
proposal. Existing finite bounded and Bernoulli methods remain unchanged.
