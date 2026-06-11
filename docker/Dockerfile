# Periodic harvester container: runs one harvest at startup, then every 4 hours via cron
# (schedule in docker/crontab). Build from the repo root:
#
#     docker build -f docker/Dockerfile -t addon-harvester .
#
# google-auth/requests are container-only extras for minting BigQuery access tokens from a
# service-account key (docker/print_token.py) — the harvester package itself stays std-lib only.
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE main.py harvest.toml ./
COPY src ./src
COPY docker ./docker

RUN pip install --no-cache-dir . google-auth requests \
    && chmod +x docker/entrypoint.sh docker/harvest.sh \
    && cp docker/crontab /etc/cron.d/harvester \
    && chmod 0644 /etc/cron.d/harvester

# snapshot output (mount this); run logs land in /app/var/log inside the container
VOLUME /data

ENTRYPOINT ["/app/docker/entrypoint.sh"]
