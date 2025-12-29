# .devcontainer/Dockerfile
FROM python:3.11-bookworm

SHELL ["/bin/bash", "-lc"]

# ---- base deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git xz-utils zstd \
    build-essential pkg-config libssl-dev \
  && rm -rf /var/lib/apt/lists/*

# ---- Rust (for Charon) ----
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# ---- OPAM + Aeneas build deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    opam m4 unzip rsync \
  && rm -rf /var/lib/apt/lists/*

# ---- Build Aeneas (includes Charon setup) ----
WORKDIR /opt
RUN git clone https://github.com/AeneasVerif/aeneas.git /opt/aeneas
WORKDIR /opt/aeneas
RUN opam init -y --disable-sandboxing \
 && opam switch create 5.3.0 -y \
 && eval "$(opam env)" \
 && opam install -y \
    ppx_deriving visitors easy_logging zarith yojson core_unix odoc \
    ocamlgraph menhir ocamlformat unionFind progress domainslib \
 && make setup-charon \
 && make

ENV PATH="/opt/aeneas/bin:/opt/aeneas/charon/bin:${PATH}"

# ---- elan (Lean + Lake) ----
RUN curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
  | sh -s -- -y
ENV PATH="/root/.elan/bin:${PATH}"

# ---- init script used by devcontainer.json postCreateCommand ----
RUN cat >/usr/local/bin/init-spec.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/app}"
SPEC_DIR="$APP_DIR/spec"

mkdir -p "$APP_DIR"

# Create Lake project if missing
if [ ! -d "$SPEC_DIR" ]; then
  lake new "$SPEC_DIR" spec
fi

# Aeneas Lean backend: overwrite lean-toolchain with the one in backends/lean
cp /opt/aeneas/backends/lean/lean-toolchain "$SPEC_DIR/lean-toolchain"

# Minimal lakefile: library only (no Main executable), plus aeneas path dependency
cat >"$SPEC_DIR/lakefile.toml" <<'TOML'
name = "spec"
version = "0.1.0"
defaultTargets = ["Spec"]

[[require]]
name = "aeneas"
path = "/opt/aeneas/backends/lean"

[[lean_lib]]
name = "Spec"
TOML

# Root module: setup.py will append imports like `import Spec.TestProject`
cat >"$SPEC_DIR/Spec.lean" <<'LEAN'
-- Root module for the Spec library.
LEAN

# Delete template files we don't use
rm -rf "$SPEC_DIR/.github" || true
rm -f "$SPEC_DIR/README.md" "$SPEC_DIR/Main.lean" "$SPEC_DIR/Spec/Basic.lean" || true
EOF

RUN chmod +x /usr/local/bin/init-spec.sh

WORKDIR /app
CMD ["bash"]
