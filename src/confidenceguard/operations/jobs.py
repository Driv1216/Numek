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
    # Investigations never compete with the essential lane (plan C.5).
    JobKind('ops_investigation', 'confidenceguard.operations.intelligence.planner:investigation_job', lane='investigation',
            job_class='isolated', rss_bytes=4 * GiB, threads=2, seconds=3600),
])
