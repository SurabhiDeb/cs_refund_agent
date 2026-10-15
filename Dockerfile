# Multi stage. The builder has curl, uv, and a compiler. The image that
# ships has none of them, because every tool in a running container is a
# tool an attacker gets for free.

FROM python:3.13-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Manifests only, so this layer is cached until a dependency actually
# changes. --frozen means the lockfile decides, never the resolver.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


FROM python:3.13-slim AS runtime

# A fixed uid, so the files it owns mean the same thing on every host.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser migrations/ /app/migrations/
COPY --chown=appuser:appuser alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Nothing at runtime installs anything. pip ships vendored copies of
# urllib3, msgpack and setuptools, and their CVEs become ours for no
# benefit. Removing the dist-info too is what makes them actually gone,
# since that is what a scanner reads.
RUN rm -rf /usr/local/lib/python3.13/site-packages/pip \
           /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
           /usr/local/lib/python3.13/site-packages/setuptools \
           /usr/local/lib/python3.13/site-packages/setuptools-*.dist-info \
           /usr/local/lib/python3.13/site-packages/pkg_resources \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13

# Everything from here runs unprivileged. Nothing below needs root, and if
# something ever does, that is the bug.
USER appuser

EXPOSE 8000

# No curl in the image, so the check uses the interpreter that is already here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

CMD ["granian", "--interface", "asgi", "ops_agent.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
