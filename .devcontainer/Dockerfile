# syntax=docker/dockerfile:1.6

FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# System deps (bash is important because our scripts use /usr/bin/env bash)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    build-essential \
    pkg-config \
    libgmp-dev \
    ocaml \
    opam \
    m4 \
    unzip \
    xz-utils \
    zstd \
  && rm -rf /var/lib/apt/lists/*

# Rust (for Charon + your Rust project)
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup
ENV PATH=/root/.cargo/bin:${PATH}
RUN curl -sSf https://sh.rustup.rs | bash -s -- -y --profile minimal

# Elan (Lean + Lake)
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y
ENV PATH=/root/.elan/bin:${PATH}

# Python tooling (optional but handy)
RUN pip install --no-cache-dir black flake8 mypy

# ---------- Aeneas + Charon ----------
# OPAM init (keep it early for caching)
ENV OPAMROOT=/root/.opam
RUN opam init -y --disable-sandboxing --bare --no-setup
RUN opam switch create aeneas 5.3.0
RUN opam exec --switch=aeneas -- opam install -y \
    dune \
    ppx_deriving \
    visitors \
    easy_logging \
    zarith \
    yojson \
    core_unix \
    odoc

# Build Charon (Rust binary) and keep repo around (for charon-ml too)
RUN git clone --depth 1 https://github.com/AeneasVerif/charon /opt/charon \
  && cd /opt/charon \
  && rustup component add rustfmt \
  && make build-charon-rust \
  && ln -sf /opt/charon/bin/charon /usr/local/bin/charon

# Build Aeneas (OCaml toolchain)
RUN git clone --depth 1 https://github.com/AeneasVerif/aeneas /opt/aeneas \
  && cd /opt/aeneas/compiler \
  && ln -sf /opt/charon/charon-ml charon \
  && cd /opt/aeneas \
  && opam exec --switch=aeneas -- make

# Provide an `aeneas` command on PATH (Aeneas README runs via dune exec)
RUN cat >/usr/local/bin/aeneas <<'EOF' \
#!/usr/bin/env bash
set -euo pipefail
cd /opt/aeneas
exec opam exec --switch=aeneas -- dune exec -- src/main.exe -- "$@"
EOF
RUN sed -i 's/\r$//' /usr/local/bin/aeneas && chmod +x /usr/local/bin/aeneas

# ---------- Devcontainer helper scripts ----------
RUN cat >/usr/local/bin/link-workspace.sh <<'EOF' \
#!/usr/bin/env bash
set -euo pipefail
# postCreateCommand runs with CWD = the workspace folder.
WS="$(pwd)"
mkdir -p /app
rm -rf /app
ln -snf "$WS" /app
echo "Linked /app -> $WS"
EOF
RUN sed -i 's/\r$//' /usr/local/bin/link-workspace.sh && chmod +x /usr/local/bin/link-workspace.sh

RUN cat >/usr/local/bin/init-spec.sh <<'EOF' \
#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/app}"

if [ ! -d "$ROOT/spec" ]; then
  echo "Expected $ROOT/spec to exist (repo should contain spec/)."
  exit 1
fi

cd "$ROOT/spec"
# This will auto-download the Lean toolchain specified by lean-toolchain if needed.
lake build
EOF
RUN sed -i 's/\r$//' /usr/local/bin/init-spec.sh && chmod +x /usr/local/bin/init-spec.sh
