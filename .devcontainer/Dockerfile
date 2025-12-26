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
COPY --from=dependencies /opt/charon/target/release/charon /usr/local/bin/charon
COPY --from=dependencies /opt/charon/target/release/charon-driver /usr/local/bin/charon-driver