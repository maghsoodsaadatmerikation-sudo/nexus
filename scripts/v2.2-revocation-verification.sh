#!/usr/bin/env bash
set -euo pipefail

required=(
  docs/V2.2-REVOCATION-REPLAY.md
  src/capability.rs
  scripts/run_gates.sh
  scripts/verify-docker.sh
)
for f in "${required[@]}"; do test -f "$f"; done

grep -Fq 'REVOCATION_SCHEMA_VERSION' src/capability.rs
grep -Fq 'RevocationSnapshot' src/capability.rs
grep -Fq 'RevocationReplayError' src/capability.rs
grep -Fq 'revocation_replay_reconstructs_state' src/capability.rs
grep -Fq 'broken_revocation_sequence_fails_closed' src/capability.rs
grep -Fq 'empty_revocation_provenance_fails_closed' src/capability.rs
grep -Fq 'No real verification -> no PASS -> no seal.' docs/V2.2-REVOCATION-REPLAY.md

./scripts/run_gates.sh

echo "NEXUS V2.2 REVOCATION REPLAY CHECK: PASS"
