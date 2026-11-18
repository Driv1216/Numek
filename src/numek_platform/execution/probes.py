"""Module-state probes for warm-process isolation.

Kept separate from ``_child`` because the child entry runs as ``__main__``:
a registry defined there would be a different object from the one imported
by job modules.
"""
_STATE_PROBES = {}


def register_state_probe(name, probe):
    """Register ``probe() -> hashable`` describing module state that jobs must not change."""
    _STATE_PROBES[name] = probe


def probe_state():
    return {name: probe() for name, probe in _STATE_PROBES.items()}
