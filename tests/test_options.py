import pytest

from addon_harvester.config import DEFAULT_CLASSIFIERS, DEFAULT_NPM_QUERIES
from addon_harvester.options import config_from_file


class TestConfigFromFile:
    def test_reads_classifiers_from_pypi_table(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[pypi]\nclassifiers = ["Framework :: Plone", "Framework :: Zope"]\n')

        # do it
        result = config_from_file(str(config))

        # postcondition
        assert result['classifiers'] == ('Framework :: Plone', 'Framework :: Zope')

    def test_reads_npm_queries_from_npm_table(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[npm]\nqueries = ["keywords:volto-addon", "keywords:aurora-addon"]\n')

        # do it
        result = config_from_file(str(config))

        # postcondition
        assert result['npm_queries'] == ('keywords:volto-addon', 'keywords:aurora-addon')

    def test_strips_whitespace_from_values(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[pypi]\nclassifiers = ["  Framework :: Plone  "]\n')

        # do it
        result = config_from_file(str(config))

        # postcondition
        assert result['classifiers'] == ('Framework :: Plone',)

    def test_missing_file_falls_back_to_defaults(self, tmp_path):
        # do it
        result = config_from_file(str(tmp_path / 'missing.toml'))

        # postcondition
        assert result == {'classifiers': DEFAULT_CLASSIFIERS, 'npm_queries': DEFAULT_NPM_QUERIES}

    def test_missing_keys_fall_back_per_key(self, tmp_path):
        # setup: only [pypi] maintained — npm queries stay at their default
        config = tmp_path / 'harvest.toml'
        config.write_text('[pypi]\nclassifiers = ["Framework :: Zope"]\n')

        # do it
        result = config_from_file(str(config))

        # postcondition
        assert result['classifiers'] == ('Framework :: Zope',)
        assert result['npm_queries'] == DEFAULT_NPM_QUERIES

    def test_empty_list_raises(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[pypi]\nclassifiers = []\n')

        # do it / postcondition
        with pytest.raises(ValueError, match=r'\[pypi\] classifiers must be a non-empty list'):
            config_from_file(str(config))

    def test_non_string_values_raise(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[npm]\nqueries = ["keywords:volto", 42]\n')

        # do it / postcondition
        with pytest.raises(ValueError, match=r'\[npm\] queries must be a non-empty list'):
            config_from_file(str(config))

    def test_malformed_toml_raises_value_error(self, tmp_path):
        # setup
        config = tmp_path / 'harvest.toml'
        config.write_text('[pypi\nclassifiers = oops')

        # do it / postcondition
        with pytest.raises(ValueError, match='invalid config file'):
            config_from_file(str(config))
