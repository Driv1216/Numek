"""Worker-host job kinds for CG7 operations (``numek worker --registry confidenceguard.operations.jobs:REGISTRY``)."""
from numek_platform.execution.host import JobKind, Registry

GiB = 1024**3

REGISTRY = Registry([
    # Essential lane: ingestion must keep flowing while investigations run.
    JobKind('ops_ingest_batch', 'confidenceguard.operations.ingest:process_job', lane='essential', job_class='warm',
            rss_bytes=2 * GiB, threads=1, seconds=1800),
    JobKind('ops_retention', 'confidenceguard.operations.retention:retention_job', lane='maintenance', job_class='warm',
            rss_bytes=1 * GiB, threads=1, seconds=1800),
    # Monitoring keeps essential capacity: window evaluation, detector advance, estimators, rules, health.
    JobKind('ops_monitoring_cycle', 'confidenceguard.operations.monitoring.runtime:cycle_job', lane='essential',
            job_class='warm', rss_bytes=2 * GiB, threads=1, seconds=1800),
])
