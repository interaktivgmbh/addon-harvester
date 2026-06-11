"""Command-line runner for the addon-harvester library.

The package itself is a library (build ``HarvestOptions``, call ``Harvester(...).run()``).
This script wires those pieces to argument parsing, logging and the JSON writer so the
harvester can be run from a shell:

    python main.py --limit 20 --output index.json
    python main.py --sources pypi --with-downloads --with-github -v

Every run also writes its full log (progress, summary, errors, timings) to a timestamped
file under ``var/log/`` — regardless of ``-v``, which only controls console verbosity.
"""
import argparse
import glob
import logging
import os
import sys
import time
from typing import Optional

from addon_harvester import (
    Harvester,
    HarvestOptions,
    config_from_file,
    logger,
    write_snapshot,
)
from addon_harvester.config import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_OUTPUT,
    DEFAULT_SOURCES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_DIR = os.path.join(BASE_DIR, 'var', 'log')
LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
KEEP_RUN_LOGS = 20


def load_dotenv(path: str) -> None:
    """Load ``KEY=value`` lines from a .env file into ``os.environ`` (existing keys win)."""
    if not os.path.isfile(path):
        return

    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()

            if not line or line.startswith('#') or '=' not in line:
                continue

            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key:
                os.environ.setdefault(key, value)


def setup_logging(verbose: bool, log_dir: Optional[str]) -> Optional[str]:
    """Console logging per ``verbose`` plus, unless disabled, a full INFO run log file.

    Returns the run-log path (``None`` when file logging is disabled).
    """
    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO if verbose else logging.WARNING)
    console.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)

    if log_dir is None:
        return None

    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, 'harvest-%s.log' % time.strftime('%Y%m%d-%H%M%S'))

    file_handler = logging.FileHandler(path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    prune_run_logs(log_dir)
    return path


def prune_run_logs(log_dir: str) -> None:
    """Keep only the newest ``KEEP_RUN_LOGS`` run logs (timestamped names sort by age)."""
    run_logs = sorted(glob.glob(os.path.join(log_dir, 'harvest-*.log')))

    for stale in run_logs[:-KEEP_RUN_LOGS]:
        try:
            os.remove(stale)
        except OSError:
            pass


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='addon-harvester',
        description='Harvest add-on metadata from PyPI and npm into a JSON snapshot.',
    )
    parser.add_argument(
        '--sources', default=','.join(DEFAULT_SOURCES),
        help='comma-separated registries to harvest (default: %(default)s)')
    parser.add_argument(
        '--config', default=os.path.join(BASE_DIR, DEFAULT_CONFIG_FILE),
        help='TOML config file with the search terms — PyPI classifiers and npm '
             'queries (default: %(default)s)')
    parser.add_argument(
        '--classifier', action='append', dest='classifiers', metavar='CLASSIFIER',
        help='PyPI trove classifier to filter on; repeatable, overrides the config file')
    parser.add_argument(
        '--limit', type=int, default=0,
        help='cap packages per source (0 = no limit, default: %(default)s)')
    parser.add_argument(
        '--workers', type=int, default=DEFAULT_WORKERS,
        help='concurrent metadata fetches (default: %(default)s)')
    parser.add_argument(
        '--timeout', type=int, default=DEFAULT_TIMEOUT,
        help='per-request timeout in seconds (default: %(default)s)')
    parser.add_argument(
        '--with-downloads', action='store_true',
        help='enrich with monthly download counts (extra requests)')
    parser.add_argument(
        '--with-github', action='store_true',
        help='enrich with GitHub stars/last-commit (needs GITHUB_TOKEN/GH_TOKEN)')
    parser.add_argument(
        '-o', '--output', default=DEFAULT_OUTPUT,
        help='snapshot output path (default: %(default)s)')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='log progress to stderr')
    parser.add_argument(
        '--log-dir', default=DEFAULT_LOG_DIR,
        help='directory for per-run log files (default: %(default)s)')
    parser.add_argument(
        '--no-log-file', action='store_true',
        help='do not write a per-run log file')

    return parser.parse_args(argv)


def main(argv: list) -> int:
    args = parse_args(argv)

    # OS environment takes precedence; .env fills in anything not already set
    load_dotenv(os.path.join(BASE_DIR, '.env'))

    log_path = setup_logging(args.verbose, None if args.no_log_file else args.log_dir)
    if log_path:
        logger.info('run log: %s', log_path)

    try:
        config = config_from_file(args.config)
    except ValueError as error:
        logger.error('%s', error)
        return 2

    options = HarvestOptions(
        sources=tuple(s.strip() for s in args.sources.split(',') if s.strip()),
        classifiers=tuple(args.classifiers) if args.classifiers else config['classifiers'],
        npm_queries=config['npm_queries'],
        limit=args.limit,
        workers=args.workers,
        timeout=args.timeout,
        with_downloads=args.with_downloads,
        with_github=args.with_github,
    )

    start = time.monotonic()
    try:
        snapshot = Harvester(options).run()
    except ValueError as error:
        logger.error('%s', error)
        return 2
    elapsed = time.monotonic() - start

    write_snapshot(snapshot, args.output)
    logger.info('wrote %d addons to %s', len(snapshot['addons']), args.output)
    print('%d addons -> %s (harvested in %.1fs)' % (len(snapshot['addons']), args.output, elapsed))
    if log_path:
        print('run log -> %s' % log_path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
