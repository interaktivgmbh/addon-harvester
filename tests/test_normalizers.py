from addon_harvester.normalizers.npm import NpmNormalizer
from addon_harvester.normalizers.pypi import PyPINormalizer


def _doc(*classifiers):
    return {'info': {'classifiers': list(classifiers)}}


class TestHasClassifier:
    def test_matches_exact_classifier(self):
        # setup
        document = _doc('Framework :: Plone')

        # do it
        result = PyPINormalizer.has_classifier(document, 'Framework :: Plone')

        # postcondition
        assert result

    def test_matches_classifier_as_prefix(self):
        # setup
        document = _doc('Framework :: Plone :: 6.2')

        # do it
        result = PyPINormalizer.has_classifier(document, 'Framework :: Plone')

        # postcondition
        assert result

    def test_does_not_match_unrelated_framework(self):
        # setup
        document = _doc('Framework :: Django')

        # do it
        result = PyPINormalizer.has_classifier(document, 'Framework :: Plone')

        # postcondition
        assert not result

    def test_missing_classifiers_is_false(self):
        # do it
        result = PyPINormalizer.has_classifier({}, 'Framework :: Plone')

        # postcondition
        assert not result


class TestIsFrontendAddon:
    def test_name_contains_volto(self):
        # setup
        packument = {'name': '@scope/volto-thing'}

        # do it
        result = NpmNormalizer.is_frontend_addon(packument)

        # postcondition
        assert result

    def test_aurora_addon_keyword_is_kept(self):
        # setup
        packument = {'name': 'collective-foo', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['aurora-addon']}}}

        # do it
        result = NpmNormalizer.is_frontend_addon(packument)

        # postcondition
        assert result

    def test_aurora_peer_dependency_is_kept(self):
        # setup
        packument = {'name': 'collective-bar', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'peerDependencies': {'@plone/aurora': '^1.0.0'}}}}

        # do it
        result = NpmNormalizer.is_frontend_addon(packument)

        # postcondition
        assert result

    def test_plain_aurora_package_is_dropped(self):
        # setup
        packument = {'name': 'aws-aurora-helper', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['aurora', 'aws', 'database']}}}

        # do it
        result = NpmNormalizer.is_frontend_addon(packument)

        # postcondition
        assert not result

    def test_plain_package_is_dropped(self):
        # setup
        packument = {'name': 'left-pad', 'dist-tags': {'latest': '1.0.0'}, 'versions': {'1.0.0': {}}}

        # do it
        result = NpmNormalizer.is_frontend_addon(packument)

        # postcondition
        assert not result


class TestEcosystems:
    def test_plone_nick_name_prefix_is_nick(self):
        # setup
        packument = {'name': '@plone/nick-blog', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['nick']
        assert NpmNormalizer.is_frontend_addon(packument)

    def test_nick_addon_keyword_is_nick(self):
        # setup
        packument = {'name': 'community-nick-thing', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['nick-addon']}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['nick']

    def test_nick_plus_cms_keywords_are_nick(self):
        # setup
        packument = {'name': 'some-blog', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['nick', 'blog', 'cms']}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['nick']

    def test_nick_peer_dependency_is_nick(self):
        # setup
        packument = {'name': 'some-extension', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'peerDependencies': {'@plone/nick': '^1.0.0'}}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['nick']

    def test_irc_nick_package_matches_nothing(self):
        # setup
        packument = {'name': 'nickserv', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['irc', 'nickserv', 'nick']}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == []
        assert not NpmNormalizer.is_frontend_addon(packument)

    def test_volto_addon_is_volto(self):
        # setup
        packument = {'name': 'collective-foo', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['volto']

    def test_aurora_peer_is_aurora(self):
        # setup
        packument = {'name': 'collective-bar', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'peerDependencies': {'@plone/aurora': '^1.0.0'}}}}

        # do it / postcondition
        assert NpmNormalizer.ecosystems(packument) == ['aurora']

    def test_normalize_uses_ecosystems_as_categories(self):
        # setup
        packument = {'name': '@plone/nick-blog', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'description': 'Blog for Nick', 'keywords': ['nick', 'cms']}},
                     'time': {'1.0.0': '2026-01-01T00:00:00Z'}}

        # do it
        addon = NpmNormalizer().normalize(packument)

        # postcondition
        assert addon['categories'] == ['nick']

    def test_normalize_tags_volto_addons_with_volto(self):
        # setup
        packument = {'name': '@scope/volto-thing', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}},
                     'time': {'1.0.0': '2026-01-01T00:00:00Z'}}

        # do it
        addon = NpmNormalizer().normalize(packument)

        # postcondition
        assert addon['categories'] == ['volto']


class TestPyPINormalize:
    def test_maps_core_fields_and_plone_versions(self):
        # setup
        document = {
            'info': {
                'name': 'collective.easyform',
                'version': '4.1',
                'summary': 'Forms for Plone',
                'classifiers': ['Framework :: Plone :: 6.0', 'Framework :: Plone :: Addon'],
                'project_urls': {'Source': 'https://github.com/collective/collective.easyform'},
            },
            'urls': [{'upload_time_iso_8601': '2024-03-01T12:00:00Z'}],
        }

        # do it
        addon = PyPINormalizer().normalize(document, downloads={'day': 4, 'week': 30, 'month': 123})

        # postcondition
        assert addon['id'] == 'pypi:collective.easyform'
        assert addon['kind'] == 'backend'
        assert addon['compat']['plone'] == ['6.0']
        assert addon['categories'] == ['addon']
        assert addon['repo_url'] == 'https://github.com/collective/collective.easyform'
        assert addon['released'] == '2024-03-01'
        assert addon['stats']['downloads_day'] == 4
        assert addon['stats']['downloads_week'] == 30
        assert addon['stats']['downloads_month'] == 123
        assert addon['stats']['npm_dependents'] is None
        assert addon['stats']['npm_insecure'] is None
        assert addon['version_sortable'] == '00004.00001.9'
        assert addon['prerelease'] is False
        assert addon['has_screenshot'] is False
        assert addon['compat']['python'] is None

    def test_extracts_python_versions_from_classifiers(self):
        # setup
        document = {'info': {'name': 'collective.thing', 'version': '1.0', 'classifiers': [
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.12',
            'Programming Language :: Python :: 3.11',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: Implementation :: CPython',
        ]}, 'urls': []}

        # do it
        addon = PyPINormalizer().normalize(document)

        # postcondition
        assert addon['compat']['python'] == ['3', '3.11', '3.12']

    def test_detects_screenshot_in_description(self):
        # setup — a real image plus a shields.io badge; only the real image counts
        readme = ('[![Build](https://img.shields.io/x.svg)](https://ci.test)\n\n'
                  '![Screenshot](https://raw.githubusercontent.com/x/y/main/docs/screen.png)\n')
        document = {'info': {'name': 'collective.thing', 'version': '1.0',
                             'classifiers': [], 'description': readme}, 'urls': []}

        # do it
        addon = PyPINormalizer().normalize(document)

        # postcondition
        assert addon['has_screenshot'] is True

    def test_badge_only_description_is_not_a_screenshot(self):
        # setup
        readme = '[![Coverage](https://coveralls.io/repos/x/badge.svg)](https://coveralls.io/x)\n'
        document = {'info': {'name': 'collective.thing', 'version': '1.0',
                             'classifiers': [], 'description': readme}, 'urls': []}

        # do it
        addon = PyPINormalizer().normalize(document)

        # postcondition
        assert addon['has_screenshot'] is False

    def test_description_is_stripped_of_markdown(self):
        # setup
        readme = (
            '# Easyform\n\n'
            '[![Build](https://img.shields.io/x.svg)](https://ci.test/x)\n\n'
            '**Easyform** is a *form* builder. See the [docs](https://plone.org).\n\n'
            '## Features\n\n'
            '- drag-and-drop\n'
            '```python\nx = 1\n```\n'
        )
        document = {'info': {'name': 'collective.easyform', 'version': '1.0',
                             'classifiers': [], 'description': readme}, 'urls': []}

        # do it
        description = PyPINormalizer().normalize(document)['description']

        # postcondition
        assert description == (
            'Easyform\n\n'
            'Easyform is a form builder. See the docs.\n\n'
            'Features\n\n'
            'drag-and-drop'
        )


class TestNpmNormalize:
    def test_maps_core_fields_and_volto_versions(self):
        # setup
        packument = {
            'name': '@plone/volto-form-block',
            'dist-tags': {'latest': '2.0.0'},
            'versions': {'2.0.0': {
                'description': 'Form block',
                'keywords': ['volto-addon'],
                'peerDependencies': {'@plone/volto': '>=17.0.0 || >=18.0.0'},
                'repository': {'url': 'git+https://github.com/plone/volto-form-block.git'},
            }},
            'time': {'2.0.0': '2024-05-02T08:00:00Z'},
        }

        # do it
        addon = NpmNormalizer().normalize(packument)

        # postcondition
        assert addon['id'] == 'npm:@plone/volto-form-block'
        assert addon['kind'] == 'frontend'
        assert addon['compat']['volto'] == ['17', '18']
        assert addon['compat']['python'] is None
        assert addon['repo_url'] == 'https://github.com/plone/volto-form-block'
        assert addon['released'] == '2024-05-02'
        assert addon['version_sortable'] == '00002.00000.00000.9'
        assert addon['prerelease'] is False

    def test_maps_search_metrics(self):
        # setup
        packument = {'name': '@plone/volto-thing', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}}, 'time': {}}
        downloads = {'day': None, 'week': 1351, 'month': 5523}

        # do it
        addon = NpmNormalizer().normalize(packument, downloads=downloads, dependents=8, insecure=False)

        # postcondition
        assert addon['stats']['downloads_week'] == 1351
        assert addon['stats']['downloads_month'] == 5523
        assert addon['stats']['npm_dependents'] == 8
        assert addon['stats']['npm_insecure'] is False

    def test_missing_metrics_are_none(self):
        # setup
        packument = {'name': '@plone/volto-thing', 'dist-tags': {'latest': '1.0.0'},
                     'versions': {'1.0.0': {'keywords': ['volto-addon']}}, 'time': {}}

        # do it
        addon = NpmNormalizer().normalize(packument)

        # postcondition
        assert addon['stats']['npm_dependents'] is None
        assert addon['stats']['npm_insecure'] is None


class TestVersionInfo:
    def test_stable_release_sorts_above_prereleases(self):
        # do it
        stable, stable_pre = PyPINormalizer._version_info('1.2.3')
        rc, rc_pre = PyPINormalizer._version_info('1.2.3rc1')
        # postcondition
        assert stable == '00001.00002.00003.9'
        assert stable_pre is False
        assert rc == '00001.00002.00003.0'
        assert rc_pre is True
        assert rc < stable  # ascending string sort keeps the pre-release below its final release

    def test_detects_prerelease_markers(self):
        # do it / postcondition
        assert PyPINormalizer._version_info('2.0.0-beta.1')[1] is True
        assert PyPINormalizer._version_info('1.0.0.dev3')[1] is True
        assert PyPINormalizer._version_info('1.0a1')[1] is True
        assert PyPINormalizer._version_info('1.0.0')[1] is False
        assert PyPINormalizer._version_info('1.0.0.post1')[1] is False  # post-release is not a pre-release

    def test_strips_v_prefix_and_handles_unparseable(self):
        # do it / postcondition
        assert PyPINormalizer._version_info('v3.4')[0] == '00003.00004.9'
        assert PyPINormalizer._version_info('')[0] is None
        assert PyPINormalizer._version_info('not-a-version') == (None, None)
