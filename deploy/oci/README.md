# NEXUS v1.1 — Durable OCI deployment

This deployment target exists to close Stage D with real persistent-storage evidence. It does not modify the immutable v1.0.0 seal.

## Required infrastructure

- OCI Always Free eligible compute in the tenancy home region.
- Persistent boot/block storage in the Always Free allowance.
- Ubuntu or Oracle Linux with Docker Engine and the Compose plugin.
- Public HTTPS terminated by an operator-managed reverse proxy or load balancer.
- TCP 3000 MUST NOT be exposed publicly; the compose contract binds it to loopback only.

Oracle documents Always Free compute and a combined 200 GB boot/block-volume allowance in the home region. Capacity and account eligibility remain external provider facts and must be checked when provisioning.

## Host layout

- repository: `/opt/nexus`
- durable workspace data: `/var/lib/nexus`
- operator backups: `/var/backups/nexus`
- runtime token: supplied only as environment/secret material; never committed

## Deploy

```sh
sudo mkdir -p /opt/nexus /var/lib/nexus /var/backups/nexus
sudo chown -R "$USER":"$USER" /opt/nexus /var/lib/nexus /var/backups/nexus
git clone https://github.com/maghsoodsaadatmerikation-sudo/nexus.git /opt/nexus
cd /opt/nexus
export NEXUS_API_TOKEN='REPLACE_WITH_A_LONG_RANDOM_SECRET'
docker compose -f deploy/oci/docker-compose.yml up -d --build
```

Do not put the real bearer token in `.env`, shell history, repository files, screenshots, CI logs, or release evidence.

## Stage D evidence procedure

Stage D is closed only after all of these are observed on the real durable host:

1. container reaches `healthy`;
2. HTTPS endpoint responds while direct public access to port 3000 remains unavailable;
3. missing and incorrect bearer tokens fail closed;
4. authenticated workspace creation succeeds;
5. workspace backup is exported with `scripts/workspace-backup.sh`;
6. service/container is destroyed and recreated without deleting `/var/lib/nexus`;
7. the workspace survives recreation;
8. a second destructive recovery test removes the workspace data only after a backup exists, then restores with `scripts/workspace-restore.sh`;
9. restored snapshot and audit history match the backup;
10. evidence records commit SHA, container image ID, storage mount, timestamps, redacted health/auth results, backup SHA-256, and recovery result.

## Constitutional boundary

Host health, persistence, TLS, authentication and recovery are operational claims only. They do not establish epistemic correctness and do not increase machine authority. `A_out <= A_in` remains unchanged.
