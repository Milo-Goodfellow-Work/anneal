#!/usr/bin/env bash
set -euo pipefail

WS="$(pwd)"

rm -rf /app
ln -snf "$WS" /app
echo "Linked /app -> $WS"
