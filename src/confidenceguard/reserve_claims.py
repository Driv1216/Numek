"""G.8 sealed-reserve claims for CG4 confirmation and CG5 policy assessment.

Ordering: (1) the study family and its selection rules are frozen; (2) the
sealed-reserve entities eligible for the family's assessment role are found
from identities only (keys, clocks, outcome existence, and the family's
identity-only role rule); (3) one ledger transaction reserves and consumes
them; (4) inspection and assessment read under that study authority.

Ordinary workflows are unchanged: v2 workspaces, tracking disabled, no active
reserve, roles taken from a data column (not decidable from identities), or no
eligible entity all leave the reserve withheld. The claim is made once per
family; retries, scheduled looks and numerical recomputations reuse it.
"""
from .history_contracts import instant


def claim(workspace, *, family_digest, selection, role_of, unit, assessment_role, purpose_label, schedule):
    """Return the family's claim receipt (new or existing), or None for the ordinary workflow."""
    from .platform_catalog import PlatformCatalog
    if workspace is None or not isinstance(workspace.catalog, PlatformCatalog):
        return None
    catalog = workspace.catalog
    existing = catalog.family_claim(family_digest)
    if existing is not None:
        return existing
    k = selection.catalog_sequence if selection.catalog_sequence is not None else catalog.head()
    ranges = [(instant(w.start), instant(w.end)) for w in selection.windows]

    def eligible(identity):
        key = identity['entity'] if unit == 'entity' else identity['opportunity_key']
        return key is not None and role_of(key) == assessment_role

    return catalog.claim_reserve(family_digest=family_digest, namespace=selection.namespace, k=k, tick_ranges=ranges,
                                 eligible=eligible, purpose_label=purpose_label,
                                 metadata={'restatement_schedule': schedule, 'assessment_role': assessment_role})
