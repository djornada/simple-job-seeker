# Web UI image. Pure stdlib, so there's nothing to install. compose.yaml at
# the repo root runs it with host networking and ./server mounted over /app,
# so state.db, config.toml and .env stay on the host.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=1000:1000 . .
USER 1000:1000

CMD ["python3", "-m", "webapp"]
