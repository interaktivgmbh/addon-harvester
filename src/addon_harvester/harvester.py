import time
from collections import Counter
from datetime import datetime, timezone
from typing import List, Tuple

from . import logger
from .config import SCHEMA_VERSION
from .healthscore.healthscore import HealthScore
from .options import HarvestOptions
from .sources.base import HarvestBase
from .sources.github import GitHubEnricher
from .sources.npm import NpmSource
from .sources.pypi import PyPISource
from .types import TAddon, TSnapshot

SOURCE_NAMES = ('pypi', 'npm')


class Harvester:
    """Orchestrates a harvest run: build sources, collect addons, enrich, return snapshot.

    Unlike a CLI driver this neither parses arguments nor writes files — :meth:`run` returns
    the snapshot in memory so the harvester can be embedded (e.g. in a FastAPI service).
    """

    def __init__(self, options: HarvestOptions) -> None:
        self.options = options

    def run(self) -> TSnapshot:
        sources = self._validated_sources()

        addons: List[TAddon] = []
        timings: List[Tuple[str, float]] = []
        for name in sources:
            started = time.monotonic()
            addons.extend(self.build_source(name).harvest(
                limit=self.options.limit,
                with_downloads=self.options.with_downloads,
                workers=self.options.workers,
            ))
            self._record_timing(timings, name, started)

        github_issues: List[str] = []
        if self.options.with_github:
            started = time.monotonic()
            github_issues = self._enrich_github(addons)
            self._record_timing(timings, 'github', started)

        scored = self._enrich_health(addons)

        addons.sort(key=lambda addon: (addon['source'], addon['name'].lower()))

        self._log_summary(sources, addons, scored, github_issues, timings)

        return self._build_snapshot(addons, sources)

    @staticmethod
    def _record_timing(timings: List[Tuple[str, float]], name: str, started: float) -> None:
        elapsed = time.monotonic() - started
        timings.append((name, elapsed))
        logger.info('%s: finished in %.1fs', name, elapsed)

    def _validated_sources(self) -> List[str]:
        sources = [s.strip() for s in self.options.sources if s and s.strip()]
        unknown = [s for s in sources if s not in SOURCE_NAMES]

        if unknown:
            raise ValueError('unknown source(s) %s — available: %s' % (unknown, ', '.join(SOURCE_NAMES)))

        return sources

    def build_source(self, name: str) -> HarvestBase:
        if name == 'pypi':
            return PyPISource(self.options.timeout, self.options.classifiers)

        return NpmSource(self.options.timeout, self.options.npm_queries)

    def _enrich_github(self, addons: List[TAddon]) -> List[str]:
        """Enrich in place; return any repos GitHub could not resolve (for the run summary)."""
        auth_token = GitHubEnricher.token_from_env()

        if not auth_token:
            logger.warning('with_github requested but no GITHUB_TOKEN/GH_TOKEN set — skipping enrichment')
            return []

        enricher = GitHubEnricher(auth_token, self.options.timeout)
        enriched = enricher.enrich(addons)
        logger.info('github: enriched %d/%d addons', enriched, len(addons))

        return enricher.unresolved

    @staticmethod
    def _enrich_health(addons: List[TAddon]) -> int:
        """Score in place; return the number of addons scored (logged in the summary)."""
        return HealthScore().enrich(addons)

    @staticmethod
    def _log_summary(sources: List[str], addons: List[TAddon], scored: int,
                     github_issues: List[str], timings: List[Tuple[str, float]]) -> None:
        """Final harvest summary: counts, health, anything not retrievable, timings last."""
        by_source = Counter(addon['source'] for addon in addons)
        breakdown = ', '.join('%s: %d' % (name, by_source.get(name, 0)) for name in sources)
        logger.info('harvested %d addons | %s', len(addons), breakdown)
        logger.info('health: scored %d/%d addons', scored, len(addons))

        if github_issues:
            logger.warning('github: %d repo(s) could not be retrieved during enrichment:', len(github_issues))
            for message in github_issues:
                logger.warning('  - %s', message)

        if timings:
            spent = ', '.join('%s=%.1fs' % (name, seconds) for name, seconds in timings)
            logger.info('timings: %s (total %.1fs)', spent, sum(seconds for _, seconds in timings))

    @staticmethod
    def _build_snapshot(addons: List[TAddon], sources: List[str]) -> TSnapshot:
        generated = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        return TSnapshot(
            generated=generated,
            schema_version=SCHEMA_VERSION,
            source='+'.join(sources),
            addons=addons,
        )
