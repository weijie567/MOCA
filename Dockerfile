FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=5 \
        -o Acquire::http::Timeout=30 \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_RETRIES=5

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv

WORKDIR /app

ARG UV_DEFAULT_INDEX=https://pypi.org/simple
ENV UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_LINK_MODE=copy

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY rules ./rules
COPY alembic.ini ./
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    chmod +x /app/docker-entrypoint.sh \
    && for attempt in 1 2 3; do \
        uv pip install --system -e . && break; \
        if [ "$attempt" = "3" ]; then exit 1; fi; \
        sleep 5; \
    done

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
