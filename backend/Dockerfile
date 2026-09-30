#
# Multi-stage build
#

# -- Stage 1 - prepare

# Default to public Docker Hub image, can be overridden with --build-arg to refer to a custom image registry (such as Harbor)
ARG PYTHON_IMAGE=python:3.14-slim

FROM ${PYTHON_IMAGE} AS builder
LABEL "maintainer"="ICTU"

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    make \
    git \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for pyright)
# Download to a file with retries: a piped `curl | bash` hides a failed download,
# so the build fails later on a misleading "Unable to locate package nodejs".
RUN curl -fsSL --retry 5 --retry-all-errors --retry-delay 5 \
        -o /tmp/nodesource_setup.sh https://deb.nodesource.com/setup_lts.x \
    && bash /tmp/nodesource_setup.sh \
    && rm /tmp/nodesource_setup.sh \
    && apt-get install -y nodejs

# Copy uv binary from the official image (cached locally by Docker after first pull)
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

# Ensure that all uv commands compile bytecode
ENV UV_COMPILE_BYTECODE=1

# Always use the latest pyright version
ENV PYRIGHT_PYTHON_FORCE_VERSION="latest"

# Install pyright globally
RUN npm install -g pyright

# Install packages
WORKDIR /backend
COPY ./pyproject.toml ./uv.lock /backend/

# Do not use venv
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
# Increase HTTP timeout for slow network connections
ENV UV_HTTP_TIMEOUT=300
RUN uv sync --frozen --no-install-project --no-dev

# -- Stage 2 - runtime (final image with build artifacts and without source code)

FROM ${PYTHON_IMAGE}

# Pass IMAGE_TAG (injected from build environment/pipeline). Served as the release
# version (`info.version`, `API-Version`), so the local default is valid semver.
ARG IMAGE_TAG=0.0.0-dev
ENV IMAGE_TAG=${IMAGE_TAG}

WORKDIR /backend

# Apply security patches for OS-level packages. No libpq: psycopg[binary] bundles
# its own, and asyncpg does not use it.
# Note: curl is NOT installed here — K8s probes use httpGet; docker-compose healthcheck uses python urllib
RUN apt-get update && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Remove pip — not needed at runtime, reduces CVE surface
RUN rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

# Copy application files
COPY ./alembic.ini /backend/alembic.ini
COPY ./alembic /backend/alembic
COPY ./app /backend/app

RUN groupadd -r app && useradd -r -g app app
USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --no-server-header"]
