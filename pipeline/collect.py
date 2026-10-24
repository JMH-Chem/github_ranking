"""Weekly collection: the official ranking plus rising-repo candidates.

    python -m pipeline.collect [--week 2026-W43] [--skip-rising]

Writes data/weeks/<week>.json, data/repos/<repo>.json for each ranked repo,
and data/snapshots/<week>.json with scored rising candidates. Prints the
week label as `week=<label>` for the workflow to pick up.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from . import config, rising, store
from .github_api import GitHub, repo_meta
from .trending import fetch_trending, new_session, parse_trending, trending_url

MIN_RANKED = 5  # fewer rows than this means the page layout changed


def build_week(entries: list[dict], week: str, gh: GitHub, now: datetime) -> dict:
    previous = [w for w in store.list_weeks() if w < week]
    ranks = {w: {e["repo"]: e["rank"] for e in store.load_week(w)["entries"]} for w in previous}
    prev_ranks = ranks[previous[-1]] if previous else {}

    rows = []
    for e in entries:
        api = gh.repo(e["repo"])
        meta = repo_meta(api) if api else {
            "repo": e["repo"],
            "url": f"https://github.com/{e['repo']}",
            "description": e["description"],
            "language": e["language"],
            "stars": e["stars_total"],
            "forks": e["forks"],
        }
        store.upsert_repo(meta, week)
        name = meta["repo"]

        seen = [w for w in previous if name in ranks[w]]
        streak = 1
        for w in reversed(previous):
            if name not in ranks[w]:
                break
            streak += 1

        rows.append({
            "rank": e["rank"],
            "repo": name,
            "stars_week": e["stars_period"],
            "stars_total": e["stars_total"],
            "forks": e["forks"],
            "language": e["language"] or meta.get("language"),
            "prev_rank": prev_ranks.get(name),
            "is_new": bool(previous) and not seen,
            "weeks_on_chart": len(seen) + 1,
            "streak": streak,
        })

    monday, sunday = store.week_range(week)
    return {
        "week": week,
        "start": monday.isoformat(),
        "end": sunday.isoformat(),
        "captured_at": now.isoformat(timespec="seconds"),
        "source": trending_url(since="weekly"),
        "entries": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="override the week label, e.g. 2026-W43")
    ap.add_argument("--skip-rising", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    week = args.week or store.week_label(now)
    session, gh = new_session(), GitHub()

    entries = parse_trending(fetch_trending(session, since="weekly"))
    if len(entries) < MIN_RANKED or any(e["stars_period"] is None for e in entries):
        print(f"parsed {len(entries)} rows with missing fields; "
              "the trending page layout may have changed", file=sys.stderr)
        return 1

    doc = build_week(entries, week, gh, now)
    store.save_week(doc)
    print(f"{week}: {len(doc['entries'])} ranked repos")

    if not args.skip_rising:
        snap = rising.gather_candidates(session, gh, week, now)
        store.write_json(store.snapshot_path(week), snap)
        print(f"{week}: {len(snap['candidates'])} rising candidates, excluded {snap['excluded']}")

    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"week={week}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
