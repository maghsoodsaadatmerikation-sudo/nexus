#!/bin/bash
set -euo pipefail

: "${RUST_IMAGE:?RUST_IMAGE environment variable is required}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f Cargo.lock ]; then
    echo "[BOOTSTRAP] Cargo.lock already exists. Skipping."
    exit 0
fi

echo "[BOOTSTRAP] Generating Cargo.lock using pinned image..."
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PROJECT_ROOT:/app" \
  -w /app \
  "$RUST_IMAGE" \
  cargo build --quiet

echo "[BOOTSTRAP] Cargo.lock generated successfully."