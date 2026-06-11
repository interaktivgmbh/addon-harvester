import json
import os

from addon_harvester.snapshot import write_snapshot


class TestWriteSnapshot:
    def test_writes_pretty_json_and_cleans_up_the_tmp_file(self, tmp_path):
        # setup
        target = tmp_path / 'out' / 'index.json'
        snapshot = {'generated': '2026-06-11T00:00:00Z', 'addons': [{'id': 'pypi:ä'}]}

        # do it
        write_snapshot(snapshot, str(target))

        # postcondition
        content = target.read_text(encoding='utf-8')
        assert json.loads(content) == snapshot
        assert 'pypi:ä' in content  # ensure_ascii=False
        assert content.endswith('\n')
        assert not os.path.exists(str(target) + '.tmp')

    def test_replaces_an_existing_file(self, tmp_path):
        # setup
        target = tmp_path / 'index.json'
        target.write_text('{"old": true}', encoding='utf-8')

        # do it
        write_snapshot({'new': True}, str(target))

        # postcondition
        assert json.loads(target.read_text(encoding='utf-8')) == {'new': True}
