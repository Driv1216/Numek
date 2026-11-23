"""Label acquisition guidance (plan G.6, corrected claim).

1. **The operational priority list** ranks groups by exposure × projected excess risk. It is a *heuristic for
   impact*, not an uncertainty-reduction claim.
2. **Neyman allocation** estimates the current-population risk Π = Σ_g w_g r_g. It allocates
   n_g ∝ w_g·√(r_g(1 − r_g)), with r_g taken from the frozen reference (0.5 when a group has no support).

   This minimizes the variance of the stratified estimator **only if labels are obtained by random sampling
   within strata**, and the guidance states that requirement. It also reports the expected 95% half-width under
   Neyman allocation against proportional allocation.
"""
import math


def neyman(shares, risks, total):
    """Integer allocation (largest remainder) of ``total`` labels across groups."""
    weights = {g: shares[g] * math.sqrt(max(r, 1e-9) * max(1 - r, 1e-9)) for g, r in risks.items() if shares.get(g)}
    norm = sum(weights.values())
    if not norm:
        return {}
    raw = {g: total * w / norm for g, w in weights.items()}
    out = {g: int(math.floor(v)) for g, v in raw.items()}
    for g in sorted(raw, key=lambda g: -(raw[g] - out[g]))[:total - sum(out.values())]:
        out[g] += 1
    return out


def half_width(shares, risks, allocation):
    terms = [shares[g] ** 2 * risks[g] * (1 - risks[g]) / allocation[g] for g in allocation if allocation[g] > 0]
    return 1.96 * math.sqrt(sum(terms)) if terms else None


def label_guidance(installation, ctx, spec):
    from . import observations as observation_rules
    comp = ((ctx['reference'] or {}).get('packet') or {}).get('composition')
    if not comp:
        return {'state': 'unavailable', 'reason': 'no_reference_composition'}
    counts = {}
    for _w, packet in observation_rules._packets(installation, ctx, 'close'):
        for u in packet['units']:
            counts[u['group']] = counts.get(u['group'], 0) + 1
    total_units = sum(counts.values())
    if not total_units:
        return {'state': 'unavailable', 'reason': 'no_units_in_incident_windows'}
    shares = {g: n / total_units for g, n in counts.items()}
    risks = {g: (comp['groups'].get(g) or {}).get('risk') for g in shares}
    risks = {g: (r if r is not None and (comp['groups'][g]['n'] or 0) >= 30 else 0.5) for g, r in risks.items()}
    budget = int(spec.get('label_budget', 400))
    allocation = neyman(shares, risks, budget)
    proportional = {g: max(1, round(budget * s)) for g, s in shares.items()}
    baseline = sum(shares[g] * (comp['groups'].get(g) or {}).get('risk', 0.0) for g in shares if (comp['groups'].get(g) or {}).get('risk') is not None)
    priority = sorted(({'group': g, 'exposure': shares[g], 'projected_excess': max(0.0, risks[g] - baseline),
                        'score': shares[g] * max(0.0, risks[g] - baseline)} for g in shares), key=lambda r: -r['score'])
    return {'state': 'available', 'label_budget': budget,
            'neyman_allocation': allocation, 'proportional_allocation': proportional,
            'expected_half_width': {'neyman': half_width(shares, risks, allocation), 'proportional': half_width(shares, risks, proportional)},
            'requirement': 'Neyman allocation minimizes the stratified estimator variance only if labels are obtained by random '
                           'sampling within strata.',
            'operational_priority': priority,
            'priority_qualification': 'Exposure x projected excess risk is a heuristic for impact, not an uncertainty-reduction claim.'}
