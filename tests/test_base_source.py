from typing import List, Optional

from addon_harvester.sources.base import HarvestBase
from addon_harvester.types import TAddon, TDownloads


class StubSource(HarvestBase):
    """Minimal source: 'b' fails to fetch, 'c' is dropped by normalisation."""

    name = 'stub'

    def __init__(self) -> None:
        super().__init__(timeout=1)
        self.downloads_requested: List[str] = []

    def list_packages(self) -> List[str]:
        return ['a', 'b', 'c']

    def fetch_package(self, name: str) -> Optional[dict]:
        return None if name == 'b' else {'name': name}

    def fetch_downloads(self, name: str) -> Optional[TDownloads]:
        self.downloads_requested.append(name)
        return TDownloads(day=1, week=2, month=3)

    def normalize(self, data: dict, downloads: Optional[TDownloads] = None) -> Optional[TAddon]:
        if data['name'] == 'c':
            return None
        return {'id': data['name'], 'downloads': downloads}


class TestHarvestPipeline:
    def test_keeps_only_fetched_and_normalised_packages(self):
        # do it
        addons = StubSource().harvest(workers=2)

        # postcondition: 'b' failed to fetch, 'c' was dropped by normalize
        assert [addon['id'] for addon in addons] == ['a']

    def test_limit_caps_the_enumerated_names(self):
        # setup
        source = StubSource()

        # do it
        addons = source.harvest(limit=1, with_downloads=True, workers=2)

        # postcondition: only 'a' was processed at all
        assert [addon['id'] for addon in addons] == ['a']
        assert source.downloads_requested == ['a']

    def test_downloads_are_skipped_by_default(self):
        # setup
        source = StubSource()

        # do it
        addons = source.harvest(workers=2)

        # postcondition
        assert source.downloads_requested == []
        assert addons[0]['downloads'] is None

    def test_downloads_are_fetched_and_passed_to_normalize(self):
        # setup
        source = StubSource()

        # do it
        addons = source.harvest(with_downloads=True, workers=2)

        # postcondition: fetched for every package with metadata ('b' never got that far)
        assert sorted(source.downloads_requested) == ['a', 'c']
        assert addons[0]['downloads'] == {'day': 1, 'week': 2, 'month': 3}
