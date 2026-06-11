from typing import List, Optional, TypedDict


class TCompat(TypedDict):
    plone: Optional[List[str]]
    volto: Optional[List[str]]
    python: Optional[List[str]]


class TDownloads(TypedDict):
    day: Optional[int]
    week: Optional[int]
    month: Optional[int]


class TStats(TypedDict):
    downloads_day: Optional[int]
    downloads_week: Optional[int]
    downloads_month: Optional[int]
    github_stars: Optional[int]
    github_watchers: Optional[int]
    github_open_issues: Optional[int]
    last_commit: Optional[str]
    npm_dependents: Optional[int]
    npm_insecure: Optional[bool]
    health_score: Optional[int]


class TAddon(TypedDict):
    id: str
    kind: str
    source: str
    name: str
    title: str
    summary: str
    description: str
    categories: List[str]
    keywords: List[str]
    latest_version: str
    version_sortable: Optional[str]
    prerelease: Optional[bool]
    released: Optional[str]
    license: Optional[str]
    repo_url: Optional[str]
    homepage: Optional[str]
    has_screenshot: bool
    compat: TCompat
    installable_profile: Optional[bool]
    stats: TStats
    pairs_with: List[str]
    trust: str


class TSnapshot(TypedDict):
    generated: str
    schema_version: int
    source: str
    addons: List[TAddon]
