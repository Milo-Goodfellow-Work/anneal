#!/usr/bin/env bash
set -euo pipefail

# Dev Containers runs postCreateCommand with CWD = workspace folder.
WS="$(pwd)"

rm -rf /app
ln -snf "$WS" /app
echo "Linked /app -> $WS"
