from unittest.mock import MagicMock, patch

from addon_harvester.config import PYPI_SIMPLE_URL
from addon_harvester.sources.base import HarvestBase
from addon_harvester.sources.pypi import PyPISource

BIGQUERY = 'addon_harvester.sources.pypi.PyPISource._browse_via_bigquery'
BROWSE = 'addon_harvester.sources.pypi.PyPISource._browse_via_xmlrpc'
FROM_ENV = 'addon_harvester.sources.pypi.BigQueryClient.from_env'
HTTP_GET = 'addon_harvester.http.HttpClient.get_json'


class TestEnumeration:
    def test_bigquery_result_is_prefiltered_and_skips_xmlrpc(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))

        # do it
        with patch(BIGQUERY, return_value=['collective.a', 'collective.b']), \
                patch(BROWSE) as browse:
            names = source.list_packages()

        # postcondition
        assert names == ['collective.a', 'collective.b']
        assert source.prefiltered
        assert not browse.called

    def test_browse_result_is_prefiltered(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))

        # do it
        with patch(BIGQUERY, return_value=[]), \
                patch(BROWSE, return_value=['collective.a', 'collective.b']):
            names = source.list_packages()

        # postcondition
        assert names == ['collective.a', 'collective.b']
        assert source.prefiltered

    def test_falls_back_to_simple_index_when_browse_is_empty(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))
        simple = {'projects': [{'name': 'plone.app.foo'}, {'name': 'unrelated'}]}

        # do it
        with patch(BIGQUERY, return_value=[]), patch(BROWSE, return_value=[]), \
                patch(HTTP_GET, return_value=simple) as get_json:
            names = source.list_packages()

        # postcondition
        assert not source.prefiltered
        assert names == ['plone.app.foo', 'unrelated']
        assert get_json.call_args.args[0] == PYPI_SIMPLE_URL

    def test_bigquery_browse_returns_empty_when_not_configured(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))

        # do it
        with patch(FROM_ENV, return_value=None):
            names = source._browse_via_bigquery()

        # postcondition
        assert names == []

    def test_browse_swallows_errors_and_returns_empty(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))

        # do it
        with patch('xmlrpc.client.ServerProxy', side_effect=RuntimeError('gone')):
            names = source._browse_via_xmlrpc()

        # postcondition
        assert names == []

    def test_browse_queries_once_per_classifier_and_unions(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone', 'Framework :: Zope'))
        results = {'Framework :: Plone': [['collective.a', '1.0'], ['Collective.A', '1.1']],
                   'Framework :: Zope': [['zope.b', '2.0'], ['collective.a', '1.0']]}
        proxy = MagicMock()
        proxy.browse.side_effect = lambda classifiers: results[classifiers[0]]

        # do it
        with patch('xmlrpc.client.ServerProxy', return_value=proxy):
            names = source._browse_via_xmlrpc()

        # postcondition: per-classifier queries (browse ANDs them), case-insensitive union
        assert proxy.browse.call_count == 2
        assert names == ['collective.a', 'zope.b']

    def test_bigquery_queries_once_per_classifier_and_unions(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone', 'Framework :: Zope'))
        results = {'Framework :: Plone': ['collective.a'], 'Framework :: Zope': ['zope.b']}
        client = MagicMock()
        client.list_names_for_classifier.side_effect = results.get

        # do it
        with patch(FROM_ENV, return_value=client):
            names = source._browse_via_bigquery()

        # postcondition
        assert client.list_names_for_classifier.call_count == 2
        assert names == ['collective.a', 'zope.b']


class TestSource:
    def test_is_a_harvest_base_subclass(self):
        # postcondition
        assert issubclass(PyPISource, HarvestBase)

    def test_normalize_keeps_prefiltered_document(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))
        source.prefiltered = True
        document = {'info': {'name': 'collective.a', 'version': '1.0', 'classifiers': []}, 'urls': []}

        # do it
        addon = source.normalize(document)

        # postcondition
        assert addon is not None
        assert addon['id'] == 'pypi:collective.a'

    def test_normalize_drops_unmatched_document_on_simple_path(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))
        source.prefiltered = False
        document = {'info': {'name': 'unrelated', 'version': '1.0', 'classifiers': ['Framework :: Django']},
                    'urls': []}

        # do it
        result = source.normalize(document)

        # postcondition
        assert result is None

    def test_normalize_keeps_document_matching_any_classifier(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone', 'Framework :: Zope'))
        source.prefiltered = False
        document = {'info': {'name': 'zope.b', 'version': '1.0', 'classifiers': ['Framework :: Zope']},
                    'urls': []}

        # do it
        addon = source.normalize(document)

        # postcondition
        assert addon is not None
        assert addon['id'] == 'pypi:zope.b'

    def test_fetch_downloads_extracts_day_week_month(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))
        recent = {'data': {'last_day': 3, 'last_week': 21, 'last_month': 42}}

        # do it
        with patch(HTTP_GET, return_value=recent):
            downloads = source.fetch_downloads('collective.a')

        # postcondition
        assert downloads == {'day': 3, 'week': 21, 'month': 42}

    def test_fetch_downloads_returns_none_when_unavailable(self):
        # setup
        source = PyPISource(30, ('Framework :: Plone',))

        # do it
        with patch(HTTP_GET, return_value=None):
            downloads = source.fetch_downloads('collective.a')

        # postcondition
        assert downloads is None
