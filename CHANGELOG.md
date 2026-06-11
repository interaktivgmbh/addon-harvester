# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-11

First public release.

### Added

- Harvest pipeline: enumerate → concurrent fetch → normalise onto a single add-on
  schema (`schema_version` 3), returned in memory as a snapshot or written atomically
  as JSON. Std-lib only — no framework dependency, embeddable anywhere.
- **PyPI source** for any trove classifier. Enumeration via the public BigQuery dataset
  `bigquery-public-data.pypi.distribution_metadata` (PyPI's supported bulk API; needs
  `BIGQUERY_PROJECT` plus an OAuth token from the env or `gcloud auth
  print-access-token`), falling back to the deprecated XML-RPC `browse` and, as a last
  resort, the Simple index with local classifier filtering.
- **npm source** for configurable registry search queries, keeping genuine Volto/Aurora
  add-ons via keyword/peer-dependency heuristics; downloads, dependents and the
  insecure flag ride along in the search response.
- **Configurable search terms** in `harvest.toml` (`[pypi] classifiers`,
  `[npm] queries`) — the shipped default is the Plone/Volto profile; any ecosystem
  classifier works (`--classifier` and `--config` override per run).
- **GitHub enrichment** (`--with-github`): stars, watchers, open issues and last commit
  via one batched GraphQL query per 50 repos.
- **Health score** (0–100) per add-on from release recency, documentation and metadata
  quality, with a GitHub-activity bonus when enrichment ran.
- **Download stats** (`--with-downloads`): day/week/month counts from pypistats.org
  (npm counts are free with the search).
- HTTP client with retries, per-thread keep-alive connections, redirect handling and
  per-run timing stats (per-source durations logged plus an end-of-run summary).
- CLI (`main.py`) with `.env` loading and per-run log files under
  `var/log/harvest-<timestamp>.log` (newest 20 kept).
- **Docker setup** (`docker-compose.yml`): harvests once at startup, then every 4 hours
  via cron; snapshot to the `/data` volume, BigQuery auth via a mounted GCP
  service-account key.
- GitHub Actions CI: ruff lint and the pytest suite (95% coverage, fully offline).

[1.0.0]: https://github.com/interaktivgmbh/addon-harvester/releases/tag/v1.0.0
