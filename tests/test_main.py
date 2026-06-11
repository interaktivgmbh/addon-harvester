import os
from unittest.mock import patch

import main


class TestLoadDotenv:
    def test_loads_values_and_skips_comments_and_garbage(self, tmp_path):
        # setup
        env_file = tmp_path / '.env'
        env_file.write_text('# comment\n\nFOO=bar\nQUOTED="with spaces"\nnoequals\n', encoding='utf-8')

        # do it
        with patch.dict(os.environ, {}, clear=True):
            main.load_dotenv(str(env_file))

            # postcondition
            assert os.environ['FOO'] == 'bar'
            assert os.environ['QUOTED'] == 'with spaces'

    def test_existing_environment_wins(self, tmp_path):
        # setup
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=from-file\n', encoding='utf-8')

        # do it
        with patch.dict(os.environ, {'FOO': 'from-env'}, clear=True):
            main.load_dotenv(str(env_file))

            # postcondition
            assert os.environ['FOO'] == 'from-env'

    def test_missing_file_is_a_no_op(self, tmp_path):
        # do it (must not raise)
        main.load_dotenv(str(tmp_path / 'absent.env'))


class TestPruneRunLogs:
    def test_keeps_only_the_newest_run_logs(self, tmp_path):
        # setup: timestamped names sort chronologically
        for index in range(main.KEEP_RUN_LOGS + 3):
            (tmp_path / ('harvest-202606%02d.log' % index)).write_text('x')
        (tmp_path / 'unrelated.txt').write_text('keep me')

        # do it
        main.prune_run_logs(str(tmp_path))

        # postcondition: oldest three removed, unrelated file untouched
        remaining = sorted(p.name for p in tmp_path.iterdir())
        assert len([name for name in remaining if name.startswith('harvest-')]) == main.KEEP_RUN_LOGS
        assert 'harvest-20260600.log' not in remaining
        assert 'unrelated.txt' in remaining


class TestParseArgs:
    def test_classifier_is_repeatable(self):
        # do it
        args = main.parse_args(['--classifier', 'Framework :: Plone', '--classifier', 'Framework :: Zope'])

        # postcondition
        assert args.classifiers == ['Framework :: Plone', 'Framework :: Zope']

    def test_defaults(self):
        # do it
        args = main.parse_args([])

        # postcondition
        assert args.classifiers is None
        assert args.config.endswith('harvest.toml')
        assert not args.no_log_file
