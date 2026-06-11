"""PyPI source — enumerate packages by trove classifier and fetch their metadata.

:class:`PyPISource` enumerates package names for one or more trove classifiers (a package
matches when it carries at least one of them), trying three paths in
order. The preferred one is the public BigQuery PyPI dataset (see
:class:`~addon_harvester.sources.bigquery.BigQueryClient`) — PyPI's supported bulk
API — used whenever credentials are configured in the environment. Second is the XML-RPC
``browse`` endpoint, which also returns only matching packages but is deprecated and may
be withdrawn. Last resort is the PyPI Simple index (every project name), letting
normalisation filter by classifier via
:meth:`~addon_harvester.normalizers.pypi.PyPINormalizer.has_classifier`;
:attr:`PyPISource.prefiltered` records whether the enumerated list is already filtered.
``fetch_package`` / ``fetch_downloads`` use the plain JSON HTTP APIs. All network access
is std-lib only (shared via :class:`HarvestBase`) and retries transient errors.
"""
import xmlrpc.client
from typing import Dict, Iterable, List, Optional, Sequence

from .. import logger
from .base import HarvestBase
from .bigquery import BigQueryClient
from ..config import (
    PYPI_JSON_URL,
    PYPI_SIMPLE_ACCEPT,
    PYPI_SIMPLE_URL,
    PYPI_XMLRPC_URL,
    PYPISTATS_RECENT_URL,
)
from ..http import TimeoutTransport
from ..normalizers.pypi import PyPINormalizer
from ..types import TAddon, TDownloads


class PyPISource(HarvestBase):
    """Harvest backend add-ons from PyPI for one or more trove classifiers."""

    name = 'pypi'

    def __init__(self, timeout: int, classifiers: Sequence[str]) -> None:
        super().__init__(timeout)
        self.classifiers = tuple(classifiers)
        self.normalizer = PyPINormalizer()
        self.prefiltered = True

    def list_packages(self) -> List[str]:
        """Candidate package names; records whether they are classifier-prefiltered.

        Tries the supported BigQuery dataset first (when configured), then the deprecated
        XML-RPC ``browse``; if both yield nothing falls back to the full Simple index,
        which is *not* pre-filtered — :meth:`normalize` then drops non-matching packages
        once their metadata is fetched.
        """
        names = self._browse_via_bigquery()
        if names:
            logger.info('found %d distinct packages for %s (BigQuery)',
                        len(names), ', '.join(map(repr, self.classifiers)))
            self.prefiltered = True
            return names
        names = self._browse_via_xmlrpc()
        if names:
            logger.info('found %d distinct packages for %s (XML-RPC browse)',
                        len(names), ', '.join(map(repr, self.classifiers)))
            self.prefiltered = True
            return names
        logger.warning('BigQuery and XML-RPC browse returned nothing; falling back to the PyPI '
                       'Simple index (fetches metadata for every project — much slower)')
        self.prefiltered = False
        return self._list_via_simple()

    def _browse_via_bigquery(self) -> List[str]:
        """Distinct package names carrying any of the classifiers via the public BigQuery dataset.

        Returns an empty list when BigQuery is not configured in the environment or the
        query fails, so the caller can fall through to the next enumeration path.
        """
        client = BigQueryClient.from_env(self.timeout)
        if client is None:
            logger.info('BigQuery not configured (set BIGQUERY_PROJECT and credentials) — '
                        'trying the deprecated XML-RPC browse')
            return []
        return self._merge_names(
            client.list_names_for_classifier(classifier) for classifier in self.classifiers)

    def _browse_via_xmlrpc(self) -> List[str]:
        """Distinct package names carrying any of the classifiers via the (deprecated) XML-RPC browse.

        ``browse`` ANDs multiple classifiers, so we query once per classifier and union the
        results. Each call returns one ``[name, version]`` pair per matching release, which
        :meth:`_merge_names` collapses to distinct names. Returns an empty list on any
        failure so the caller can fall back to the Simple index.
        """
        try:
            transport = TimeoutTransport(self.timeout)
            client = xmlrpc.client.ServerProxy(PYPI_XMLRPC_URL, transport=transport)
            batches = [[name for name, _version in client.browse([classifier])]
                       for classifier in self.classifiers]
        except Exception as error:
            logger.warning('XML-RPC browse failed (%s); falling back to the PyPI Simple index', error)
            return []
        return self._merge_names(batches)

    @staticmethod
    def _merge_names(batches: Iterable[List[str]]) -> List[str]:
        """Union of name lists, collapsed case-insensitively (first-seen spelling wins)."""
        seen: Dict[str, str] = {}
        for batch in batches:
            for name in batch:
                seen.setdefault(name.lower(), name)
        return sorted(seen.values(), key=str.lower)

    def _list_via_simple(self) -> List[str]:
        """Every project name from the PyPI Simple index (no classifier info — filter later)."""
        data = self.get_json(PYPI_SIMPLE_URL, accept=PYPI_SIMPLE_ACCEPT)
        projects = (data or {}).get('projects') or []
        names = sorted({p['name'] for p in projects if p.get('name')}, key=str.lower)
        logger.info('Simple index: %d projects (filtered locally by classifier)', len(names))
        return names

    def fetch_package(self, name: str) -> Optional[dict]:
        """Raw PyPI JSON document for ``name`` (``None`` if unavailable)."""
        return self.get_json(PYPI_JSON_URL.format(name=name))

    def fetch_downloads(self, name: str) -> Optional[TDownloads]:
        """Recent day/week/month download counts from pypistats.org (one call, ``None`` if unavailable)."""
        data = self.get_json(PYPISTATS_RECENT_URL.format(name=name))
        if not data:
            return None

        recent = data.get('data') or {}

        return TDownloads(
            day=recent.get('last_day'),
            week=recent.get('last_week'),
            month=recent.get('last_month'),
        )

    def normalize(self, data: dict, downloads: Optional[TDownloads] = None) -> Optional[TAddon]:
        """Normalise a PyPI document, dropping it if it lacks every classifier (Simple-index path)."""
        if not self.prefiltered and not any(
                PyPINormalizer.has_classifier(data, classifier) for classifier in self.classifiers):
            return None
        return self.normalizer.normalize(data, downloads=downloads)
