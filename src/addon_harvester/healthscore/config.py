from typing import Tuple

Bucket = Tuple[float, int]
Buckets = Tuple[Bucket, ...]

# Release recency: fresher scores higher. (max_age_days, points), ascending by age.
RECENCY_BUCKETS: Buckets = ((180, 40), (365, 30), (730, 20), (1095, 10), (1825, 5))

# GitHub commit activity: more recent scores higher. (max_age_days, points), ascending by age.
ACTIVITY_BUCKETS: Buckets = ((30, 10), (90, 7), (180, 5), (365, 3))

# GitHub popularity: more stars score higher. (min_stars, points), descending by stars.
STARS_BUCKETS: Buckets = ((1000, 10), (500, 7), (100, 5), (50, 3), (10, 1))

# GitHub maintenance: a lower open-issue-to-star ratio scores higher. (max_ratio, points), ascending.
ISSUE_RATIO_BUCKETS: Buckets = ((0.1, 10), (0.25, 7), (0.5, 5), (1.0, 3))

# Documentation sub-weights (sum == MAX_DOCUMENTATION_POINTS).
DESCRIPTION_POINTS = 15
HOMEPAGE_POINTS = 5
REPO_POINTS = 5
SCREENSHOT_POINTS = 5

# Metadata sub-weights (sum == MAX_METADATA_POINTS).
LICENSE_POINTS = 10
KEYWORDS_POINTS = 10
COMPAT_POINTS = 10

MIN_DESCRIPTION_CHARS = 150
MIN_KEYWORDS = 3

# Category maxima, derived from the rubric above so they can never drift out of sync.
MAX_RECENCY_POINTS = RECENCY_BUCKETS[0][1]
MAX_DOCUMENTATION_POINTS = DESCRIPTION_POINTS + HOMEPAGE_POINTS + REPO_POINTS + SCREENSHOT_POINTS
MAX_METADATA_POINTS = LICENSE_POINTS + KEYWORDS_POINTS + COMPAT_POINTS
MAX_GITHUB_BONUS = STARS_BUCKETS[0][1] + ACTIVITY_BUCKETS[0][1] + ISSUE_RATIO_BUCKETS[0][1]

MAX_SCORE = 100
