from typing import List, Optional

from ..types import TAddon, TStats
from . import age_in_days, config, score_at_least, score_below


class HealthScore:
    """Score each addon 0-100 from its already-normalised :class:`~addon_harvester.types.TAddon`.

    The base score (recency + documentation + metadata) needs no network and is computed for every
    snapshot. GitHub bonuses (stars, activity, open-issue ratio) only contribute when the matching
    ``stats.github_*`` / ``stats.last_commit`` fields have been populated by
    :class:`~addon_harvester.sources.github.GitHubEnricher` (i.e. after ``--with-github``).
    The final score is capped at :data:`~addon_harvester.healthscore.config.MAX_SCORE`.

    The scoring rubric lives in :mod:`~addon_harvester.healthscore.config`; the methods below
    only read addon fields and delegate the tier lookup to the helpers in
    :mod:`~addon_harvester.healthscore`.
    """

    def enrich(self, addons: List[TAddon]) -> int:
        for addon in addons:
            stats = addon.setdefault('stats', TStats(
                downloads_day=None, downloads_week=None, downloads_month=None,
                github_stars=None, github_watchers=None, github_open_issues=None,
                last_commit=None, npm_dependents=None, npm_insecure=None, health_score=None,
            ))
            stats['health_score'] = self.score(addon)

        return len(addons)

    def score(self, addon: TAddon) -> int:
        base = (
            self._compute_recency_points(addon.get('released'))
            + self._compute_documentation_points(addon)
            + self._compute_metadata_points(addon)
        )
        bonus = self._compute_github_bonus(addon.get('stats'))

        return min(config.MAX_SCORE, base + bonus)

    @staticmethod
    def _compute_recency_points(released: Optional[str]) -> int:
        age_days = age_in_days(released)
        if age_days is None:
            return 0

        return score_below(age_days, config.RECENCY_BUCKETS)

    @staticmethod
    def _compute_documentation_points(addon: TAddon) -> int:
        points = 0

        if len(addon.get('description') or '') > config.MIN_DESCRIPTION_CHARS:
            points += config.DESCRIPTION_POINTS

        if addon.get('homepage'):
            points += config.HOMEPAGE_POINTS

        if addon.get('repo_url'):
            points += config.REPO_POINTS

        if addon.get('has_screenshot'):
            points += config.SCREENSHOT_POINTS

        return points

    @staticmethod
    def _compute_metadata_points(addon: TAddon) -> int:
        points = 0

        if addon.get('license'):
            points += config.LICENSE_POINTS

        if len(addon.get('keywords') or []) >= config.MIN_KEYWORDS:
            points += config.KEYWORDS_POINTS

        compat = addon.get('compat') or {}
        if compat.get('plone') or compat.get('volto'):
            points += config.COMPAT_POINTS

        return points

    def _compute_github_bonus(self, stats: Optional[TStats]) -> int:
        if not stats:
            return 0

        return (
            self._compute_stars_bonus(stats.get('github_stars'))
            + self._compute_activity_bonus(stats.get('last_commit'))
            + self._compute_issue_bonus(stats.get('github_stars'), stats.get('github_open_issues'))
        )

    @staticmethod
    def _compute_stars_bonus(stars: Optional[int]) -> int:
        if not stars:
            return 0

        return score_at_least(stars, config.STARS_BUCKETS)

    @staticmethod
    def _compute_activity_bonus(last_commit: Optional[str]) -> int:
        age_days = age_in_days(last_commit)
        if age_days is None:
            return 0

        return score_below(age_days, config.ACTIVITY_BUCKETS)

    @staticmethod
    def _compute_issue_bonus(stars: Optional[int], open_issues: Optional[int]) -> int:
        """Reward a healthy open-issue-to-stars ratio (needs both fields from GitHub enrichment)."""
        if not stars or open_issues is None:
            return 0

        return score_below(open_issues / stars, config.ISSUE_RATIO_BUCKETS)
