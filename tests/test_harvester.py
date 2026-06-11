import logging
from unittest.mock import patch

import pytest

from addon_harvester.harvester import Harvester
from addon_harvester.options import HarvestOptions
from addon_harvester.sources.npm import NpmSource
from addon_harvester.sources.pypi import PyPISource


def _addon(addon_id, source, name):
    kind = 'backend' if source == 'pypi' else 'frontend'
    return {'id': addon_id, 'source': source, 'name': name, 'kind': kind,
            'keywords': [], 'repo_url': None, 'pairs_with': []}


class FakeSource:
    def __init__(self, addons):
        self._addons = addons

    def harvest(self, **kwargs):
        return list(self._addons)


class TestRun:
    def test_returns_snapshot_with_sorted_addons(self):
        # setup
        by_source = {
            'pypi': [_addon('pypi:collective.thing', 'pypi', 'collective.thing')],
            'npm': [_addon('npm:volto-thing', 'npm', 'volto-thing')],
        }
        options = HarvestOptions(sources=('pypi', 'npm'))

        # do it
        with patch.object(Harvester, 'build_source', side_effect=lambda name: FakeSource(by_source[name])):
            snapshot = Harvester(options).run()

        # postcondition
        assert snapshot['schema_version'] == 3
        assert snapshot['source'] == 'pypi+npm'
        assert [a['id'] for a in snapshot['addons']] == ['npm:volto-thing', 'pypi:collective.thing']
        assert snapshot['generated'].endswith('Z')

    def test_logs_per_source_timings_and_a_summary(self, caplog):
        # setup
        by_source = {
            'pypi': [_addon('pypi:collective.thing', 'pypi', 'collective.thing')],
            'npm': [_addon('npm:volto-thing', 'npm', 'volto-thing')],
        }
        options = HarvestOptions(sources=('pypi', 'npm'))

        # do it
        with patch.object(Harvester, 'build_source', side_effect=lambda name: FakeSource(by_source[name])), \
                caplog.at_level(logging.INFO, logger='addon_harvester'):
            Harvester(options).run()

        # postcondition
        messages = [record.getMessage() for record in caplog.records]
        assert any(message.startswith('pypi: finished in ') for message in messages)
        assert any(message.startswith('npm: finished in ') for message in messages)
        assert any(message.startswith('timings: pypi=') and 'npm=' in message and 'total' in message
                   for message in messages)

    def test_with_github_but_no_token_skips_enrichment(self, caplog):
        # setup
        by_source = {'pypi': [_addon('pypi:collective.thing', 'pypi', 'collective.thing')]}
        options = HarvestOptions(sources=('pypi',), with_github=True)

        # do it
        with patch.object(Harvester, 'build_source', side_effect=lambda name: FakeSource(by_source[name])), \
                patch('addon_harvester.sources.github.GitHubEnricher.token_from_env', return_value=None), \
                caplog.at_level(logging.INFO, logger='addon_harvester'):
            snapshot = Harvester(options).run()

        # postcondition: run survives, warning logged, no github stats applied
        assert len(snapshot['addons']) == 1
        assert any('no GITHUB_TOKEN' in record.getMessage() for record in caplog.records)

    def test_unknown_source_raises_value_error(self):
        # do it / postcondition
        with pytest.raises(ValueError):
            Harvester(HarvestOptions(sources=('bogus',))).run()


class TestBuildSource:
    def test_pypi_builds_pypi_source(self):
        # do it
        source = Harvester(HarvestOptions()).build_source('pypi')

        # postcondition
        assert isinstance(source, PyPISource)

    def test_npm_builds_npm_source(self):
        # do it
        source = Harvester(HarvestOptions()).build_source('npm')

        # postcondition
        assert isinstance(source, NpmSource)
