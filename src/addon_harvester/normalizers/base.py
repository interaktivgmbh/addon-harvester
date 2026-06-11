import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..config import MAX_DESCRIPTION_CHARS
from ..types import TAddon, TDownloads, TStats


class Normalizer(ABC):
    """Map a raw registry document onto the normalised :class:`TAddon` schema."""
    _KEYWORD_SPLIT_RE = re.compile(r'[,\s]+')

    # markup stripping — registry descriptions ship Markdown / reStructuredText
    _CODE_FENCE_RE = re.compile(r'```.*?```|~~~.*?~~~', re.DOTALL)
    _RST_DIRECTIVE_RE = re.compile(r'^[ \t]*\.\.\s+\S.*$', re.MULTILINE)
    _RST_LITERAL_RE = re.compile(r'::\s*$', re.MULTILINE)
    _MD_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
    _RST_LINK_RE = re.compile(r'`([^`<]+?)\s*<[^>]+>`__?')
    _MD_INLINE_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
    _MD_REF_LINK_RE = re.compile(r'\[([^\]]*)\]\[[^\]]*\]')
    _MD_LINK_DEF_RE = re.compile(r'^[ \t]*\[[^\]]+\]:\s*\S+.*$', re.MULTILINE)
    _HTML_TAG_RE = re.compile(r'<[^>]+>')
    _HEADING_RE = re.compile(r'^[ \t]{0,3}#{1,6}[ \t]*', re.MULTILINE)
    _SETEXT_RULE_RE = re.compile(r'^[ \t]*([=\-*_])\1{2,}[ \t]*$', re.MULTILINE)
    _BLOCKQUOTE_RE = re.compile(r'^[ \t]{0,3}>[ \t]?', re.MULTILINE)
    _LIST_MARKER_RE = re.compile(r'^[ \t]{0,3}(?:[-*+]|\d+\.)[ \t]+', re.MULTILINE)
    _EMPHASIS_CHARS_RE = re.compile(r'[`*]+')
    _INLINE_WS_RE = re.compile(r'[ \t\f\v]+')
    _BLANK_LINES_RE = re.compile(r'[ \t]*\n[ \t]*')
    _PARAGRAPH_RE = re.compile(r'\n{3,}')

    # version parsing — leading numeric release + a pre-release marker tail (stdlib, PEP 440 / semver subset)
    _VERSION_CORE_RE = re.compile(r'\d+(?:\.\d+)*')
    _PRERELEASE_RE = re.compile(r'^[-_.]?(?:a|b|c|rc|alpha|beta|dev|pre|preview|nightly|snapshot|m)\d*', re.IGNORECASE)

    # screenshot detection — image references in raw Markdown / RST / HTML, minus CI/badge images
    _IMG_MD_RE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)')
    _IMG_HTML_RE = re.compile(r'<img\b[^>]*\bsrc=["\']?([^"\'>\s]+)', re.IGNORECASE)
    _IMG_RST_RE = re.compile(r'\.\.\s+(?:image|figure)::\s*(\S+)', re.IGNORECASE)
    _BADGE_RE = re.compile(
        r'shields\.io|badgen|/badge|badge\.|travis-ci|circleci|coveralls|codecov|readthedocs\.org/projects/'
        r'|/workflows/[^)]*badge|/actions/workflows/|fury\.io|pyup\.io|snyk\.io|opencollective|gitter|deepsource',
        re.IGNORECASE,
    )

    @abstractmethod
    def normalize(self, data: Dict[str, Any], downloads: Optional[TDownloads] = None) -> TAddon:
        """Map a raw metadata document onto a normalised addon record."""

    @staticmethod
    def _stats(
        downloads: Optional[TDownloads] = None,
        *,
        github_stars: Optional[int] = None,
        github_watchers: Optional[int] = None,
        github_open_issues: Optional[int] = None,
        last_commit: Optional[str] = None,
        npm_dependents: Optional[int] = None,
        npm_insecure: Optional[bool] = None,
    ) -> TStats:
        """Build a :class:`TStats`; GitHub/health fields are filled by later enrichment."""
        downloads = downloads or {}

        return TStats(
            downloads_day=downloads.get('day'),
            downloads_week=downloads.get('week'),
            downloads_month=downloads.get('month'),
            github_stars=github_stars,
            github_watchers=github_watchers,
            github_open_issues=github_open_issues,
            last_commit=last_commit,
            npm_dependents=npm_dependents,
            npm_insecure=npm_insecure,
            health_score=None,
        )

    @classmethod
    def _version_info(cls, version: Optional[str]) -> Tuple[Optional[str], Optional[bool]]:
        """Return a lexicographically sortable key and a pre-release flag for ``version``.

        ``version_sortable`` zero-pads each numeric release segment and appends ``9`` for stable /
        ``0`` for pre-releases, so a plain ascending string sort orders versions correctly and keeps
        pre-releases below their final release. Returns ``(None, None)`` for unparseable input.
        """
        if not version:
            return None, None

        raw = version.strip().lstrip('vV=')
        match = cls._VERSION_CORE_RE.match(raw)
        if not match:
            return None, None

        core = match.group(0)
        suffix = raw[len(core):]
        prerelease = suffix.startswith('-') or bool(cls._PRERELEASE_RE.search(suffix))
        padded = '.'.join('%05d' % int(part) for part in core.split('.')[:5])

        return '%s.%s' % (padded, '0' if prerelease else '9'), prerelease

    @classmethod
    def _detect_screenshot(cls, text: Optional[str]) -> bool:
        """True if the raw README/description embeds a real image (CI/coverage badges don't count)."""
        if not text:
            return False

        urls = cls._IMG_MD_RE.findall(text) + cls._IMG_HTML_RE.findall(text) + cls._IMG_RST_RE.findall(text)

        return any(not cls._BADGE_RE.search(url) for url in urls)

    @classmethod
    def _parse_keywords(cls, raw: Optional[str]) -> List[str]:
        if not raw:
            return []

        seen: Dict[str, None] = {}
        for token in cls._KEYWORD_SPLIT_RE.split(raw.lower()):
            token = token.strip()

            if token:
                seen.setdefault(token, None)

        return list(seen)

    @classmethod
    def _clean_description(cls, text: str) -> str:
        """Strip Markdown / reStructuredText markup down to clean, readable prose."""
        text = cls._strip_markup(text or '')

        if len(text) > MAX_DESCRIPTION_CHARS:
            text = text[:MAX_DESCRIPTION_CHARS].rstrip() + '…'

        return text

    @classmethod
    def _strip_markup(cls, text: str) -> str:
        text = cls._CODE_FENCE_RE.sub(' ', text)
        text = cls._RST_DIRECTIVE_RE.sub('', text)
        text = cls._MD_LINK_DEF_RE.sub('', text)
        text = cls._MD_IMAGE_RE.sub('', text)
        text = cls._RST_LINK_RE.sub(r'\1', text)
        text = cls._MD_INLINE_LINK_RE.sub(r'\1', text)
        text = cls._MD_REF_LINK_RE.sub(r'\1', text)
        text = cls._HTML_TAG_RE.sub(' ', text)
        text = cls._SETEXT_RULE_RE.sub('', text)
        text = cls._HEADING_RE.sub('', text)
        text = cls._BLOCKQUOTE_RE.sub('', text)
        text = cls._LIST_MARKER_RE.sub('', text)
        text = cls._RST_LITERAL_RE.sub('', text)
        text = cls._EMPHASIS_CHARS_RE.sub('', text)

        # normalise whitespace, keep paragraph breaks
        text = cls._INLINE_WS_RE.sub(' ', text)
        text = cls._BLANK_LINES_RE.sub('\n', text)
        text = cls._PARAGRAPH_RE.sub('\n\n', text)

        return text.strip()
