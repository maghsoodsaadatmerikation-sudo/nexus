# Stage D self-hosted candidate (Docker + Tailscale Funnel)

Status: **deployment candidate only**. This file is not Stage D evidence, a PASS, or a Seal. A real host and an independently stored evidence pack are still required. The operator must verify that the chosen machine has durable storage, remains available during the exercise, and has a successful NEXUS Verification run for the exact 40-character commit deployed.

## Host setup

Use a personally controlled Linux, macOS, or Windows/WSL2 machine with Docker and Tailscale installed. Tailscale Funnel is public: keep the bearer token private and use a dedicated machine or account. Do not use an ephemeral development workspace.

1. Check out the exact verified commit, recording its full SHA. The final commit must include this deployment configuration and have a successful NEXUS Verification run.
2. Set a strong private `NEXUS_API_TOKEN` in the operator's environment (not in Git, command arguments, URLs, screenshots, or the evidence pack). Run `docker compose -f deploy/stage-d-self-hosted.compose.yaml up -d --build` from the repository root.
3. Inspect `docker compose -f deploy/stage-d-self-hosted.compose.yaml ps` and `curl --fail http://127.0.0.1:3000/`. The Compose volume is mounted at `/data` inside the container. Docker publishes port 3000 only on host loopback.
4. On the same host, enable Tailscale Funnel for the local port: `tailscale funnel --bg --https=443 3000`. Record the HTTPS URL returned by `tailscale funnel status`. Do not expose port 3000 through the router or firewall.

## Evidence boundary

Run `scripts/stage-d-evidence.sh` from an operator machine with the evidence directory stored independently of the host. Set `NEXUS_BASE_URL` to the Funnel HTTPS origin and supply the private token through the operator environment. Run `preflight`; create an isolated witness workspace; then run `capture` with `NEXUS_DEPLOYED_COMMIT` set to the exact deployed SHA.

For the replacement exercise, recreate the container **without removing the named volume** and corroborate the event identifier, UTC time, and exact running SHA before `record-replacement` and `verify-survival`. A restart alone is not a replacement. Keep the witness workspace and its volume separate from any valuable data.

The later destructive absence and restore exercise must be performed separately on the isolated witness state, after an independent backup and an explicit operator review of the exact data path. Never use `docker compose down -v` on a volume containing other data. Run `verify-absence`, `restore-verify`, and `scripts/v1.1-release-readiness.sh` only after the required lifecycle evidence exists. Independently confirm the referenced NEXUS Verification run. Do not mark Stage D complete or seal v1.1.0 from configuration alone.

Limits: this approach depends on the host staying powered and connected; neither Docker nor Funnel proves production availability. The actual mounted volume, container replacement, HTTPS behavior, and recovery must be observed. `A_out <= A_in`; evidence does not grant authority.
