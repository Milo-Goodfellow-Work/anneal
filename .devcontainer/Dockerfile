# syntax=docker/dockerfile:1.6
FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV OPAMROOT=/root/.opam
ENV OPAMYES=1
ENV OPAMNONINTERACTIVE=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    build-essential \
    pkg-config \
    libgmp-dev \
    opam \
    m4 \
    unzip \
    xz-utils \
    zstd \
  && rm -rf /var/lib/apt/lists/*

# Rust
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup
ENV PATH=/root/.cargo/bin:${PATH}
RUN curl -sSf https://sh.rustup.rs | bash -s -- -y --profile minimal

# Elan (Lean + Lake)
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y
ENV PATH=/root/.elan/bin:${PATH}

# Python tooling (optional)
RUN pip install --no-cache-dir black flake8 mypy

# ---------- Aeneas + Charon ----------
RUN opam init -y --disable-sandboxing --bare --no-setup
RUN opam switch create aeneas ocaml-base-compiler.5.3.0

# OCaml deps (you already discovered you need these)
RUN opam exec --switch=aeneas -- opam install -y \
    dune \
    ppx_deriving \
    visitors \
    easy_logging \
    zarith \
    yojson \
    core_unix \
    odoc \
    unionfind \
    menhir \
    domainslib \
    ocamlgraph \
    progress

# Copy your vendored fork (no network dependency for it)
COPY spec/vendor/aeneas /opt/aeneas

# Build Aeneas + pinned Charon
RUN bash -euxo pipefail <<'BASH'
cd /opt/aeneas
opam exec --switch=aeneas -- make setup-charon

cd /opt/aeneas/charon
if [[ -f rust-toolchain.toml ]]; then
  TOOLCHAIN="$(awk -F'"' '/^[[:space:]]*channel[[:space:]]*=/ {print $2; exit}' rust-toolchain.toml | tr -d '\r')"
elif [[ -f rust-toolchain ]]; then
  TOOLCHAIN="$(tr -d '\r\n' < rust-toolchain)"
else
  echo "No rust-toolchain(.toml) found in /opt/aeneas/charon" >&2
  exit 1
fi

echo "Using Rust toolchain: ${TOOLCHAIN}"
rustup toolchain install "${TOOLCHAIN}"
rustup component add rustfmt --toolchain "${TOOLCHAIN}"

cd /opt/aeneas
opam exec --switch=aeneas -- make

ln -sf /opt/aeneas/bin/aeneas /usr/local/bin/aeneas
ln -sf /opt/aeneas/charon/bin/charon /usr/local/bin/charon
BASH


# ---------- Devcontainer helper scripts ----------
COPY .devcontainer/scripts/link-workspace.sh /usr/local/bin/link-workspace.sh
COPY .devcontainer/scripts/init-spec.sh /usr/local/bin/init-spec.sh
RUN sed -i 's/\r$//' /usr/local/bin/link-workspace.sh /usr/local/bin/init-spec.sh \
 && chmod +x /usr/local/bin/link-workspace.sh /usr/local/bin/init-spec.sh
