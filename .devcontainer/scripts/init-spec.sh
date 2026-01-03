#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/app}"
cd "$ROOT/spec"

# Ensure the toolchain is installed and use 'elan run' for maximum reliability
TOOLCHAIN="$(tr -d '\r' < lean-toolchain)"
elan install "$TOOLCHAIN"

elan run "$TOOLCHAIN" lake update
elan run "$TOOLCHAIN" lake exe cache get
elan run "$TOOLCHAIN" lake build
