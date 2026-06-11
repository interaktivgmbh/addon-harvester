#!/bin/sh
# One harvest run. Called by the entrypoint (with full env) and by cron (bare env —
# main.py reloads /app/.env itself, only the shell-level settings are re-read here).
set -e
cd /app

if [ -f .env ]; then
    [ -n "$HARVEST_ARGS" ] || HARVEST_ARGS=$(sed -n 's/^HARVEST_ARGS=//p' .env)
    [ -n "$HARVEST_OUTPUT" ] || HARVEST_OUTPUT=$(sed -n 's/^HARVEST_OUTPUT=//p' .env)
fi

# mint a fresh BigQuery access token from a mounted service-account key (tokens expire
# hourly, so this happens per run); without a key main.py falls back to XML-RPC browse
KEY_FILE="${GOOGLE_APPLICATION_CREDENTIALS:-/secrets/gcp-key.json}"
if [ -f "$KEY_FILE" ]; then
    BIGQUERY_TOKEN=$(python /app/docker/print_token.py "$KEY_FILE")
    export BIGQUERY_TOKEN
fi

exec python main.py --output "${HARVEST_OUTPUT:-/data/index.json}" ${HARVEST_ARGS:--v}
