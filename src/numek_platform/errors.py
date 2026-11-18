"""Stable, code-bearing platform errors.

Messages never contain evidence values, SQL or filesystem paths, so they can
be shown to API clients unchanged.
"""


class PlatformError(Exception):
    def __init__(self, message, code='platform_error', *, retryable=False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class FenceLost(PlatformError):
    """The caller no longer owns the job attempt it is acting for."""

    def __init__(self, message='Job ownership was lost; this attempt may not write.'):
        super().__init__(message, 'fence_lost')


class IntegrityFailure(PlatformError):
    """Stored bytes do not match their recorded identity."""

    def __init__(self, message='Stored evidence failed verification.'):
        super().__init__(message, 'evidence_corrupt')
