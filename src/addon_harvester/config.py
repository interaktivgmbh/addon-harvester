from typing import Dict, Tuple

USER_AGENT = 'addon-harvester (+https://github.com/interaktivgmbh/addon-harvester)'

PYPI_XMLRPC_URL = 'https://pypi.org/pypi'
PYPI_JSON_URL = 'https://pypi.org/pypi/{name}/json'
PYPI_SIMPLE_URL = 'https://pypi.org/simple/'
PYPI_SIMPLE_ACCEPT = 'application/vnd.pypi.simple.v1+json'
PYPISTATS_RECENT_URL = 'https://pypistats.org/api/packages/{name}/recent'

DEFAULT_CLASSIFIERS: Tuple[str, ...] = ('Framework :: Plone',)
DEFAULT_CONFIG_FILE = 'harvest.toml'

BIGQUERY_QUERY_URL = 'https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries'
BIGQUERY_RESULTS_URL = 'https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries/{job_id}'
BIGQUERY_CLASSIFIER_QUERY = (
    'SELECT DISTINCT name FROM `bigquery-public-data.pypi.distribution_metadata` '
    'WHERE @classifier IN UNNEST(classifiers)'
)
BIGQUERY_PROJECT_ENV = ('BIGQUERY_PROJECT', 'GOOGLE_CLOUD_PROJECT')
BIGQUERY_TOKEN_ENV = ('BIGQUERY_TOKEN', 'GOOGLE_OAUTH_ACCESS_TOKEN')
BIGQUERY_GCLOUD_TOKEN_COMMAND = ('gcloud', 'auth', 'print-access-token')
BIGQUERY_PAGE_SIZE = 10000
BIGQUERY_MAX_PAGES = 100

NPM_SEARCH_URL = 'https://registry.npmjs.org/-/v1/search'
NPM_PACKUMENT_URL = 'https://registry.npmjs.org/{name}'
NPM_SEARCH_PAGE_SIZE = 250
NPM_SEARCH_MAX = 2000

DEFAULT_NPM_QUERIES = (
    'keywords:volto-addon',
    'keywords:volto',
    'keywords:aurora-addon',
    'keywords:plone-aurora',
    'keywords:nick-addon',
    'keywords:nick',
)

NPM_VOLTO_PEER = '@plone/volto'
NPM_AURORA_PEER = '@plone/aurora'
NPM_NICK_PEER = '@plone/nick'
NPM_ADDON_PEERS = (NPM_VOLTO_PEER, NPM_AURORA_PEER)
NPM_ADDON_KEYWORDS = ('volto', 'volto-addon', 'aurora-addon', 'plone-aurora', 'plone')

NPM_NICK_KEYWORD = 'nick-addon'
NPM_NICK_KEYWORD_PAIR = ('nick', 'cms')
NPM_NICK_NAME_PREFIX = '@plone/nick'
NICK_CATEGORY = 'nick'

GITHUB_GRAPHQL_URL = 'https://api.github.com/graphql'
GITHUB_TOKEN_ENV = ('GITHUB_TOKEN', 'GH_TOKEN')
GITHUB_BATCH_SIZE = 50

SCHEMA_VERSION = 3
DEFAULT_SOURCES = ('pypi', 'npm')
DEFAULT_TRUST = 'community'
DEFAULT_OUTPUT = 'index.json'

DEFAULT_WORKERS = 8
DEFAULT_TIMEOUT = 30
HTTP_RETRIES = 3
HTTP_BACKOFF_SECONDS = 2.0

MAX_DESCRIPTION_CHARS = 2000

PLONE_TYPE_CATEGORIES: Dict[str, str] = {
    'Addon': 'addon',
    'Theme': 'theme',
    'Core': 'core',
    'Distribution': 'distribution',
}

LICENSE_CLASSIFIER_MAP: Dict[str, str] = {
    'License :: OSI Approved :: GNU General Public License v2 (GPLv2)': 'GPL-2.0',
    'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)': 'GPL-2.0-or-later',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)': 'GPL-3.0',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)': 'GPL-3.0-or-later',
    'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)': 'LGPL-2.0-or-later',
    'License :: OSI Approved :: GNU Lesser General Public License v2.1 (LGPLv2.1)': 'LGPL-2.1',
    'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)': 'LGPL-3.0',
    'License :: OSI Approved :: MIT License': 'MIT',
    'License :: OSI Approved :: BSD License': 'BSD-3-Clause',
    'License :: OSI Approved :: Apache Software License': 'Apache-2.0',
    'License :: OSI Approved :: Zope Public License': 'ZPL-2.1',
    'License :: OSI Approved :: Python Software Foundation License': 'PSF-2.0',
}

REPO_URL_KEYS: Tuple[str, ...] = (
    'source',
    'source code',
    'repository',
    'code',
    'github',
    'git',
)

VCS_HOSTS: Tuple[str, ...] = ('github.com', 'gitlab.com', 'bitbucket.org', 'codeberg.org')
