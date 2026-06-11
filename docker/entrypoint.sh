#!/bin/sh
# Container entrypoint: persist the environment for cron, harvest once, then run cron.
set -e

# cron jobs run with a bare environment — write the harvester-relevant variables to
# /app/.env, which main.py loads itself and harvest.sh reads for its own settings
printenv | grep -E '^(BIGQUERY_|GOOGLE_|GITHUB_TOKEN=|GH_TOKEN=|HARVEST_)' > /app/.env || true

echo "entrypoint: initial harvest (then every 4 hours via cron)"
/app/docker/harvest.sh || echo "entrypoint: initial harvest failed — cron retries on schedule"

exec cron -f
