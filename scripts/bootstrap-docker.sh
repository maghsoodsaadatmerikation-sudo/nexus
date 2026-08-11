#!/usr/bin/env bash
set -euo pipefail

: "${RUST_IMAGE:?RUST_IMAGE environment variable is required}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! "$RUST_IMAGE" =~ ^rust@sha256:[0-9a-f]{64}$ ]]; then
    echo "[FATAL] Docker image is not digest-pinned."
    exit 1
fi

if [[ -f Cargo.lock ]]; then
    echo "[BOOTSTRAP] Cargo.lock already exists. Skipping."
    exit 0
fi

[[ -f Cargo.toml ]] || { echo "[FATAL] Cargo.toml missing."; exit 1; }

echo "[BOOTSTRAP] Generating Cargo.lock using pinned image..."
docker pull "$RUST_IMAGE"
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/home \
  -e CARGO_HOME=/tmp/cargo \
  -v "$PROJECT_ROOT:/app" \
  -w /app \
  "$RUST_IMAGE" \
  cargo generate-lockfile

[[ -s Cargo.lock ]] || { echo "[FATAL] Cargo.lock was not generated."; exit 1; }
echo "[BOOTSTRAP] Cargo.lock generated successfully."
