"""Source connectors: how batches reach ingestion besides HTTP push (plan H.5).

The ``SourceConnector`` seam is fixed now; only the directory connector is implemented in CG7.
Database and object-store (S3) pull connectors are deferred until a concrete need justifies their
qualification cost. A connector produces (batch id, bytes) pairs; ingestion's idempotency
(source, batch id, bytes) makes re-delivery safe, and connectors never delete customer data.
"""
from typing import Iterable, Protocol


class SourceConnector(Protocol):
    def batches(self) -> Iterable[tuple[str, bytes]]:
        """Yield (stable batch id, raw bytes) for data not yet delivered."""


class DirectoryConnector:
    """Files in one directory become batches (``ingest.pull_directory`` records fingerprints)."""

    def __init__(self, installation, source_id, directory, *, processed=None):
        self.installation, self.source_id, self.directory, self.processed = installation, source_id, directory, processed

    def deliver(self):
        from .ingest import pull_directory
        return pull_directory(self.installation, self.source_id, self.directory, processed=self.processed)
