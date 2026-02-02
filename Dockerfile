# syntax=docker/dockerfile:1.6
# Anneal Unified Dockerfile (Dev + Prod)

FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git build-essential pkg-config \
    libgmp-dev xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# Elan (Lean + Lake)
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y
ENV PATH=/root/.elan/bin:${PATH}

# Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 24: Copy spec and pre-build Mathlib cache
COPY spec/ ./spec/
RUN cd /app/spec && lake exe cache get && lake build

# 28: Copy application source code
# We copy files/dirs selectively to avoid overwriting the built ./spec folder
COPY main.py helpers.py requirements.txt ./
COPY stages/ ./stages/
COPY trigger_api/ ./trigger_api/

# Create working directory for generated code
RUN mkdir -p /app/generated

# Default to running the application (for Cloud Run Jobs)
CMD ["python", "main.py"]
