"""Rising repos: gather candidates, score them, and pick 5 per category.

Candidates come from the weekly trending tabs of individual languages (which
give a real "stars this week" number) and from GitHub search for young repos
(where weekly stars are estimated from the average daily rate). Repos that
are on the main weekly ranking, or were recently ranked or recommended, are
left out so this page shows something different.

    python -m pipeline.rising --week 2026-W43     # write data/rising/<week>.json
"""

import argparse
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

from . import config, store
from .github_api import GitHub, age_days, repo_meta
from .trending import fetch_trending, parse_trending

AWESOME_RE = re.compile(r"(^|[-_])awesome([-_]|$)|curated list|awesome list", re.I)

META_KEYS = ("repo", "url", "description", "homepage", "language", "topics", "license",
             "stars", "forks", "open_issues", "created_at", "pushed_at", "archived",
             "is_fork", "owner_avatar")


# --- heuristics ------------------------------------------------------------

def guess_category(meta: dict) -> str:
    """Cheap keyword match used until Claude assigns a category."""
    topics = " ".join(meta.get("topics") or []).lower()
    text = " ".join([meta["repo"].split("/")[-1], meta.get("description") or ""]).lower()
    best, best_hits = "etc", 0
    for cat in config.CATEGORIES:
        hits = 0
        for kw in cat["keywords"]:
            pat = rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])"
            hits += 2 * len(re.findall(pat, topics)) + len(re.findall(pat, text))
        if hits > best_hits:
            best, best_hits = cat["key"], hits
    return best


def estimate_weekly(stars: int, age: int | None) -> int:
    """Average stars per week since creation, for repos without trending data."""
    if not age or age <= 7:
        return stars
    return round(stars * 7 / age)


def score(c: dict) -> float:
    stars_week = c["stars_week"] or 0
    ratio = min(stars_week / max(c["stars"] or 1, 1), 1.0)
    age = c["age_days"]
    if age is None:
        age_factor = 1.0
    elif age <= 30:
        age_factor = 1.5
    elif age <= 90:
        age_factor = 1.25
    elif age <= 365:
        age_factor = 1.0
    else:
        age_factor = 0.75
    estimated = 0.85 if c["stars_week_estimated"] else 1.0
    return round(math.log10(1 + stars_week) * (1 + 1.5 * ratio) * age_factor * estimated, 4)


def exclusion_reason(c: dict, blocked: set[str]) -> str | None:
    if c["repo"] in blocked:
        return "recent"
    if c.get("archived"):
        return "archived"
    if c.get("is_fork"):
        return "fork"
    if (c.get("stars") or 0) < config.MIN_CANDIDATE_STARS:
        return "few-stars"
    if AWESOME_RE.search(c["repo"].split("/")[-1]) or AWESOME_RE.search(c.get("description") or ""):
        return "list"
    if (c.get("forks") or 0) == 0 and (c.get("stars") or 0) >= 300:
        return "suspicious"
    return None


def blocked_repos(week: str) -> set[str]:
    """Repos ranked this week or recently, or recommended recently."""
    n = config.RECOMMEND_COOLDOWN_WEEKS
    blocked = set()
    weeks = [w for w in store.list_weeks() if w <= week][-n:]
    for w in weeks:
        blocked.update(e["repo"] for e in store.load_week(w)["entries"])
    for w in [w for w in store.list_rising() if w < week][-n:]:
        doc = store.read_json(store.rising_path(w), {})
        for cat in doc.get("categories", []):
            blocked.update(r["repo"] for r in cat["repos"])
    return blocked


# --- gathering -------------------------------------------------------------

def _prelim(c: dict) -> float:
    return math.log10(1 + c["stars_week"]) * (1 + c["stars_week"] / max(c["stars_total"] or 1, 1))


def gather_candidates(session: requests.Session, gh: GitHub, week: str,
                      now: datetime) -> dict:
    """Collect, enrich, filter and score candidates. Returns the snapshot doc."""
    blocked = blocked_repos(week)

    tab_hits: dict[str, dict] = {}
    for lang in config.LANGUAGE_TABS:
        time.sleep(config.REQUEST_DELAY)
        try:
            entries = parse_trending(fetch_trending(session, lang, "weekly"))
        except requests.RequestException as exc:
            print(f"skip trending/{lang}: {exc}", file=sys.stderr)
            continue
        for e in entries:
            if e["stars_period"] is None or e["repo"] in blocked:
                continue
            hit = tab_hits.setdefault(e["repo"], {"stars_week": 0, "stars_total": e["stars_total"],
                                                  "sources": []})
            hit["stars_week"] = max(hit["stars_week"], e["stars_period"])
            hit["sources"].append(f"trending:{lang}")

    candidates: dict[str, dict] = {}
    top = sorted(tab_hits.items(), key=lambda kv: _prelim(kv[1]), reverse=True)
    for name, hit in top[:config.CANDIDATE_ENRICH_LIMIT]:
        api = gh.repo(name)
        if api is None:
            continue
        meta = repo_meta(api)
        candidates[meta["repo"]] = {**meta, "stars_week": hit["stars_week"],
                                    "stars_week_estimated": False, "sources": hit["sources"]}

    new_since = (now - timedelta(days=config.NEW_REPO_DAYS)).date().isoformat()
    cat_since = (now - timedelta(days=config.CATEGORY_SEARCH_DAYS)).date().isoformat()
    queries = [("search:new", f"created:>={new_since} stars:>={config.MIN_CANDIDATE_STARS}")]
    queries += [(f"search:{c['key']}",
                 f"{c['search']} created:>={cat_since} stars:>={config.MIN_CANDIDATE_STARS}")
                for c in config.CATEGORIES]
    for source, query in queries:
        try:
            items = gh.search_repos(query, per_page=30)
        except requests.RequestException as exc:
            print(f"skip search {query!r}: {exc}", file=sys.stderr)
            continue
        for obj in items:
            meta = repo_meta(obj)
            if meta["repo"] in candidates:
                candidates[meta["repo"]]["sources"].append(source)
                continue
            age = age_days(meta["created_at"], now)
            candidates[meta["repo"]] = {**meta,
                                        "stars_week": estimate_weekly(meta["stars"] or 0, age),
                                        "stars_week_estimated": True, "sources": [source]}

    kept, excluded = [], Counter()
    for c in candidates.values():
        c["age_days"] = age_days(c["created_at"], now)
        reason = exclusion_reason(c, blocked)
        if reason:
            excluded[reason] += 1
            continue
        c["guess_category"] = guess_category(c)
        c["score"] = score(c)
        kept.append(c)
    kept.sort(key=lambda c: c["score"], reverse=True)

    return {
        "week": week,
        "captured_at": now.isoformat(timespec="seconds"),
        "excluded": dict(sorted(excluded.items())),
        "candidates": kept[:250],
    }


# --- selection -------------------------------------------------------------

def shortlist(candidates: list[dict]) -> list[dict]:
    """Top candidates per guessed category; these get Korean summaries."""
    picked, per_cat = [], Counter()
    for c in candidates:  # already sorted by score
        if per_cat[c["guess_category"]] < config.SHORTLIST_PER_CATEGORY:
            picked.append(c)
            per_cat[c["guess_category"]] += 1
    return picked


def meta_of(c: dict) -> dict:
    return {k: c.get(k) for k in META_KEYS}


def reason_text(c: dict) -> str:
    stars_week = c["stars_week"] or 0
    if c["stars_week_estimated"]:
        parts = [f"최근 7일 ★ 약 +{stars_week:,} (추정)"]
    else:
        parts = [f"이번 주 ★ +{stars_week:,}"]
        ratio = stars_week / max(c["stars"] or 1, 1)
        if ratio >= 0.2:
            parts.append(f"전체 스타의 {ratio:.0%}가 이번 주 유입")
    age = c.get("age_days")
    if age is not None:
        if age <= 7:
            parts.append("공개 일주일 이내")
        elif age <= 180:
            parts.append(f"공개 {age}일 차")
        elif c.get("created_at"):
            parts.append(f"{c['created_at'][:4]}년 시작")
    return " · ".join(parts)


def finalize(week: str) -> dict:
    snap = store.read_json(store.snapshot_path(week))
    if snap is None:
        raise SystemExit(f"no snapshot for {week}")

    by_cat: dict[str, list[tuple]] = {k: [] for k in config.CATEGORY_KEYS}
    for c in snap["candidates"]:
        doc = store.load_repo(c["repo"])
        ko = (doc or {}).get("ko")
        cat = ko["category"] if ko else c["guess_category"]
        by_cat[cat].append((bool(ko), c))

    categories = []
    for cat in config.CATEGORIES:
        rows = sorted(by_cat[cat["key"]], key=lambda t: (t[0], t[1]["score"]), reverse=True)
        picks = []
        for _, c in rows[:config.RISING_PER_CATEGORY]:
            store.upsert_repo(meta_of(c), week)
            picks.append({
                "repo": c["repo"],
                "score": c["score"],
                "stars_week": c["stars_week"],
                "stars_week_estimated": c["stars_week_estimated"],
                "stars": c["stars"],
                "age_days": c["age_days"],
                "reason": reason_text(c),
            })
        categories.append({"key": cat["key"], "name": cat["name"], "repos": picks})

    doc = {
        "week": week,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": categories,
    }
    store.write_json(store.rising_path(week), doc)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="defaults to the latest collected week")
    args = ap.parse_args()
    week = args.week or (store.list_weeks() or [None])[-1]
    if week is None:
        print("no collected weeks yet", file=sys.stderr)
        return 1
    doc = finalize(week)
    for cat in doc["categories"]:
        print(f"{cat['key']:9} {len(cat['repos'])} repos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
