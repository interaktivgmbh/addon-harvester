import os
from unittest.mock import patch

from addon_harvester.sources.bigquery import BigQueryClient

HTTP_GET = 'addon_harvester.http.HttpClient.get_json'
HTTP_POST = 'addon_harvester.http.HttpClient.post_json'
GCLOUD_TOKEN = 'addon_harvester.sources.bigquery.BigQueryClient.token_from_gcloud'


def rows(*names):
    return [{'f': [{'v': name}]} for name in names]


class TestFromEnv:
    def test_returns_none_without_a_project(self):
        # do it
        with patch.dict(os.environ, {}, clear=True):
            client = BigQueryClient.from_env(30)

        # postcondition
        assert client is None

    def test_builds_client_from_project_and_token(self):
        # setup
        env = {'BIGQUERY_PROJECT': 'my-project', 'BIGQUERY_TOKEN': 'my-token'}

        # do it
        with patch.dict(os.environ, env, clear=True):
            client = BigQueryClient.from_env(30)

        # postcondition
        assert client is not None
        assert client.project == 'my-project'
        assert client.auth_token == 'my-token'

    def test_falls_back_to_gcloud_for_the_token(self):
        # setup
        env = {'GOOGLE_CLOUD_PROJECT': 'my-project'}

        # do it
        with patch.dict(os.environ, env, clear=True), patch(GCLOUD_TOKEN, return_value='gcloud-token'):
            client = BigQueryClient.from_env(30)

        # postcondition
        assert client is not None
        assert client.auth_token == 'gcloud-token'

    def test_returns_none_when_no_token_is_obtainable(self):
        # setup
        env = {'BIGQUERY_PROJECT': 'my-project'}

        # do it
        with patch.dict(os.environ, env, clear=True), patch(GCLOUD_TOKEN, return_value=None):
            client = BigQueryClient.from_env(30)

        # postcondition
        assert client is None


class TestListNames:
    def test_collects_sorts_and_deduplicates_names(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)
        response = {'jobComplete': True, 'rows': rows('Products.B', 'collective.a', 'PRODUCTS.B')}

        # do it
        with patch(HTTP_POST, return_value=response):
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == ['collective.a', 'Products.B']

    def test_query_is_parameterised_with_the_classifier(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)
        response = {'jobComplete': True, 'rows': []}

        # do it
        with patch(HTTP_POST, return_value=response) as post_json:
            client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        payload = post_json.call_args.args[1]
        assert payload['queryParameters'][0]['parameterValue']['value'] == 'Framework :: Plone'
        assert post_json.call_args.kwargs['headers'] == {'Authorization': 'Bearer my-token'}

    def test_follows_the_page_token(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)
        first = {'jobComplete': True, 'rows': rows('collective.a'), 'pageToken': 'next-page',
                 'jobReference': {'jobId': 'job-1', 'location': 'US'}}
        second = {'jobComplete': True, 'rows': rows('collective.b')}

        # do it
        with patch(HTTP_POST, return_value=first), patch(HTTP_GET, return_value=second) as get_json:
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == ['collective.a', 'collective.b']
        assert 'pageToken=next-page' in get_json.call_args.args[0]
        assert 'job-1' in get_json.call_args.args[0]

    def test_polls_until_the_job_completes(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)
        pending = {'jobComplete': False, 'jobReference': {'jobId': 'job-1'}}
        done = {'jobComplete': True, 'rows': rows('collective.a')}

        # do it
        with patch(HTTP_POST, return_value=pending), patch(HTTP_GET, return_value=done) as get_json:
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == ['collective.a']
        assert 'pageToken' not in get_json.call_args.args[0]

    def test_returns_empty_when_the_query_fails(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)

        # do it
        with patch(HTTP_POST, return_value=None):
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == []

    def test_returns_empty_when_the_job_never_completes(self):
        # setup
        client = BigQueryClient('my-project', 'my-token', 30)
        pending = {'jobComplete': False, 'jobReference': {'jobId': 'job-1'}}

        # do it
        with patch(HTTP_POST, return_value=pending), patch(HTTP_GET, return_value=pending), \
                patch('addon_harvester.sources.bigquery.BIGQUERY_MAX_PAGES', 3):
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == []

    def test_returns_empty_when_the_job_reference_is_missing(self):
        # setup: incomplete job without a jobReference cannot be polled
        client = BigQueryClient('my-project', 'my-token', 30)

        # do it
        with patch(HTTP_POST, return_value={'jobComplete': False}):
            names = client.list_names_for_classifier('Framework :: Plone')

        # postcondition
        assert names == []


class TestTokenFromGcloud:
    def _result(self, returncode=0, stdout='gcloud-token\n'):
        class Result:
            pass
        result = Result()
        result.returncode = returncode
        result.stdout = stdout
        return result

    def test_returns_the_stripped_token(self):
        # do it
        with patch('subprocess.run', return_value=self._result()):
            token = BigQueryClient.token_from_gcloud()

        # postcondition
        assert token == 'gcloud-token'

    def test_returns_none_on_a_nonzero_exit(self):
        # do it
        with patch('subprocess.run', return_value=self._result(returncode=1, stdout='')):
            token = BigQueryClient.token_from_gcloud()

        # postcondition
        assert token is None

    def test_returns_none_when_gcloud_is_missing(self):
        # do it
        with patch('subprocess.run', side_effect=FileNotFoundError('no gcloud')):
            token = BigQueryClient.token_from_gcloud()

        # postcondition
        assert token is None
