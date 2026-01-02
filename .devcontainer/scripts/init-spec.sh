#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/app}"
cd "$ROOT/spec"

# Force lake to use the project's pinned toolchain (fixes the mismatch warning)
export ELAN_TOOLCHAIN="$(tr -d '\r' < lean-toolchain)"

lake update
lake exe cache get
lake build
