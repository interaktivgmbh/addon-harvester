# addon-harvester

Harvests add-on/package metadata from **PyPI** (any trove classifier) and **npm** (search
queries) into one normalised JSON snapshot (`index.json`, `schema_version` 3) with a
0–100 health score per add-on. Std-lib only, no framework dependency. PyPI is enumerated
via the public BigQuery dataset (the only non-deprecated bulk API); XML-RPC browse and
the Simple index remain as fallbacks.

The search terms live in `harvest.toml` — point them at any ecosystem
(`"Framework :: Django"`, `"Framework :: Zope"`, ...). The shipped default is the
**Plone profile**: `Framework :: Plone` plus npm queries for Volto/Aurora and
[Nick](https://github.com/plone/nick) add-ons (Nick hits are tagged with the `nick`
category), with Plone-specific enrichments (version compat, add-on categories,
backend/frontend pairing) that simply stay empty for other ecosystems.

## Docker (production, refresh every 4 h)

**1.** `.env` in the repo root:

```ini
BIGQUERY_PROJECT=my-gcp-project
GITHUB_TOKEN=ghp_...        # optional: GitHub stars/last-commit enrichment
```

**2.** GCP service-account key at `secrets/gcp-key.json` (one-time):

```sh
gcloud iam service-accounts create harvester --project=$PROJECT
gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:harvester@$PROJECT.iam.gserviceaccount.com" \
    --role=roles/bigquery.jobUser
gcloud iam service-accounts keys create secrets/gcp-key.json \
    --iam-account=harvester@$PROJECT.iam.gserviceaccount.com
```

**3.** Run:

```sh
docker compose up -d --build
docker compose logs -f harvester
```

The container harvests once at startup, then every 4 hours (`docker/crontab`), writing to
`./data/index.json`. Harvest flags live in `HARVEST_ARGS` in `docker-compose.yml`.
Without a key file the harvester falls back to the deprecated XML-RPC API.

## Local development

```sh
make install        # venv + package + dev extras (Python ≥ 3.14)
make test           # pytest — offline, all network mocked
make lint           # ruff
make harvest        # full run (ARGS="--limit 20" to override)
```

For BigQuery enumeration locally, log in once with `gcloud auth login` and set
`BIGQUERY_PROJECT` in `.env` — tokens are minted automatically per run.

As a library (no I/O, snapshot returned in memory):

```python
from addon_harvester import Harvester, HarvestOptions, write_snapshot

snapshot = Harvester(HarvestOptions(limit=20)).run()
write_snapshot(snapshot, "index.json")
```

## Configuration

| Where | What |
| --- | --- |
| `harvest.toml` | search terms: PyPI trove classifiers + npm search queries (`--classifier` overrides the classifiers, `--config` for another file) |
| `.env` | `BIGQUERY_PROJECT`, `GITHUB_TOKEN`/`GH_TOKEN`, optional `BIGQUERY_TOKEN` |
| `python main.py --help` | all CLI flags (sources, limit, workers, output, ...) |

Every CLI run writes its full log to `var/log/harvest-<timestamp>.log` (newest 20 kept);
`-v` only controls console verbosity.

## Architecture

```
src/addon_harvester/
├── harvester.py    orchestration → snapshot (no I/O)
├── sources/        pypi (BigQuery → XML-RPC → Simple), npm, github enricher, bigquery client
├── normalizers/    raw registry document → TAddon
├── healthscore/    health score (rubric: healthscore/config.py)
└── http.py         retrying JSON client with per-thread keep-alive · config.py · types.py
```

Each source implements `list_packages` / `fetch_package` / `fetch_downloads` /
`normalize`; `HarvestBase.harvest()` drives them identically. `main.py` is the CLI
wrapper, `Makefile` the task runner.

## Release

```sh
make build          # sdist + wheel into dist/
make publish        # upload to PyPI (needs credentials)
```
