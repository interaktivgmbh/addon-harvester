"""GitHub enrichment — fill stars/last-commit on already-normalised records.

:class:`GitHubEnricher` is *not* a :class:`HarvestBase`: it does not enumerate packages, it
enriches existing addon records in place via a batched GraphQL query keyed by ``repo_url``.
Needs a token in ``GITHUB_TOKEN``/``GH_TOKEN``.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from .. import logger
from ..config import (
    GITHUB_BATCH_SIZE,
    GITHUB_GRAPHQL_URL,
    GITHUB_TOKEN_ENV,
    HTTP_BACKOFF_SECONDS,
    HTTP_RETRIES,
    USER_AGENT,
)
from ..types import TAddon


class GitHubEnricher:
    name = 'github'

    _REPO_RE = re.compile(r'github\.com[/:]+([^/]+)/([^/#?]+)', re.IGNORECASE)
    _RETRYABLE_STATUS = (403, 429, 500, 502, 503, 504)

    def __init__(self, auth_token: str, timeout: int, batch_size: int = GITHUB_BATCH_SIZE) -> None:
        self.auth_token = auth_token
        self.timeout = timeout
        self.batch_size = batch_size
        # per-repo GraphQL errors (missing repo, SAML, forbidden token) collected for the
        # end-of-run summary instead of being logged inline during enrichment.
        self.unresolved: List[str] = []

    @staticmethod
    def token_from_env() -> Optional[str]:
        for name in GITHUB_TOKEN_ENV:
            value = os.environ.get(name)

            if value:
                return value

        return None

    @classmethod
    def parse_repo(cls, url: Optional[str]) -> Optional[Tuple[str, str]]:
        """Extract ``(owner, name)`` from a github.com URL, or ``None`` for other hosts."""
        if not url:
            return None

        match = cls._REPO_RE.search(url)
        if not match:
            return None

        owner, name = match.group(1), match.group(2)
        if name.endswith('.git'):
            name = name[:-4]

        return owner, name

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace('\\', '\\\\').replace('"', '\\"')

    _REPO_FIELDS = 'stargazerCount watchers { totalCount } issues(states: OPEN) { totalCount } pushedAt isArchived'

    def _build_query(self, batch: List[Dict]) -> str:
        return 'query {\n%s\n}' % '\n'.join([
            'r%d: repository(owner: "%s", name: "%s") { %s }'
            % (index, self._escape(repo['owner']), self._escape(repo['name']), self._REPO_FIELDS)
            for index, repo in enumerate(batch)
        ])

    def _post_graphql(self, query: str) -> Optional[dict]:
        body = json.dumps({'query': query}).encode('utf-8')
        headers = {
            'Authorization': 'bearer %s' % self.auth_token,
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
        }

        for attempt in range(1, HTTP_RETRIES + 1):
            request = urllib.request.Request(GITHUB_GRAPHQL_URL, data=body, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)

            except urllib.error.HTTPError as error:
                if error.code not in self._RETRYABLE_STATUS or attempt == HTTP_RETRIES:
                    logger.warning('GitHub GraphQL failed: HTTP %s', error.code)
                    return None

            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                if attempt == HTTP_RETRIES:
                    logger.warning('GitHub GraphQL failed: %s', error)
                    return None

            time.sleep(HTTP_BACKOFF_SECONDS * attempt)

        return None

    def _index_repos(self, addons: List[TAddon]) -> List[Dict]:
        repos: Dict[Tuple[str, str], Dict] = {}

        for addon in addons:
            parsed = self.parse_repo(addon.get('repo_url'))
            if not parsed:
                continue
            key = (parsed[0].lower(), parsed[1].lower())
            entry = repos.setdefault(key, {'owner': parsed[0], 'name': parsed[1], 'addons': []})
            entry['addons'].append(addon)

        return list(repos.values())

    @staticmethod
    def _apply(node: Optional[dict], addons: List[TAddon]) -> None:
        if not node:
            return

        stars = node.get('stargazerCount')
        watchers = (node.get('watchers') or {}).get('totalCount')
        open_issues = (node.get('issues') or {}).get('totalCount')
        pushed = node.get('pushedAt')

        for addon in addons:
            addon['stats']['github_stars'] = stars
            addon['stats']['github_watchers'] = watchers
            addon['stats']['github_open_issues'] = open_issues
            if pushed:
                addon['stats']['last_commit'] = pushed[:10]

    def _collect_errors(self, errors: Optional[List[dict]]) -> None:
        """Record per-repo GraphQL errors (forbidden token, SAML, missing repo) once each."""
        for message in (e.get('message') for e in errors or [] if e.get('message')):
            if message not in self.unresolved:
                self.unresolved.append(message)

    def enrich(self, addons: List[TAddon]) -> int:
        """Fill github stats in place; return the number of addons enriched."""
        repos = self._index_repos(addons)
        logger.info('github: %d distinct repos across %d addons', len(repos), sum(len(r['addons']) for r in repos))

        enriched = 0
        for start in range(0, len(repos), self.batch_size):
            batch = repos[start:start + self.batch_size]
            data = self._post_graphql(self._build_query(batch))

            if not data:
                continue

            self._collect_errors(data.get('errors'))
            payload = data.get('data') or {}
            for index, repo in enumerate(batch):
                node = payload.get('r%d' % index)

                if node:
                    self._apply(node, repo['addons'])
                    enriched += len(repo['addons'])

            logger.info(
                'github: processed %d/%d repos (%d addons enriched)',
                min(start + self.batch_size, len(repos)), len(repos), enriched
            )

        return enriched
