FROM python:3.11-bookworm AS base

# Runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libgmp10 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies

RUN apt-get update && apt-get install -y \
    curl git build-essential pkg-config libssl-dev \
    opam m4 unzip bubblewrap libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# Rust (needed for make setup-charon)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt

# Opam + OCaml deps, then Aeneas + pinned Charon
ENV OPAMYES=1 OPAMNONINTERACTIVE=1

RUN opam init -y --disable-sandboxing \
 && opam switch create 5.3.0 -y \
 && eval "$(opam env --switch=5.3.0)" \
 && opam install -y \
      dune ppx_deriving visitors easy_logging zarith yojson core_unix odoc \
      unionFind ocamlgraph menhir ocamlformat progress domainslib \
 && git clone https://github.com/AeneasVerif/aeneas \
 && cd aeneas \
 && eval "$(opam env --switch=5.3.0)" \
 && make setup-charon \
 && make

# Convenience PATHs (Aeneas bin is in ./bin; Charon make outputs bin/charon)
ENV PATH="/opt/aeneas/bin:/opt/aeneas/charon/bin:${PATH}"

FROM dependencies AS dev

RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain leanprover/lean4:stable
ENV PATH="/root/.elan/bin:${PATH}"

RUN pip install --no-cache-dir black flake8 mypy

# In devcontainers, VS Code often forces the repo to /workspaces/<repo>.
# This script makes /app point at that repo so paths match prod (/app/...) for tooling.
RUN printf '%s\n' \
'#!/bin/sh' \
'set -eu' \
'' \
'WS="/workspaces/anneal"' \
'' \
'if [ -d "$WS" ]; then' \
'  if [ -L /app ]; then' \
'    echo "/app is already a symlink; leaving it."' \
'    exit 0' \
'  fi' \
'  echo "Linking /app -> $WS (devcontainer workspace)..."' \
'  rm -rf /app' \
'  ln -s "$WS" /app' \
'  exit 0' \
'fi' \
'' \
'echo "No $WS found; leaving /app as a normal directory (prod-style)."' \
> /usr/local/bin/link-workspace.sh \
 && chmod +x /usr/local/bin/link-workspace.sh

# Create a single spec project under /app/spec (no mathlib).
# Uses Aeneas's Lean backend lean-toolchain for compatibility.
RUN printf '%s\n' \
'#!/bin/sh' \
'set -eu' \
'' \
'ROOT="${1:-/app}"' \
'PKG="spec"' \
'SPEC="${ROOT}/${PKG}"' \
'' \
'mkdir -p "${ROOT}"' \
'' \
'if [ -d "${SPEC}" ]; then' \
'  echo "spec already exists at ${SPEC}"' \
'  exit 0' \
'fi' \
'' \
'echo "Creating spec Lake project at ${SPEC}"' \
'cd "${ROOT}"' \
'lake new "${PKG}"' \
'' \
'# Aeneas recommends using its Lean backend''s lean-toolchain for compatibility.' \
'cp /opt/aeneas/backends/lean/lean-toolchain "${SPEC}/lean-toolchain"' \
'' \
'# Minimal lakefile: depend on Aeneas Lean backend, no mathlib.' \
'cat > "${SPEC}/lakefile.toml" <<'\''TOML'\''' \
'name = "spec"' \
'version = "0.1.0"' \
'defaultTargets = ["Spec"]' \
'' \
'[[lean_lib]]' \
'name = "Spec"' \
'' \
'[[require]]' \
'name = "aeneas"' \
'path = "/opt/aeneas/backends/lean"' \
'TOML' \
'' \
'echo "Done. (No lake update/build performed.)"' \
> /usr/local/bin/init-spec.sh \
 && chmod +x /usr/local/bin/init-spec.sh

# Optional convenience: default working directory
WORKDIR /app

FROM dev AS builder
WORKDIR /app
COPY . .

RUN cargo build --release

FROM base AS prod
WORKDIR /app

# Install runtime dependencies for verification tools
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

# Install Rust and Lean
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain leanprover/lean4:stable
ENV PATH="/root/.elan/bin:${PATH}"

# Copy Aeneas and Charon
COPY --from=dependencies /opt/aeneas/bin/aeneas /usr/local/bin/aeneas
COPY --from=dependencies /opt/aeneas/charon/bin/charon /usr/local/bin/charon
COPY --from=dependencies /opt/aeneas/charon/bin/charon-driver /usr/local/bin/charon-driver

# Copy the Aeneas Lean backend so /opt/aeneas/backends/lean exists in prod too
COPY --from=dependencies /opt/aeneas/backends/lean /opt/aeneas/backends/lean

# Copy the spec init script into prod so your queue worker can call it too.
COPY --from=dev /usr/local/bin/init-spec.sh /usr/local/bin/init-spec.sh
RUN chmod +x /usr/local/bin/init-spec.sh
