FROM python:3.9-slim as builder

WORKDIR /usr/src/app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt > requirements.txt

FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONUTF8=1 \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install -r requirements.txt
COPY . .
