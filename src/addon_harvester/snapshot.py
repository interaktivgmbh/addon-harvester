import json
import os

from .types import TSnapshot


def write_snapshot(snapshot: TSnapshot, output: str) -> None:
    """Atomically write ``snapshot`` to ``output`` as pretty-printed UTF-8 JSON."""
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    tmp = '%s.tmp' % output

    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write('\n')
    os.replace(tmp, output)
