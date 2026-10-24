"""Reading and writing the JSON files under data/."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config

KST = timezone(timedelta(hours=9))


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def slug(full_name: str) -> str:
    """owner/name -> owner__name. GitHub owners can't contain "_", so this is reversible."""
    return full_name.replace("/", "__", 1)


def unslug(s: str) -> str:
    return s.replace("__", "/", 1)


# --- weeks -----------------------------------------------------------------

def week_label(now: datetime) -> str:
    """Label for a capture taken at `now`.

    The Monday-morning capture describes the week that just ended, so the
    label is the ISO week of the previous day in KST.
    """
    day = (now.astimezone(KST) - timedelta(days=1)).date()
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_range(label: str) -> tuple[date, date]:
    """(Monday, Sunday) of an ISO week label like 2026-W43."""
    year, week = label.split("-W")
    monday = date.fromisocalendar(int(year), int(week), 1)
    return monday, monday + timedelta(days=6)


def weeks_dir() -> Path:
    return config.DATA_DIR / "weeks"


def list_weeks() -> list[str]:
    return sorted(p.stem for p in weeks_dir().glob("*.json"))


def load_week(label: str) -> dict | None:
    return read_json(weeks_dir() / f"{label}.json")


def save_week(doc: dict) -> None:
    write_json(weeks_dir() / f"{doc['week']}.json", doc)


# --- repos -----------------------------------------------------------------

def repo_path(full_name: str) -> Path:
    return config.DATA_DIR / "repos" / f"{slug(full_name)}.json"


def load_repo(full_name: str) -> dict | None:
    return read_json(repo_path(full_name))


def save_repo(doc: dict) -> None:
    write_json(repo_path(doc["repo"]), doc)


def upsert_repo(meta: dict, week: str) -> dict:
    """Merge fresh metadata into the stored repo doc, keeping the Korean summary."""
    doc = load_repo(meta["repo"]) or {"repo": meta["repo"], "first_seen": week}
    ko = doc.get("ko")
    doc.update(meta)
    if ko is not None:
        doc["ko"] = ko
    doc["last_seen"] = week
    save_repo(doc)
    return doc


# --- snapshots / rising ----------------------------------------------------

def snapshot_path(label: str) -> Path:
    return config.DATA_DIR / "snapshots" / f"{label}.json"


def rising_path(label: str) -> Path:
    return config.DATA_DIR / "rising" / f"{label}.json"


def list_rising() -> list[str]:
    return sorted(p.stem for p in (config.DATA_DIR / "rising").glob("*.json"))
