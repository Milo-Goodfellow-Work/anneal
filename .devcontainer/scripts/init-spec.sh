#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/app}"
cd "$ROOT/spec"

echo "[init-spec] normalizing .lake directory"

# Always put .lake on container FS (never bind-mounted)
CACHE_ROOT="/var/cache/lake/spec-lake"

mkdir -p "$CACHE_ROOT"

# Remove any existing .lake (dir or symlink)
if [ -e .lake ] || [ -L .lake ]; then
  rm -rf .lake
fi

# Recreate as symlink
ln -s "$CACHE_ROOT" .lake

# Create directories Lake / git expect
mkdir -p .lake/packages .lake/build

# Read toolchain (strip CR for Windows checkouts)
TOOLCHAIN="$(tr -d '\r' < lean-toolchain)"

# Ensure toolchain exists
elan install "$TOOLCHAIN"

# Force all lake/lean invocations to use this toolchain
export ELAN_TOOLCHAIN="$TOOLCHAIN"

echo "[init-spec] ELAN_TOOLCHAIN=$ELAN_TOOLCHAIN"
lake --version
lean --version

echo "[init-spec] lake update"
lake update -v

echo "[init-spec] lake exe cache get (this can take a while the first time)"
lake -v exe cache get

echo "[init-spec] lake build"
lake build -v

echo "[init-spec] done"
