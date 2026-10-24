"""Fetch and parse https://github.com/trending.

GitHub has no API for trending, so this parses the HTML. Each repo is an
`article.Box-row`; see tests/fixtures/trending_weekly.html for a captured
sample.

    python -m pipeline.trending                 # print weekly, all languages
    python -m pipeline.trending --language rust --since daily
    python -m pipeline.trending --check 10      # fail unless >=10 rows parse
"""

import argparse
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

from . import config

PERIOD_RE = re.compile(r"([\d,]+)\s+stars?\s+(today|this week|this month)", re.I)


def trending_url(language: str | None = None, since: str = "weekly") -> str:
    path = f"/{language}" if language else ""
    return f"{config.TRENDING_URL}{path}?since={since}"


def fetch_trending(session: requests.Session, language: str | None = None,
                   since: str = "weekly") -> str:
    resp = session.get(trending_url(language, since), timeout=30)
    resp.raise_for_status()
    return resp.text


def _int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_trending(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for article in soup.select("article.Box-row"):
        link = article.select_one("h2 a[href]")
        if link is None:
            continue
        repo = link["href"].strip("/")
        if repo.count("/") != 1:
            continue

        desc_el = article.select_one("p")
        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        stars_el = article.select_one('a[href$="/stargazers"]')
        forks_el = (article.select_one('a[href$="/forks"]')
                    or article.select_one('a[href$="/network/members"]'))

        period = PERIOD_RE.search(article.get_text(" ", strip=True))

        entries.append({
            "rank": len(entries) + 1,
            "repo": repo,
            "description": desc_el.get_text(" ", strip=True) if desc_el else None,
            "language": lang_el.get_text(strip=True) if lang_el else None,
            "stars_total": _int(stars_el.get_text() if stars_el else None),
            "forks": _int(forks_el.get_text() if forks_el else None),
            "stars_period": _int(period.group(1)) if period else None,
        })
    return entries


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = config.USER_AGENT
    s.headers["Accept-Language"] = "en-US,en;q=0.9"
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--language")
    ap.add_argument("--since", default="weekly", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--check", type=int, metavar="N",
                    help="exit 1 unless at least N complete rows were parsed")
    args = ap.parse_args()

    entries = parse_trending(fetch_trending(new_session(), args.language, args.since))
    print(json.dumps(entries, ensure_ascii=False, indent=2))

    if args.check is not None:
        complete = [e for e in entries
                    if e["stars_total"] is not None and e["stars_period"] is not None]
        if len(complete) < args.check:
            print(f"parsed {len(complete)} complete rows, expected >= {args.check}",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
