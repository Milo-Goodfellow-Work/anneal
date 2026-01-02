#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/app}"

cd "$ROOT/spec"

# Make sure Lean toolchain is present, then fetch precompiled olean cache for deps (Mathlib, etc.)
lake update
lake exe cache get

# Now build *your* project; should be fast because deps come from cache
lake build
