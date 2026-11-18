"""NUMEK evidence and execution platform.

Shared infrastructure for persistent NUMEK products:

* PostgreSQL is the single transactional authority for evidence identity,
  publication order (the catalog sequence K), governance, jobs and audit.
* Bulk evidence lives in an immutable object store and is verified by hashing
  the exact bytes that are consumed.
* Jobs run under fenced leases on worker hosts; a stale owner can never
  publish.

Analytical semantics (CG1-CG6 kernels, contracts and refusals) do not live
here. This package only stores, orders, protects and executes.
"""

__version__ = '0.1.0'
PLATFORM_SCHEMA = 'numek'
