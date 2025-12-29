FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-lc"]

# --- OS deps ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    make \
    build-essential \
    pkg-config \
    libssl-dev \
    m4 \
    opam \
    zlib1g-dev \
    libgmp-dev \
    xz-utils \
    unzip \
  && rm -rf /var/lib/apt/lists/*

# --- Rust (for Charon) ---
RUN curl -sSf https://sh.rustup.rs | bash -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:/root/.elan/bin:/opt/aeneas/bin:/opt/aeneas/charon/bin:${PATH}"

# --- Lean tooling (elan provides lean + lake) ---
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y

# --- OCaml / OPAM deps (per Aeneas README) ---
ENV OPAMYES=1
ENV OPAMNONINTERACTIVE=1
RUN opam init -y --disable-sandboxing \
 && opam switch create 5.3.0 \
 && eval "$(opam env)" \
 && opam install -y \
      dune \
      ppx_deriving \
      visitors \
      easy_logging \
      zarith \
      yojson \
      core_unix \
      odoc \
      ocamlgraph \
      menhir \
      ocamlformat \
      unionFind \
      progress \
      domainslib \
 && opam clean -a -y

# --- Build Aeneas + pinned Charon ---
RUN git clone https://github.com/AeneasVerif/aeneas.git /opt/aeneas \
 && cd /opt/aeneas \
 && eval "$(opam env)" \
 && make setup-charon \
 && make

# --- Helper: initialize/build the spec Lake project inside your workspace ---
RUN cat > /usr/local/bin/init-spec.sh <<'EOF'
#!/usr/bin/env bash
set -e

ROOT="${1:-/app}"
mkdir -p "$ROOT"
cd "$ROOT"

# Ensure lean toolchain matches Aeneas Lean backend
if [ -d "/opt/aeneas/backends/lean" ]; then
  mkdir -p spec
  cp -f /opt/aeneas/backends/lean/lean-toolchain spec/lean-toolchain
fi

# Ensure Lake dependency on Aeneas Lean backend (path dep = matches installed Aeneas)
if [ -f "spec/lakefile.toml" ] && ! grep -q 'name *= *"aeneas"' spec/lakefile.toml; then
  cat >> spec/lakefile.toml <<'TOML'

[[require]]
name = "aeneas"
path = "/opt/aeneas/backends/lean"
TOML
fi

# Build (and fetch deps) so VSCode/Lean is “warm”
if [ -f "spec/lakefile.toml" ]; then
  (cd spec && lake update && lake build)
fi
EOF

RUN chmod +x /usr/local/bin/init-spec.sh

WORKDIR /app
CMD ["bash"]
