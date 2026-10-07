#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'ARTIFACT 06 BOOTSTRAP: tracked sources must match the exact commit' >&2
  exit 1
fi

output="${1:-artifact-06-output}"
if [[ "$output" != /* ]]; then
  output="$ROOT/$output"
fi
if [[ -e "$output" ]]; then
  echo "ARTIFACT 06 BOOTSTRAP: output already exists: $output" >&2
  exit 1
fi
mkdir -p "$output"

cleanup_on_error() {
  status=$?
  if [[ $status -ne 0 ]]; then
    rm -rf "$output"
  fi
  exit "$status"
}
trap cleanup_on_error EXIT

python3 scripts/verify-artifact-06.py

commit="${GITHUB_SHA:-$(git rev-parse HEAD)}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'ARTIFACT 06 BOOTSTRAP: exact 40-character commit required' >&2
  exit 1
}
test "$(git rev-parse HEAD)" = "$commit"

cargo test --locked --test constitutional_tests -- --nocapture \
  >"$output/core-tests.log" 2>&1
cargo test --manifest-path artifact-05/Cargo.toml --locked --test http_contract -- --nocapture \
  >"$output/gateway-tests.log" 2>&1
grep -F '20 passed' "$output/core-tests.log" >/dev/null
grep -F 'test result: ok' "$output/gateway-tests.log" >/dev/null

cp artifact-06/scenarios.json "$output/scenarios.json"

python3 - "$output" "$commit" <<'PY'
import hashlib, json, pathlib, sys

out = pathlib.Path(sys.argv[1])

def digest(name):
    return hashlib.sha256((out / name).read_bytes()).hexdigest()

root = pathlib.Path.cwd()
manifest = {
    "schema_version": 1,
    "artifact": "Artifact 06 — Synthetic Reality Lab",
    "status": "PASS",
    "verified_commit": sys.argv[2],
    "authority_claim": "NONE",
    "epistemic_claim": "VERIFICATION_ONLY",
    "production_mutation": "NONE",
    "sealed": False,
    "invariant": "A_out <= A_in",
    "bootstrap_verify_separation": True,
    "cargo_locks": {
        "Cargo.lock": hashlib.sha256((root / "Cargo.lock").read_bytes()).hexdigest(),
        "artifact-05/Cargo.lock": hashlib.sha256((root / "artifact-05/Cargo.lock").read_bytes()).hexdigest(),
    },
    "files": {name: digest(name) for name in ("core-tests.log", "gateway-tests.log", "scenarios.json")},
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY

tar -C "$output" -czf "$output/artifact-06-evidence.tar.gz" \
  manifest.json core-tests.log gateway-tests.log scenarios.json
python3 scripts/verify-artifact-06.py "$output/artifact-06-evidence.tar.gz"

trap - EXIT
echo "ARTIFACT 06 BOOTSTRAP: PASS"
echo "Evidence: $output/artifact-06-evidence.tar.gz"
