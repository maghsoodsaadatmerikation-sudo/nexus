#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

inputs=(
  Cargo.toml
  Cargo.lock
  Dockerfile
  src
  artifact-05
  web
  scripts/source-tree-digest.sh
)

for input in "${inputs[@]}"; do
  test -e "$input" || {
    echo "missing source-tree input: $input" >&2
    exit 1
  }
done

find "${inputs[@]}" \
  -type f \
  ! -path '*/target/*' \
  -print0 \
  | LC_ALL=C sort -z \
  | xargs -0 sha256sum \
  | sha256sum \
  | awk '{print $1}'
