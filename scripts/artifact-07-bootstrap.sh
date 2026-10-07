#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'ARTIFACT 07 BOOTSTRAP: tracked sources must match the exact commit' >&2
  exit 1
fi

output="${1:-artifact-07-output}"
if [[ "$output" != /* ]]; then
  output="$ROOT/$output"
fi
if [[ -e "$output" ]]; then
  echo "ARTIFACT 07 BOOTSTRAP: output already exists: $output" >&2
  exit 1
fi
mkdir -p "$output"

cleanup_on_error() {
  status=$?
  if [[ $status -ne 0 ]]; then
    find "$output" -type f -delete
    rmdir "$output" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup_on_error EXIT

python3 scripts/verify-artifact-07.py
commit="${GITHUB_SHA:-$(git rev-parse HEAD)}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'ARTIFACT 07 BOOTSTRAP: exact 40-character commit required' >&2
  exit 1
}
test "$(git rev-parse HEAD)" = "$commit"

cargo test --manifest-path artifact-05/Cargo.toml --locked --test http_contract artifact_07_ -- --nocapture \
  >"$output/safety-tests.log" 2>&1
grep -F '6 passed' "$output/safety-tests.log" >/dev/null
cp artifact-07/controls.json "$output/controls.json"

python3 - "$output" "$commit" <<'PY'
import hashlib, json, pathlib, sys

out = pathlib.Path(sys.argv[1])
root = pathlib.Path.cwd()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = {
    "schema_version": 1,
    "artifact": "Artifact 07 — Public Exposure Safety Boundary",
    "status": "PASS",
    "verified_commit": sys.argv[2],
    "authority_claim": "NONE",
    "epistemic_claim": "VERIFICATION_ONLY",
    "production_mutation": "NONE",
    "sealed": False,
    "invariant": "A_out <= A_in",
    "bootstrap_verify_separation": True,
    "cargo_locks": {
        "Cargo.lock": digest(root / "Cargo.lock"),
        "artifact-05/Cargo.lock": digest(root / "artifact-05/Cargo.lock"),
    },
    "files": {
        name: digest(out / name) for name in ("safety-tests.log", "controls.json")
    },
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY

tar -C "$output" -czf "$output/artifact-07-evidence.tar.gz" \
  manifest.json safety-tests.log controls.json
python3 scripts/verify-artifact-07.py "$output/artifact-07-evidence.tar.gz"

trap - EXIT
echo 'ARTIFACT 07 BOOTSTRAP: PASS'
echo "Evidence: $output/artifact-07-evidence.tar.gz"
