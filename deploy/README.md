# Deploying NUMEK ConfidenceGuard operations (CG7)

One distribution runs three kinds of process against one installation (a PostgreSQL database, an object store and a
secrets store):

| Process | Command | Notes |
|---|---|---|
| API and console | `confidenceguard ops serve` | gunicorn, `gthread` workers. Beyond loopback it needs TLS (`--tls-cert`/`--tls-key`) or `--trusted-proxy --proxy-ips IP`. |
| Controller | `confidenceguard ops controller` | The epoch-fenced leader: scheduling, window closing, conditions, notifications, retention, GC. Running two is safe; one leads. |
| Worker hosts | `confidenceguard ops worker --lanes essential,investigation,maintenance` | Claim fenced jobs; run as many as the host's budget allows. |

## Profiles

| Profile | What | Standing |
|---|---|---|
| **P-LOCAL** | macOS/Linux, a managed PostgreSQL cluster under the installation root (Unix socket, owner-only), loopback API. `confidenceguard ops init --root DIR`. | Used by every test and measurement in this repository (macOS arm64). |
| **P-SERVER, systemd** | `deploy/systemd/`: three units, hardened (`ProtectSystem=strict`, writes only `/var/lib/numek`), the DSN in `/etc/numek/ops.env`. | **Intended, not qualified.** Not run on Linux hardware here. |
| **P-SERVER, OCI** | `deploy/oci/Containerfile` and `deploy/compose/compose.yaml` (PostgreSQL, a one-shot init, API, controller, worker; read-only root filesystem, no capabilities). | **Intended, not qualified.** See below. |

Neither P-SERVER form has been run under the plan's W-REF workload or the M.3 fault injection on Linux x86_64, so
no capacity or resilience claim is made for them.

## Installing (systemd)

1. Create a `numek` system user, and `/var/lib/numek` (mode 0700, owned by `numek`).
2. Create a virtual environment at `/opt/numek/venv`, then install with hashes:
   `pip install --require-hashes -r constraints/cg7-ops-linux-x86_64-py313.lock`, and the wheel with `--no-deps`.
3. Write `/etc/numek/ops.env` from `deploy/systemd/ops.env.example` (mode 0640, `root:numek`).
4. Initialise once: `sudo -u numek env $(cat /etc/numek/ops.env) confidenceguard ops init --root /var/lib/numek --dsn-env NUMEK_DSN`.
   The installation records only the variable name `NUMEK_DSN`, never the connection string.
5. Create the first administrator: `confidenceguard ops user create alice --role admin` (the password is read from
   stdin). Further users, roles and tokens are managed in the console's Admin area.
6. Put the TLS certificate and key in `/etc/numek/tls/`, then
   `systemctl enable --now numek-ops-api numek-ops-controller numek-ops-worker@1`.

## Before a substantial workload: preflight

`confidenceguard ops preflight --workload W-DEV --scratch /var/lib/numek-scratch --out preflight.json` calibrates on a
scratch installation (about 10⁶ facts through the real ingestion path), projects database, WAL, objects, backup and
memory, and admits the workload only if it fits within 80% of the free disk and of the memory. A workload that does
not fit is recorded `not_admitted_on_host` with its identity kept; a smaller workload has its own name and lists how
it differs.

## Backups and audit anchors

- `confidenceguard ops backup create --installation <root> --destination <new dir>` takes the recoverable cut: a
  database snapshot, the objects it references, the installation configuration (with its digest) and a keyring wrapped
  with the backup passphrase. The keyring holds every data key an included object needs (the backup refuses if one is
  missing), the other live data keys, and every operational secret: sealed-reserve assignment secrets, notification
  channel secrets, and the monitoring unit-order and audit-sampling secrets. A restore therefore needs nothing else from
  the old secrets directory. The recovery point is the snapshot: batches acknowledged after it are not covered.
  (`numek backup create` is the same cut for a bare platform database, given its object and secret stores.)
- Export audit-chain anchors to a file outside the installation on a schedule:
  `confidenceguard ops audit anchor --sink /var/log/numek/anchors.jsonl`, and check them with `audit verify --sink`.

## Known limits

- The object store is a local filesystem, so the API, controller and workers must share one host (or one volume).
  Several hosts need the S3-compatible store, which is deferred.
- D-1: ConfidenceGuard workspaces bound to a shared installation keep per-workspace object stores; there is no
  installation-wide backup for them, and no production-readiness claim is made for shared installations.
