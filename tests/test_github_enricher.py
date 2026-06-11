import os
from unittest.mock import patch

from addon_harvester.sources.github import GitHubEnricher

POST_GRAPHQL = 'addon_harvester.sources.github.GitHubEnricher._post_graphql'


def _addon(repo_url):
    return {'id': 'pypi:x', 'repo_url': repo_url, 'stats': {}}


class TestParseRepo:
    def test_extracts_owner_and_name_from_https_url(self):
        # do it / postcondition
        assert GitHubEnricher.parse_repo('https://github.com/collective/plone.api') \
            == ('collective', 'plone.api')

    def test_strips_a_git_suffix(self):
        # do it / postcondition
        assert GitHubEnricher.parse_repo('git@github.com:collective/repo.git') == ('collective', 'repo')

    def test_ignores_other_hosts_and_missing_urls(self):
        # do it / postcondition
        assert GitHubEnricher.parse_repo('https://gitlab.com/owner/repo') is None
        assert GitHubEnricher.parse_repo(None) is None


class TestTokenFromEnv:
    def test_prefers_github_token_and_falls_back_to_gh_token(self):
        # do it / postcondition
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'one', 'GH_TOKEN': 'two'}, clear=True):
            assert GitHubEnricher.token_from_env() == 'one'
        with patch.dict(os.environ, {'GH_TOKEN': 'two'}, clear=True):
            assert GitHubEnricher.token_from_env() == 'two'
        with patch.dict(os.environ, {}, clear=True):
            assert GitHubEnricher.token_from_env() is None


class TestEnrich:
    def _node(self):
        return {'stargazerCount': 7, 'watchers': {'totalCount': 3},
                'issues': {'totalCount': 2}, 'pushedAt': '2026-06-01T12:00:00Z', 'isArchived': False}

    def test_applies_stats_to_every_addon_of_the_repo(self):
        # setup
        first = _addon('https://github.com/collective/repo')
        second = _addon('https://github.com/Collective/Repo')  # same repo, different case
        enricher = GitHubEnricher('token', 30)

        # do it
        with patch(POST_GRAPHQL, return_value={'data': {'r0': self._node()}}) as post:
            enriched = enricher.enrich([first, second])

        # postcondition: one deduplicated repo, both addons enriched
        assert post.call_count == 1
        assert enriched == 2
        for addon in (first, second):
            assert addon['stats']['github_stars'] == 7
            assert addon['stats']['github_watchers'] == 3
            assert addon['stats']['github_open_issues'] == 2
            assert addon['stats']['last_commit'] == '2026-06-01'

    def test_collects_graphql_errors_once_for_the_summary(self):
        # setup
        addon = _addon('https://github.com/collective/gone')
        enricher = GitHubEnricher('token', 30)
        response = {'data': {'r0': None},
                    'errors': [{'message': 'Could not resolve'}, {'message': 'Could not resolve'}]}

        # do it
        with patch(POST_GRAPHQL, return_value=response):
            enriched = enricher.enrich([addon])

        # postcondition
        assert enriched == 0
        assert enricher.unresolved == ['Could not resolve']
        assert addon['stats'] == {}

    def test_batches_repos_by_batch_size(self):
        # setup
        addons = [_addon('https://github.com/owner/repo-%d' % index) for index in range(3)]
        enricher = GitHubEnricher('token', 30, batch_size=2)

        # do it
        with patch(POST_GRAPHQL, return_value={'data': {}}) as post:
            enricher.enrich(addons)

        # postcondition
        assert post.call_count == 2

    def test_query_escapes_quotes_in_repo_names(self):
        # setup
        enricher = GitHubEnricher('token', 30)
        batch = [{'owner': 'owner"x', 'name': 'repo', 'addons': []}]

        # do it
        query = enricher._build_query(batch)

        # postcondition
        assert 'owner\\"x' in query
