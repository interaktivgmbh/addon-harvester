from datetime import datetime, timedelta, timezone

from addon_harvester.healthscore.healthscore import HealthScore


def _day(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime('%Y-%m-%d')


def _addon(**overrides):
    addon = {
        'released': None,
        'description': '',
        'homepage': None,
        'repo_url': None,
        'license': None,
        'keywords': [],
        'has_screenshot': False,
        'compat': {'plone': None, 'volto': None},
        'stats': {'downloads_day': None, 'downloads_week': None, 'downloads_month': None,
                  'github_stars': None, 'github_watchers': None, 'github_open_issues': None,
                  'last_commit': None, 'npm_dependents': None, 'npm_insecure': None, 'health_score': None},
    }
    addon.update(overrides)
    return addon


class TestRecency:
    def test_fresh_release_scores_full_points(self):
        assert HealthScore()._compute_recency_points(_day(10)) == 40

    def test_tiers_step_down_with_age(self):
        scorer = HealthScore()
        assert scorer._compute_recency_points(_day(200)) == 30
        assert scorer._compute_recency_points(_day(500)) == 20
        assert scorer._compute_recency_points(_day(900)) == 10
        assert scorer._compute_recency_points(_day(1500)) == 5
        assert scorer._compute_recency_points(_day(3000)) == 0

    def test_missing_or_malformed_date_scores_zero(self):
        scorer = HealthScore()
        assert scorer._compute_recency_points(None) == 0
        assert scorer._compute_recency_points('not-a-date') == 0


class TestDocumentation:
    def test_description_homepage_repo_and_screenshot_max_out(self):
        addon = _addon(description='x' * 200, homepage='https://plone.org',
                       repo_url='https://github.com/a/b', has_screenshot=True)
        assert HealthScore()._compute_documentation_points(addon) == 30

    def test_without_screenshot_caps_at_25(self):
        addon = _addon(description='x' * 200, homepage='https://plone.org', repo_url='https://github.com/a/b')
        assert HealthScore()._compute_documentation_points(addon) == 25

    def test_short_description_earns_no_description_points(self):
        addon = _addon(description='too short', homepage='https://plone.org', repo_url='https://github.com/a/b')
        assert HealthScore()._compute_documentation_points(addon) == 10

    def test_screenshot_alone_earns_its_points(self):
        addon = _addon(has_screenshot=True)
        assert HealthScore()._compute_documentation_points(addon) == 5

    def test_empty_addon_scores_zero(self):
        assert HealthScore()._compute_documentation_points(_addon()) == 0


class TestMetadata:
    def test_license_keywords_and_compat_max_out(self):
        addon = _addon(license='GPL', keywords=['plone', 'cms', 'addon'], compat={'plone': ['6.0'], 'volto': None})
        assert HealthScore()._compute_metadata_points(addon) == 30

    def test_too_few_keywords_and_no_compat(self):
        addon = _addon(license='GPL', keywords=['plone'], compat={'plone': None, 'volto': None})
        assert HealthScore()._compute_metadata_points(addon) == 10

    def test_volto_compat_counts(self):
        addon = _addon(compat={'plone': None, 'volto': ['17']})
        assert HealthScore()._compute_metadata_points(addon) == 10


class TestGithubBonus:
    def test_stars_tiers(self):
        scorer = HealthScore()
        assert scorer._compute_stars_bonus(2000) == 10
        assert scorer._compute_stars_bonus(600) == 7
        assert scorer._compute_stars_bonus(150) == 5
        assert scorer._compute_stars_bonus(60) == 3
        assert scorer._compute_stars_bonus(20) == 1
        assert scorer._compute_stars_bonus(5) == 0
        assert scorer._compute_stars_bonus(None) == 0

    def test_activity_tiers(self):
        scorer = HealthScore()
        assert scorer._compute_activity_bonus(_day(10)) == 10
        assert scorer._compute_activity_bonus(_day(60)) == 7
        assert scorer._compute_activity_bonus(_day(120)) == 5
        assert scorer._compute_activity_bonus(_day(300)) == 3
        assert scorer._compute_activity_bonus(_day(800)) == 0
        assert scorer._compute_activity_bonus(None) == 0

    def test_issue_ratio_tiers(self):
        scorer = HealthScore()
        assert scorer._compute_issue_bonus(1000, 50) == 10
        assert scorer._compute_issue_bonus(1000, 200) == 7
        assert scorer._compute_issue_bonus(1000, 400) == 5
        assert scorer._compute_issue_bonus(1000, 900) == 3
        assert scorer._compute_issue_bonus(1000, 2000) == 0
        assert scorer._compute_issue_bonus(None, 5) == 0
        assert scorer._compute_issue_bonus(1000, None) == 0


class TestScore:
    def test_absent_stats_means_no_bonus(self):
        addon = _addon(released=_day(10), description='x' * 200, homepage='h', repo_url='r', has_screenshot=True,
                       license='GPL', keywords=['a', 'b', 'c'], compat={'plone': ['6.0'], 'volto': None})
        del addon['stats']
        assert HealthScore().score(addon) == 100

    def test_score_is_capped_at_100(self):
        addon = _addon(released=_day(10), description='x' * 200, homepage='h', repo_url='r', has_screenshot=True,
                       license='GPL', keywords=['a', 'b', 'c'], compat={'plone': ['6.0'], 'volto': None},
                       stats={'github_stars': 5000, 'last_commit': _day(5)})
        assert HealthScore().score(addon) == 100

    def test_empty_addon_scores_zero(self):
        assert HealthScore().score(_addon()) == 0


class TestEnrich:
    def test_sets_health_score_on_every_addon_and_returns_count(self):
        addons = [_addon(), _addon(released=_day(10))]
        count = HealthScore().enrich(addons)

        assert count == 2
        assert addons[0]['stats']['health_score'] == 0
        assert addons[1]['stats']['health_score'] == 40

    def test_creates_stats_when_missing(self):
        addon = _addon()
        del addon['stats']
        HealthScore().enrich([addon])

        assert addon['stats']['health_score'] == 0
