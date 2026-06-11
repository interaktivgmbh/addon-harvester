import re
from typing import Any, Dict, List, Optional

from .base import Normalizer
from ..config import DEFAULT_TRUST, LICENSE_CLASSIFIER_MAP, PLONE_TYPE_CATEGORIES, REPO_URL_KEYS, VCS_HOSTS
from ..types import TAddon, TCompat, TDownloads


class PyPINormalizer(Normalizer):
    _PLONE_VERSION_RE = re.compile(r'^\d+\.\d+$')
    _PYTHON_VERSION_RE = re.compile(r'^\d+(?:\.\d+)?$')

    @staticmethod
    def has_classifier(data: dict, classifier: str) -> bool:
        classifiers = (data.get('info') or {}).get('classifiers') or []
        prefix = '%s ::' % classifier
        return any(c == classifier or c.startswith(prefix) for c in classifiers)

    def normalize(self, data: Dict[str, Any], downloads: Optional[TDownloads] = None) -> TAddon:
        info = data['info']
        name = info['name']
        classifiers = info.get('classifiers') or []
        raw_description = info.get('description') or ''
        version_sortable, prerelease = self._version_info(info.get('version'))

        return TAddon(
            id='pypi:%s' % name,
            kind='backend',
            source='pypi',
            name=name,
            title=self._humanize_title(name),
            summary=(info.get('summary') or '').strip(),
            description=self._clean_description(raw_description),
            categories=self._categories(classifiers),
            keywords=self._parse_keywords(info.get('keywords')),
            latest_version=info.get('version') or '',
            version_sortable=version_sortable,
            prerelease=prerelease,
            released=self._released(data),
            license=self._license(info),
            repo_url=self._repo_url(info),
            homepage=self._homepage(info),
            has_screenshot=self._detect_screenshot(raw_description),
            compat=TCompat(
                plone=self._plone_versions(classifiers),
                volto=None,
                python=self._python_versions(classifiers),
            ),
            installable_profile=None,
            stats=self._stats(downloads),
            pairs_with=[],
            trust=DEFAULT_TRUST,
        )

    @staticmethod
    def _humanize_title(name: str) -> str:
        leaf = name.split('.')[-1].split('-')[-1]
        if any(c.isupper() for c in leaf[1:]):
            return leaf

        return leaf.replace('_', ' ').title()

    @classmethod
    def _plone_versions(cls, classifiers: List[str]) -> Optional[List[str]]:
        versions = []

        for classifier in classifiers:
            parts = [p.strip() for p in classifier.split('::')]
            if len(parts) == 3 and parts[0] == 'Framework' and parts[1] == 'Plone':
                if cls._PLONE_VERSION_RE.match(parts[2]):
                    versions.append(parts[2])

        return sorted(set(versions)) or None

    @classmethod
    def _python_versions(cls, classifiers: List[str]) -> Optional[List[str]]:
        versions = []

        for classifier in classifiers:
            parts = [p.strip() for p in classifier.split('::')]
            if len(parts) == 3 and parts[0] == 'Programming Language' and parts[1] == 'Python':
                if cls._PYTHON_VERSION_RE.match(parts[2]):
                    versions.append(parts[2])

        return sorted(set(versions), key=lambda v: [int(n) for n in v.split('.')]) or None

    @staticmethod
    def _categories(classifiers: List[str]) -> List[str]:
        categories: Dict[str, None] = {}

        for classifier in classifiers:
            parts = [p.strip() for p in classifier.split('::')]
            if len(parts) == 3 and parts[0] == 'Framework' and parts[1] == 'Plone':
                category = PLONE_TYPE_CATEGORIES.get(parts[2])
                if category:
                    categories.setdefault(category, None)

        return list(categories)

    @staticmethod
    def _license(info: Dict[str, Any]) -> Optional[str]:
        for classifier in info.get('classifiers') or []:
            if classifier in LICENSE_CLASSIFIER_MAP:
                return LICENSE_CLASSIFIER_MAP[classifier]
        expression = info.get('license_expression')

        if expression:
            return expression

        license_text = (info.get('license') or '').strip()
        if license_text and len(license_text) <= 50 and '\n' not in license_text:
            return license_text

        return None

    @staticmethod
    def _repo_url(info: Dict[str, Any]) -> Optional[str]:
        project_urls = info.get('project_urls') or {}
        lowered = {key.lower(): value for key, value in project_urls.items()}

        for key in REPO_URL_KEYS:
            value = lowered.get(key)
            if value and any(host in value for host in VCS_HOSTS):
                return value

        for value in project_urls.values():
            if value and any(host in value for host in VCS_HOSTS):
                return value

        home_page = info.get('home_page')
        if home_page and any(host in home_page for host in VCS_HOSTS):
            return home_page

        return None

    @staticmethod
    def _homepage(info: Dict[str, Any]) -> Optional[str]:
        project_urls = info.get('project_urls') or {}
        return (
                project_urls.get('Homepage')
                or info.get('home_page')
                or info.get('project_url')
                or None
        )

    @staticmethod
    def _released(data: Dict[str, Any]) -> Optional[str]:
        uploads = [
            f.get('upload_time_iso_8601')
            for f in data.get('urls') or []
            if f.get('upload_time_iso_8601')
        ]

        if not uploads:
            return None

        return min(uploads)[:10]
