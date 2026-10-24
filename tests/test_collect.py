import json
from datetime import datetime, timezone

from pipeline import collect, config, prepare_summaries, store

NOW = datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)


class FakeGitHub:
    def __init__(self, readmes=None):
        self.readmes = readmes or {}

    def repo(self, name):
        if name == "gone/repo":
            return None
        return {"full_name": name, "html_url": f"https://github.com/{name}",
                "description": f"{name} desc", "language": "Python", "topics": ["cli"],
                "stargazers_count": 100, "forks_count": 5, "created_at": "2026-01-01T00:00:00Z",
                "owner": {"avatar_url": "https://avatars/x"}}

    def readme(self, name):
        return self.readmes.get(name, ("# Readme\nhello", f"sha-{name}"))


def entry(rank, repo):
    return {"rank": rank, "repo": repo, "description": None, "language": "Go",
            "stars_total": 1000, "forks": 10, "stars_period": 200}


def test_build_week_tracks_movement(data_dir):
    store.save_week({"week": "2026-W41", "entries": [{"repo": "a/a", "rank": 3}]})
    store.save_week({"week": "2026-W42", "entries": [{"repo": "a/a", "rank": 1},
                                                     {"repo": "b/b", "rank": 2}]})
    doc = collect.build_week([entry(1, "b/b"), entry(2, "a/a"), entry(3, "gone/repo")],
                             "2026-W43", FakeGitHub(), NOW)
    rows = {r["repo"]: r for r in doc["entries"]}

    assert rows["a/a"]["prev_rank"] == 1
    assert rows["a/a"]["streak"] == 3
    assert rows["a/a"]["weeks_on_chart"] == 3
    assert rows["b/b"]["prev_rank"] == 2 and rows["b/b"]["streak"] == 2
    assert rows["gone/repo"]["is_new"] and rows["gone/repo"]["prev_rank"] is None
    assert not rows["a/a"]["is_new"]
    assert (doc["start"], doc["end"]) == ("2026-10-19", "2026-10-25")
    # repo files exist, including the one the API couldn't find
    assert store.load_repo("gone/repo")["url"] == "https://github.com/gone/repo"
    assert store.load_repo("a/a")["first_seen"] == "2026-W43"


def test_first_week_marks_nothing_new(data_dir):
    doc = collect.build_week([entry(1, "a/a")], "2026-W43", FakeGitHub(), NOW)
    assert doc["entries"][0]["is_new"] is False


def test_prepare_stages_only_stale_repos(data_dir, monkeypatch):
    monkeypatch.setattr(config, "CHUNK_SIZE", 2)
    monkeypatch.setattr(prepare_summaries, "GitHub",
                        lambda: FakeGitHub({"same/readme": ("# x", "sha-same")}))
    names = ["new/one", "new/two", "new/three", "fresh/summary", "same/readme"]
    store.save_week({"week": "2026-W43", "entries": [{"repo": n, "rank": i}
                                                     for i, n in enumerate(names, 1)]})
    for n in names:
        store.save_repo({"repo": n, "description": "d"})
    today = datetime.now(timezone.utc).date().isoformat()
    store.save_repo({"repo": "fresh/summary", "ko": {"generated_at": today}})
    store.save_repo({"repo": "same/readme",
                     "ko": {"generated_at": "2026-01-01", "readme_sha": "sha-same"}})

    monkeypatch.setattr("sys.argv", ["prepare_summaries", "--week", "2026-W43"])
    assert prepare_summaries.main() == 0

    manifest = json.loads((config.WORK_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert sorted(manifest) == ["new__one", "new__three", "new__two"]
    assert manifest["new__three"]["chunk"] == "chunk-01"
    staged = (config.WORK_DIR / "pending/chunk-00/new__one.md").read_text(encoding="utf-8")
    assert "- 출력 파일: work/out/new__one.json" in staged
    assert "hello" in staged
    # unchanged README: summary kept, check date recorded
    assert store.load_repo("same/readme")["ko"]["checked_at"] == today
