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

# Build dependencies
RUN apt-get update && apt-get install -y \
    curl git build-essential pkg-config libssl-dev \
    opam m4 unzip bubblewrap libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Charon (Aeneas dependency)
WORKDIR /opt
RUN git clone https://github.com/AeneasVerif/charon && \
    cd charon && \
    cargo build --release
ENV PATH="/opt/charon/target/release:${PATH}"

# Install Aeneas
RUN opam init -y --disable-sandboxing --compiler=4.14.1 && \
    opam install -y dune menhir ppx_deriving visitors easy_format zarith && \
    git clone https://github.com/AeneasVerif/aeneas && \
    cd aeneas && \
    eval $(opam env) && \
    make
ENV PATH="/opt/aeneas/bin:${PATH}"

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

# COPY --from=builder /app/target/release/my-app /usr/local/bin/my-app
# CMD ["my-app"]