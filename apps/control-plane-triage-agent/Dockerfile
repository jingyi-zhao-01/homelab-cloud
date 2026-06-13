FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

COPY pyproject.toml ./
COPY uv.lock ./
COPY src ./src

RUN set -eux; \
    for attempt in 1 2 3; do \
      uv sync --locked --no-dev && exit 0; \
      if [ "$attempt" -eq 3 ]; then \
        exit 1; \
      fi; \
      sleep $((attempt * 5)); \
    done

CMD ["uv", "run", "control-plane-triage-agent"]
