"""npm source — enumerate Volto/Aurora add-ons and fetch their metadata.

:class:`NpmSource` runs the registry search API for the community keyword queries and unions
the results, then fetches the registry packument for each candidate. The search response also
carries per-package metrics (weekly/monthly downloads, dependent count, an ``insecure`` flag),
which are captured during enumeration and applied in :meth:`normalize` — so npm downloads need
no extra request and are always present. Genuine Volto/Aurora add-ons are kept and search noise
dropped via :meth:`~addon_harvester.normalizers.npm.NpmNormalizer.is_frontend_addon`.
Std-lib only; the retrying HTTP GET is shared with the other sources via :class:`HarvestBase`.
"""
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence

from .. import logger
from .base import HarvestBase
from ..config import (
    DEFAULT_NPM_QUERIES,
    NPM_PACKUMENT_URL,
    NPM_SEARCH_MAX,
    NPM_SEARCH_PAGE_SIZE,
    NPM_SEARCH_URL,
)
from ..normalizers.npm import NpmNormalizer
from ..types import TAddon, TDownloads


class NpmSource(HarvestBase):
    """Harvest frontend (Volto/Aurora) add-ons from the npm registry."""

    name = 'npm'

    def __init__(self, timeout: int, queries: Optional[Sequence[str]] = None) -> None:
        super().__init__(timeout)
        self.queries = list(queries) if queries is not None else list(DEFAULT_NPM_QUERIES)
        self.normalizer = NpmNormalizer()
        # downloads / dependents / insecure ride along in the search response, keyed by package
        # name so normalize() can pick them up later (first spelling wins).
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def list_packages(self) -> List[str]:
        """Distinct candidate package names across all search queries, sorted."""
        seen: dict = {}
        for query in self.queries:
            for name in self._search(query):
                seen.setdefault(name, None)
            logger.info('npm search %r -> %d distinct candidates so far', query, len(seen))
        return sorted(seen, key=str.lower)

    def _search(self, query: str) -> List[str]:
        """All package names the registry search returns for ``query`` (paginated)."""
        names: List[str] = []
        offset = 0
        while offset < NPM_SEARCH_MAX:
            params = urllib.parse.urlencode({'text': query, 'size': NPM_SEARCH_PAGE_SIZE, 'from': offset})
            data = self.get_json('%s?%s' % (NPM_SEARCH_URL, params))
            if not data:
                break
            objects = data.get('objects') or []
            for obj in objects:
                name = (obj.get('package') or {}).get('name') if isinstance(obj, dict) else None
                if not name:
                    logger.warning('npm search %r: skipping result without package.name (%r)', query, obj)
                    continue
                names.append(name)
                self.metrics.setdefault(name, self._metrics(obj))
            offset += len(objects)
            if not objects or offset >= (data.get('total') or 0):
                break
        return names

    @staticmethod
    def _metrics(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Pull downloads / dependents / insecure flag out of one search result object."""
        downloads = obj.get('downloads') or {}
        flags = obj.get('flags') or {}

        return {
            'downloads': TDownloads(day=None, week=downloads.get('weekly'), month=downloads.get('monthly')),
            'dependents': obj.get('dependents'),
            'insecure': bool(flags['insecure']) if 'insecure' in flags else None,
        }

    def fetch_package(self, name: str) -> Optional[dict]:
        """Raw npm packument for ``name`` (scoped names keep their literal ``/``)."""
        return self.get_json(NPM_PACKUMENT_URL.format(name=name))

    def fetch_downloads(self, name: str) -> Optional[TDownloads]:
        """No-op: npm download counts ship inside the search response (see :meth:`_search`)."""
        return None

    def normalize(self, data: dict, downloads: Optional[TDownloads] = None) -> Optional[TAddon]:
        """Normalise a packument, dropping it unless it is a genuine Volto/Aurora add-on."""
        if not NpmNormalizer.is_frontend_addon(data):
            return None

        metrics = self.metrics.get(data.get('name')) or {}

        return self.normalizer.normalize(
            data,
            downloads=metrics.get('downloads'),
            dependents=metrics.get('dependents'),
            insecure=metrics.get('insecure'),
        )
