FROM python:3.10-slim as builder

WORKDIR /usr/src/app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt > requirements.txt

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONUTF8=1 \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on

RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    libc6-dev \
    libffi-dev \
    gcc \
  ; \
  rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install -r requirements.txt --ignore-installed --no-deps
COPY . .
ENV PYTHONPATH=/usr/src/app

ENTRYPOINT ["/usr/src/app/bin/get_metrics_from_prom.py"]
