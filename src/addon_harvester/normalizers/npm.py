import re
from typing import Any, Dict, List, Optional

from .base import Normalizer
from ..config import (
    DEFAULT_TRUST,
    NICK_CATEGORY,
    NPM_ADDON_KEYWORDS,
    NPM_ADDON_PEERS,
    NPM_NICK_KEYWORD,
    NPM_NICK_KEYWORD_PAIR,
    NPM_NICK_NAME_PREFIX,
    NPM_NICK_PEER,
    NPM_VOLTO_PEER,
)
from ..types import TAddon, TCompat, TDownloads


class NpmNormalizer(Normalizer):
    _MAJOR_RE = re.compile(r'(\d+)')

    @classmethod
    def is_frontend_addon(cls, packument: Dict[str, Any]) -> bool:
        """Keep genuine Volto/Aurora/Nick add-ons and drop registry-search noise."""
        name = (packument.get('name') or '').lower()

        if 'volto' in name:
            return True

        version = cls._latest_version(packument)
        keywords = {k.lower() for k in version.get('keywords') or []}

        if keywords.intersection(NPM_ADDON_KEYWORDS):
            return True

        for group in ('peerDependencies', 'dependencies'):
            deps = version.get(group) or {}
            if any(peer in deps for peer in NPM_ADDON_PEERS):
                return True

        return cls.is_nick_addon(packument)

    @classmethod
    def is_nick_addon(cls, packument: Dict[str, Any]) -> bool:
        """Nick (plone/nick) add-ons via unambiguous markers — the bare ``nick`` keyword is IRC noise."""
        name = (packument.get('name') or '').lower()
        if name.startswith(NPM_NICK_NAME_PREFIX):
            return True

        version = cls._latest_version(packument)
        keywords = {k.lower() for k in version.get('keywords') or []}

        if NPM_NICK_KEYWORD in keywords or keywords.issuperset(NPM_NICK_KEYWORD_PAIR):
            return True

        for group in ('peerDependencies', 'dependencies'):
            if NPM_NICK_PEER in (version.get(group) or {}):
                return True

        return False

    def normalize(self, data: Dict[str, Any], downloads: Optional[TDownloads] = None,
                  dependents: Optional[int] = None, insecure: Optional[bool] = None) -> TAddon:
        packument = data
        name = packument['name']
        latest = (packument.get('dist-tags') or {}).get('latest')
        version = self._latest_version(packument)
        keywords = self._parse_keywords(' '.join(version.get('keywords') or []))
        raw_readme = packument.get('readme') or version.get('description') or ''
        version_sortable, prerelease = self._version_info(latest)

        return TAddon(
            id='npm:%s' % name,
            kind='frontend',
            source='npm',
            name=name,
            title=self._humanize_title(name),
            summary=(version.get('description') or '').strip(),
            description=self._clean_description(raw_readme),
            categories=[NICK_CATEGORY] if self.is_nick_addon(packument) else [],
            keywords=keywords,
            latest_version=latest or '',
            version_sortable=version_sortable,
            prerelease=prerelease,
            released=self._released(packument, latest),
            license=self._license(version),
            repo_url=self._repo_url(version.get('repository') or packument.get('repository')),
            homepage=version.get('homepage') or 'https://www.npmjs.com/package/%s' % name,
            has_screenshot=self._detect_screenshot(raw_readme),
            compat=TCompat(plone=None, volto=self._volto_versions(version), python=None),
            installable_profile=False,
            stats=self._stats(downloads, npm_dependents=dependents, npm_insecure=insecure),
            pairs_with=[],
            trust=DEFAULT_TRUST,
        )

    @staticmethod
    def _latest_version(packument: Dict[str, Any]) -> Dict[str, Any]:
        latest = (packument.get('dist-tags') or {}).get('latest')
        return (packument.get('versions') or {}).get(latest, {}) if latest else {}

    @staticmethod
    def _humanize_title(name: str) -> str:
        leaf = name.split('/')[-1]
        return leaf.replace('-', ' ').replace('_', ' ').title()

    @staticmethod
    def _license(version: Dict[str, Any]) -> Optional[str]:
        license_field = version.get('license')

        if isinstance(license_field, dict):
            return license_field.get('type')

        return license_field or None

    @staticmethod
    def _released(packument: Dict[str, Any], latest: Optional[str]) -> Optional[str]:
        times = packument.get('time') or {}
        stamp = times.get(latest) or times.get('modified')

        return stamp[:10] if stamp else None

    @staticmethod
    def _repo_url(raw: Any) -> Optional[str]:
        url = raw.get('url') if isinstance(raw, dict) else raw

        if not url or not isinstance(url, str):
            return None

        url = url.strip()
        if url.startswith('git+'):
            url = url[4:]

        url = url.replace('ssh://git@', 'https://').replace('git@github.com:', 'https://github.com/')
        if url.startswith('git://'):
            url = 'https://' + url[len('git://'):]

        if url.endswith('.git'):
            url = url[:-4]

        return url if url.startswith('http') else None

    @classmethod
    def _volto_versions(cls, version: Dict[str, Any]) -> Optional[List[str]]:
        for group in ('peerDependencies', 'dependencies', 'devDependencies'):
            spec = (version.get(group) or {}).get(NPM_VOLTO_PEER)

            if not spec:
                continue

            majors = []
            for comparator in re.split(r'\s*\|\|\s*|\s+', spec):
                comparator = comparator.strip()

                if not comparator or comparator.startswith('<'):
                    continue

                match = cls._MAJOR_RE.search(comparator)
                if match:
                    majors.append(match.group(1))

            return sorted(set(majors), key=int) or None

        return None
