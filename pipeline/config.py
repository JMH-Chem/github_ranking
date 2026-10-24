"""Settings shared by the pipeline scripts."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
WORK_DIR = Path(os.environ.get("WORK_DIR", ROOT / "work"))

TRENDING_URL = "https://github.com/trending"
USER_AGENT = "github_ranking-bot (+https://github.com/JMH-Chem/github_ranking)"

# Language tabs on the trending page scanned for rising-repo candidates.
# Values are the URL slugs GitHub uses (c# is "c%23").
LANGUAGE_TABS = [
    "python", "typescript", "javascript", "rust", "go", "java", "c++", "c",
    "swift", "kotlin", "c%23", "ruby", "php", "dart", "shell", "zig",
]

# Seconds to wait between trending page requests.
REQUEST_DELAY = 2.0

# Korean summaries
SUMMARY_LIMIT_PER_RUN = 60   # ranked repos first, then rising shortlist
CHUNK_SIZE = 8               # repos per Claude Code run
README_MAX_CHARS = 20_000
KO_REFRESH_DAYS = 28         # regenerate only if README changed and summary is older

# Rising repos
RISING_PER_CATEGORY = 5
SHORTLIST_PER_CATEGORY = 8   # candidates per category sent for summaries
RECOMMEND_COOLDOWN_WEEKS = 4 # don't recommend the same repo again within N weeks
CANDIDATE_ENRICH_LIMIT = 120 # trending-tab candidates looked up via the API
MIN_CANDIDATE_STARS = 50
MIN_STARS_WEEK = 100        # weekly gain (real or estimated) needed to be recommended
ESTABLISHED_DAYS = 365      # repos older than this need real momentum to count as rising:
ESTABLISHED_MIN_RATIO = 0.05  # weekly gain / total stars
# Never recommend repos whose name, description or topics contain these words.
BLOCKED_KEYWORDS = ["jailbreak", "jailbreaks", "keygen", "cracked", "piracy", "warez"]
# Hand-maintained list of repos to leave out (owner/name or owner/*).
BLOCKLIST_FILE = ROOT / "pipeline" / "blocklist.txt"
NEW_REPO_DAYS = 30           # "new repo" search window
CATEGORY_SEARCH_DAYS = 90    # per-category search window

# Fixed category list, shared with the website. `keywords` drive the cheap
# heuristic used before a Korean summary exists; once Claude has summarized a
# repo its own `category` wins.
with (Path(__file__).parent / "categories.json").open(encoding="utf-8") as _f:
    CATEGORIES = json.load(_f)

CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
