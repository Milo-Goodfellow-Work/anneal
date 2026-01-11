# syntax=docker/dockerfile:1.6
# Use the same base image logic as devcontainer to ensure all tools (Lean, Aeneas, Rust) are present
# We can repurpose the steps or just copy the file. 
# For simplicity/robustness, we'll repeat the base setup or assume we can build from the devcontainer context.
# Let's assume this Dockerfile acts as the production build, using the same base.

FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV OPAMROOT=/root/.opam
ENV OPAMYES=1
ENV OPAMNONINTERACTIVE=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash ca-certificates curl git build-essential pkg-config libgmp-dev opam m4 unzip xz-utils zstd \
  && rm -rf /var/lib/apt/lists/*

# Rust
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup
ENV PATH=/root/.cargo/bin:${PATH}
RUN curl -sSf https://sh.rustup.rs | bash -s -- -y --profile minimal

# Elan (Lean + Lake)
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y
ENV PATH=/root/.elan/bin:${PATH}

# OCaml/Aeneas Setup
RUN opam init -y --disable-sandboxing --bare --no-setup && \
    opam switch create aeneas ocaml-base-compiler.5.3.0

RUN opam exec --switch=aeneas -- opam install -y \
  dune ppx_deriving visitors easy_logging zarith yojson core_unix odoc unionfind menhir domainslib ocamlgraph progress

# Copy Vendors (Aeneas)
COPY vendors/aeneas /opt/aeneas
RUN find /opt/aeneas -type f -exec sed -i 's/\r$//' {} +

# Build Aeneas & Charon
RUN cd /opt/aeneas \
  && PINNED=$(tail -1 charon-pin | tr -d '\r') \
  && git clone https://github.com/AeneasVerif/charon \
  && cd charon \
  && git checkout $PINNED \
  && . /root/.cargo/env \
  && TOOLCHAIN=$(grep -h 'channel =' rust-toolchain rust-toolchain.toml 2>/dev/null | head -n 1 | cut -d '"' -f 2) \
  && rustup toolchain install $TOOLCHAIN \
  && rustup component add rustfmt --toolchain $TOOLCHAIN \
  && cd /opt/aeneas \
  && opam exec --switch=aeneas -- make setup-charon \
  && cd charon && opam exec --switch=aeneas -- opam install . -y && cd .. \
  && opam exec --switch=aeneas -- make build \
  && ln -sf /opt/aeneas/bin/aeneas /usr/local/bin/aeneas \
  && ln -sf /opt/aeneas/charon/bin/charon /usr/local/bin/charon

# Setup Application
WORKDIR /app

# Copy dependency requirements
# (We manually install specific ones for now as we don't have a requirements.txt)
RUN pip install --no-cache-dir openai flask requests gunicorn

# Copy Source Code
COPY main.py setup.py worker.py secrets.toml ./
# Copy Spec template
COPY spec /app/spec

# Pre-bake Mathlib cache for the spec template
RUN cd /app/spec \
  && sed -i 's|path = "../../vendors/aeneas"|path = "/opt/aeneas"|' lakefile.toml \
  && lake exe cache get \
  && lake build -v

# Secrets Handling:
# For this prototype, we copy secrets.toml directly into the image.
# NOTE: Ensure secrets.toml has your actual key before building!
COPY secrets.toml ./


ENV PORT=8080
# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "worker:app"]
