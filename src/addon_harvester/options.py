import os
import tomllib
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from .config import (
    DEFAULT_CLASSIFIERS,
    DEFAULT_NPM_QUERIES,
    DEFAULT_SOURCES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)


@dataclass(frozen=True)
class HarvestOptions:
    """Inputs for a single harvest run."""

    sources: Sequence[str] = DEFAULT_SOURCES
    classifiers: Sequence[str] = DEFAULT_CLASSIFIERS
    npm_queries: Sequence[str] = DEFAULT_NPM_QUERIES
    limit: int = 0
    workers: int = DEFAULT_WORKERS
    timeout: int = DEFAULT_TIMEOUT
    with_downloads: bool = False
    with_github: bool = False


def config_from_file(path: str) -> Dict[str, Tuple[str, ...]]:
    """Search terms maintained in a TOML config file (``harvest.toml``).

    Returns ``classifiers`` (``[pypi] classifiers``) and ``npm_queries`` (``[npm] queries``).
    A missing file or a missing key falls back to the respective default. A malformed file
    or an empty/non-string list raises ``ValueError`` — a hand-maintained config should
    fail loudly instead of silently harvesting defaults.
    """
    data = _read_toml(path)

    return {
        'classifiers': _string_tuple(data, 'pypi', 'classifiers', DEFAULT_CLASSIFIERS, path),
        'npm_queries': _string_tuple(data, 'npm', 'queries', DEFAULT_NPM_QUERIES, path),
    }


def _read_toml(path: str) -> dict:
    if not os.path.isfile(path):
        return {}

    try:
        with open(path, 'rb') as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ValueError('invalid config file %s: %s' % (path, error))


def _string_tuple(data: dict, table: str, key: str,
                  default: Tuple[str, ...], path: str) -> Tuple[str, ...]:
    values = (data.get(table) or {}).get(key)

    if values is None:
        return default

    if (not isinstance(values, list) or not values
            or not all(isinstance(value, str) and value.strip() for value in values)):
        raise ValueError(
            '%s: [%s] %s must be a non-empty list of strings' % (path, table, key))

    return tuple(value.strip() for value in values)
