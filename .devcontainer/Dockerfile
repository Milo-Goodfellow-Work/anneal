# syntax=docker/dockerfile:1.6
FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV OPAMROOT=/root/.opam
ENV OPAMYES=1
ENV OPAMNONINTERACTIVE=1

# System deps (bash is important because our scripts use /usr/bin/env bash)
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

# Elan (Lean + Lake)
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y
ENV PATH=/root/.elan/bin:${PATH}

# Python tooling (optional but handy)
RUN pip install --no-cache-dir black flake8 mypy

# ---------- Pre-bake Mathlib Cache ----------
# Copy spec and download cache so it's part of the image.
# This avoids slow downloads on bind-mounts during devcontainer startup.
COPY spec /opt/spec
RUN cd /opt/spec \
  && lake exe cache get \
  && lake build -v