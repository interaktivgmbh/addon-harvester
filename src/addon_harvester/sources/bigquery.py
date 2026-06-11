"""BigQuery enumeration — list PyPI package names for a trove classifier.

PyPI offers no supported search-by-classifier API (XML-RPC ``browse`` is deprecated); the
officially documented bulk path is the public BigQuery dataset
``bigquery-public-data.pypi.distribution_metadata``. :class:`BigQueryClient` runs one
parameterised query against it via the BigQuery REST API — std-lib only, no Google SDK.

Configuration comes from the environment (see :func:`BigQueryClient.from_env`): a billing
project in ``BIGQUERY_PROJECT``/``GOOGLE_CLOUD_PROJECT`` plus an OAuth2 access token in
``BIGQUERY_TOKEN``/``GOOGLE_OAUTH_ACCESS_TOKEN``; without a token we shell out to
``gcloud auth print-access-token`` so a logged-in workstation or CI service account works
without extra setup. Querying the public dataset is free-tier territory (the table scan is
far below the monthly quota), only the project for quota attribution is required.
"""
import os
import subprocess
import urllib.parse
from typing import Dict, List, Optional

from .. import logger
from ..config import (
    BIGQUERY_CLASSIFIER_QUERY,
    BIGQUERY_GCLOUD_TOKEN_COMMAND,
    BIGQUERY_MAX_PAGES,
    BIGQUERY_PAGE_SIZE,
    BIGQUERY_PROJECT_ENV,
    BIGQUERY_QUERY_URL,
    BIGQUERY_RESULTS_URL,
    BIGQUERY_TOKEN_ENV,
)
from ..http import HttpClient


class BigQueryClient:
    """Query the public PyPI metadata dataset for package names carrying a classifier."""

    name = 'bigquery'

    def __init__(self, project: str, auth_token: str, timeout: int) -> None:
        self.project = project
        self.auth_token = auth_token
        self.http = HttpClient(timeout)

    @staticmethod
    def project_from_env() -> Optional[str]:
        for name in BIGQUERY_PROJECT_ENV:
            value = os.environ.get(name)

            if value:
                return value

        return None

    @staticmethod
    def token_from_env() -> Optional[str]:
        for name in BIGQUERY_TOKEN_ENV:
            value = os.environ.get(name)

            if value:
                return value

        return None

    @staticmethod
    def token_from_gcloud() -> Optional[str]:
        try:
            result = subprocess.run(
                BIGQUERY_GCLOUD_TOKEN_COMMAND, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None

        token = result.stdout.strip()
        return token if result.returncode == 0 and token else None

    @classmethod
    def from_env(cls, timeout: int) -> Optional['BigQueryClient']:
        """Build a client from the environment, or ``None`` when BigQuery is not configured.

        A project without an obtainable token is reported loudly: the caller will fall back
        to a deprecated or much slower enumeration path.
        """
        project = cls.project_from_env()
        if not project:
            return None

        auth_token = cls.token_from_env() or cls.token_from_gcloud()
        if not auth_token:
            logger.warning('BigQuery project %r configured but no access token found '
                           '(set %s or log in with gcloud)', project, '/'.join(BIGQUERY_TOKEN_ENV))
            return None

        return cls(project, auth_token, timeout)

    def list_names_for_classifier(self, classifier: str) -> List[str]:
        """Distinct package names carrying ``classifier``, collapsed case-insensitively.

        Follows incomplete-job polling and result pagination; returns an empty list on any
        failure so the caller can fall back to another enumeration path.
        """
        url = BIGQUERY_QUERY_URL.format(project=self.project)
        data = self.http.post_json(url, self._query_payload(classifier), headers=self._auth_headers())

        seen: Dict[str, str] = {}
        for _page in range(BIGQUERY_MAX_PAGES):
            if data is None:
                return []

            if not data.get('jobComplete'):
                data = self._fetch_results(data)
                continue

            for row in data.get('rows') or []:
                fields = row.get('f') or []
                value = fields[0].get('v') if fields else None

                if value:
                    seen.setdefault(value.lower(), value)

            page_token = data.get('pageToken')
            if not page_token:
                return sorted(seen.values(), key=str.lower)

            data = self._fetch_results(data, page_token=page_token)

        logger.warning('BigQuery: query did not finish within %d pages/polls', BIGQUERY_MAX_PAGES)
        return []

    def _auth_headers(self) -> dict:
        return {'Authorization': 'Bearer %s' % self.auth_token}

    def _query_payload(self, classifier: str) -> dict:
        return {
            'query': BIGQUERY_CLASSIFIER_QUERY,
            'useLegacySql': False,
            'parameterMode': 'NAMED',
            'queryParameters': [{
                'name': 'classifier',
                'parameterType': {'type': 'STRING'},
                'parameterValue': {'value': classifier},
            }],
            'timeoutMs': self.http.timeout * 1000,
            'maxResults': BIGQUERY_PAGE_SIZE,
        }

    def _fetch_results(self, data: dict, page_token: Optional[str] = None) -> Optional[dict]:
        """Next ``getQueryResults`` page for the job referenced in ``data`` (poll when no token)."""
        job = data.get('jobReference') or {}
        job_id = job.get('jobId')

        if not job_id:
            return None

        params = {'timeoutMs': self.http.timeout * 1000, 'maxResults': BIGQUERY_PAGE_SIZE}
        if job.get('location'):
            params['location'] = job['location']
        if page_token:
            params['pageToken'] = page_token

        url = BIGQUERY_RESULTS_URL.format(project=self.project, job_id=job_id)
        return self.http.get_json('%s?%s' % (url, urllib.parse.urlencode(params)),
                                  headers=self._auth_headers())
