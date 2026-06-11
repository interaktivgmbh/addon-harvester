from unittest.mock import patch

from addon_harvester.sources.base import HarvestBase
from addon_harvester.sources.npm import NpmSource

HTTP_GET = 'addon_harvester.http.HttpClient.get_json'


class TestSource:
    def test_is_a_harvest_base_subclass(self):
        # postcondition
        assert issubclass(NpmSource, HarvestBase)

    def test_list_packages_unions_and_sorts_search_results(self):
        # setup
        source = NpmSource(30, queries=['keywords:volto'])
        page = {'objects': [{'package': {'name': 'b-addon'}}, {'package': {'name': 'a-addon'}}], 'total': 2}

        # do it
        with patch(HTTP_GET, return_value=page):
            names = source.list_packages()

        # postcondition
        assert names == ['a-addon', 'b-addon']

    def test_list_packages_captures_search_metrics(self):
        # setup
        source = NpmSource(30, queries=['keywords:volto'])
        obj = {'package': {'name': 'a-addon'}, 'downloads': {'weekly': 1351, 'monthly': 5523},
               'dependents': 8, 'flags': {'insecure': 0}}
        page = {'objects': [obj], 'total': 1}

        # do it
        with patch(HTTP_GET, return_value=page):
            source.list_packages()

        # postcondition
        assert source.metrics['a-addon'] == {
            'downloads': {'day': None, 'week': 1351, 'month': 5523},
            'dependents': 8,
            'insecure': False,
        }

    def test_normalize_applies_captured_metrics(self):
        # setup
        source = NpmSource(30)
        source.metrics['@plone/volto-form-block'] = {
            'downloads': {'day': None, 'week': 100, 'month': 400}, 'dependents': 3, 'insecure': True}
        packument = {'name': '@plone/volto-form-block', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}}, 'time': {}}

        # do it
        addon = source.normalize(packument)

        # postcondition
        assert addon['stats']['downloads_month'] == 400
        assert addon['stats']['npm_dependents'] == 3
        assert addon['stats']['npm_insecure'] is True

    def test_fetch_downloads_is_a_noop(self):
        # do it
        downloads = NpmSource(30).fetch_downloads('@plone/volto-thing')
        # postcondition
        assert downloads is None

    def test_normalize_drops_non_addon_packument(self):
        # setup
        source = NpmSource(30)
        packument = {'name': 'left-pad', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': []}}}

        # do it
        result = source.normalize(packument)

        # postcondition
        assert result is None

    def test_normalize_keeps_volto_packument(self):
        # setup
        source = NpmSource(30)
        packument = {'name': '@plone/volto-form-block', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}}, 'time': {}}

        # do it
        addon = source.normalize(packument)

        # postcondition
        assert addon is not None
        assert addon['id'] == 'npm:@plone/volto-form-block'

    def test_get_json_delegates_to_http_client(self):
        # setup
        source = NpmSource(15)

        # do it
        with patch(HTTP_GET, return_value={'ok': True}) as helper:
            result = source.get_json('https://example.test/x')

        # postcondition
        assert result == {'ok': True}
        assert helper.call_args.args[0] == 'https://example.test/x'
        assert source.http.timeout == 15
