# .devcontainer/Dockerfile
FROM python:3.11-bookworm AS base

SHELL ["/bin/bash", "-lc"]

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    build-essential \
    libgmp10 \
    ca-certificates \
    xz-utils \
    zstd \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential pkg-config libssl-dev \
    opam m4 unzip rsync \
    libgmp-dev \
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
 && git clone https://github.com/AeneasVerif/aeneas /opt/aeneas \
 && cd /opt/aeneas \
 && eval "$(opam env --switch=5.3.0)" \
 && make setup-charon \
 && make

# Convenience PATHs (Aeneas bin is in ./bin; Charon make outputs bin/charon)
ENV PATH="/opt/aeneas/bin:/opt/aeneas/charon/bin:${PATH}"

# ---- DEV STAGE (this name must exist for devcontainers build.target = "dev") ----
FROM base AS dev

# Runtime deps for tools + building/running your worker
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    build-essential \
    pkg-config \
    libssl-dev \
    libgmp10 \
    ca-certificates \
    xz-utils \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Rust (for your worker / running charon cargo)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Lean (elan includes lake)
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf \
  | sh -s -- -y --default-toolchain leanprover/lean4:stable
ENV PATH="/root/.elan/bin:${PATH}"

# Copy the built Aeneas tree (we need backends/lean too) and binaries
COPY --from=dependencies /opt/aeneas /opt/aeneas
ENV PATH="/opt/aeneas/bin:/opt/aeneas/charon/bin:${PATH}"

WORKDIR /opt

# Symlink /app -> /workspaces/anneal so dev feels like prod paths.
RUN cat >/usr/local/bin/link-workspace.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
rm -rf /app
ln -s /workspaces/anneal /app
EOF
RUN chmod +x /usr/local/bin/link-workspace.sh

# Create/refresh the spec Lake project in /app/spec and delete template junk.
RUN cat >/usr/local/bin/init-spec.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/app}"
cd "$APP_DIR"

# Create Lake project if missing (package name must be 'spec', not a path)
if [ ! -d "spec" ]; then
  lake new spec
fi

# Overwrite Lean toolchain with the one Aeneas expects for its Lean backend
cp /opt/aeneas/backends/lean/lean-toolchain "$APP_DIR/spec/lean-toolchain"

# Minimal lakefile: library only; no Main executable; depend on Aeneas via path
cat >"$APP_DIR/spec/lakefile.toml" <<'TOML'
name = "spec"
version = "0.1.0"
defaultTargets = ["Spec"]

[[require]]
name = "aeneas"
path = "/opt/aeneas/backends/lean"

[[lean_lib]]
name = "Spec"
TOML

# Root module: setup.py will append `import Spec.<CrateModule>`
cat >"$APP_DIR/spec/Spec.lean" <<'LEAN'
-- Root module for the Spec library.
LEAN

# Delete template files we don't use
rm -rf "$APP_DIR/spec/.github" || true
rm -f "$APP_DIR/spec/README.md" || true
rm -f "$APP_DIR/spec/Main.lean" || true
rm -f "$APP_DIR/spec/Spec/Basic.lean" || true
EOF
RUN chmod +x /usr/local/bin/init-spec.sh

WORKDIR /app
CMD ["bash"]
