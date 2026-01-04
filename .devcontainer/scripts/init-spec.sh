#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/app}"
cd "$ROOT/spec"

echo "[init-spec] normalizing .lake directory"

CACHE_ROOT="/var/cache/lake/spec-lake"
mkdir -p "$CACHE_ROOT"

# Remove any existing .lake (dir or symlink), then re-link
rm -rf .lake
ln -snf "$CACHE_ROOT" .lake

# Ensure Lake has somewhere to put things immediately
mkdir -p .lake/packages .lake/build

TOOLCHAIN="$(tr -d '\r' < lean-toolchain)"

elan install "$TOOLCHAIN"

echo "[init-spec] using toolchain: $TOOLCHAIN"
echo "[init-spec] lake update"
elan run "$TOOLCHAIN" lake update -v

echo "[init-spec] lake exe cache get (first time can be big/slow)"
elan run "$TOOLCHAIN" lake -v exe cache get

echo "[init-spec] lake build"
elan run "$TOOLCHAIN" lake build -v

echo "[init-spec] done"
