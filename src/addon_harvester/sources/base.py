from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

from .. import logger
from ..config import DEFAULT_WORKERS
from ..http import HttpClient
from ..types import TAddon, TDownloads


class HarvestBase(ABC):
    """Source interface and pipeline: enumerate -> concurrent fetch -> normalise.

    Concrete sources implement :meth:`list_packages` / :meth:`fetch_package` /
    :meth:`fetch_downloads` / :meth:`normalize`; :meth:`harvest` drives them identically
    for every source. Network access goes through the shared :class:`HttpClient`.
    """

    name: str = ''

    def __init__(self, timeout: int) -> None:
        self.http = HttpClient(timeout)

    @property
    def timeout(self) -> int:
        return self.http.timeout

    def get_json(self, url: str, accept: str = 'application/json') -> Optional[Any]:
        return self.http.get_json(url, accept=accept)

    @abstractmethod
    def list_packages(self) -> List[str]:
        """Candidate package names to harvest for this source."""

    @abstractmethod
    def fetch_package(self, name: str) -> Optional[dict]:
        """Raw metadata document for ``name`` (``None`` if unavailable)."""

    @abstractmethod
    def fetch_downloads(self, name: str) -> Optional[TDownloads]:
        """Recent download counts (day/week/month) for ``name`` (``None`` if unavailable)."""

    @abstractmethod
    def normalize(self, data: dict, downloads: Optional[TDownloads] = None) -> Optional[TAddon]:
        """Map a raw metadata document onto the normalised addon schema.

        Returns ``None`` when the document should be dropped (e.g. it does not actually
        match the source's selection criteria once its metadata is inspected).
        """

    def harvest(self, limit: int = 0, with_downloads: bool = False, workers: int = DEFAULT_WORKERS) -> List[TAddon]:
        names = self.list_packages()

        if limit:
            names = names[:limit]

        return self._collect(names, with_downloads, workers)

    def _collect(self, names: List[str], with_downloads: bool, workers: int) -> List[TAddon]:
        """Run :meth:`_harvest_one` over ``names`` concurrently; skip dropped results."""
        addons: List[TAddon] = []
        total = len(names)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._harvest_one, name, with_downloads) for name in names]

            for index, future in enumerate(futures, start=1):
                addon = future.result()

                if addon is not None:
                    addons.append(addon)

                if index % 100 == 0 or index == total:
                    logger.info('%s: processed %d/%d (%d kept)', self.name, index, total, len(addons))

        return addons

    def _harvest_one(self, name: str, with_downloads: bool) -> Optional[TAddon]:
        """Fetch and normalise a single package (``None`` if unavailable or dropped)."""
        data = self.fetch_package(name)

        if not data:
            return None

        return self.normalize(data, downloads=self.fetch_downloads(name) if with_downloads else None)
