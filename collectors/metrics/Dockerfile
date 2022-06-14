FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONUTF8=1 \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /usr/src/app

COPY . .
ENV PYTHONPATH=/usr/src/app

ENTRYPOINT ["/usr/src/app/bin/get_metrics_from_prom.py"]
