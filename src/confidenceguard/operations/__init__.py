"""ConfidenceGuard CG7 reliability operations.

S4 (ingestion): ``registry`` (systems, deployments, versioned source contracts, ingest tokens),
``contracts`` (row checks and minimization), ``ingest`` (durable encrypted receipt, processing,
quarantine, watermarks, deployment events, directory pull), ``identity`` (deployment identity
standings and signed statements), ``retention`` (raw/quarantine retention and key shredding),
``web`` (the minimal authenticated ingestion HTTP surface) and ``jobs`` (worker-host job kinds).
The producer SDK is the separate ``numek_monitor`` package.
"""
