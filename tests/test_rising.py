from pipeline import config, rising, store


def cand(repo, **kw):
    c = {
        "repo": repo, "description": "", "topics": [], "stars": 1000, "forks": 50,
        "archived": False, "is_fork": False, "stars_week": 300,
        "stars_week_estimated": False, "age_days": 40, "created_at": "2026-09-14T00:00:00Z",
    }
    c.update(kw)
    return c


def test_guess_category_prefers_topics():
    assert rising.guess_category(cand("x/y", topics=["llm", "agent"])) == "ai-llm"
    assert rising.guess_category(cand("x/y", description="A fast terminal UI for git")) == "devtools"
    assert rising.guess_category(cand("x/y", topics=["pentest"], description="AI helper")) == "security"
    assert rising.guess_category(cand("x/y", description="nothing to see")) == "etc"


def test_guess_category_ignores_substrings():
    # "ai" must not match inside "maintain"
    assert rising.guess_category(cand("x/y", description="easy to maintain")) == "etc"


def test_score_rewards_growth_and_youth():
    young = rising.score(cand("a/b", stars=1000, stars_week=500, age_days=10))
    old = rising.score(cand("a/b", stars=1000, stars_week=500, age_days=1000))
    slow = rising.score(cand("a/b", stars=50000, stars_week=500, age_days=10))
    estimated = rising.score(cand("a/b", stars=1000, stars_week=500, age_days=10,
                                  stars_week_estimated=True))
    assert young > old
    assert young > slow
    assert young > estimated


def test_estimate_weekly():
    assert rising.estimate_weekly(700, 3) == 700
    assert rising.estimate_weekly(700, 70) == 70


def test_exclusions():
    blocked = {"ranked/repo"}
    assert rising.exclusion_reason(cand("ranked/repo"), blocked) == "recent"
    assert rising.exclusion_reason(cand("a/b", archived=True), blocked) == "archived"
    assert rising.exclusion_reason(cand("a/awesome-rust"), blocked) == "list"
    assert rising.exclusion_reason(cand("a/b", description="A curated list of tools"), blocked) == "list"
    assert rising.exclusion_reason(cand("a/b", stars=10), blocked) == "few-stars"
    assert rising.exclusion_reason(cand("a/b", forks=0, stars=5000), blocked) == "suspicious"
    assert rising.exclusion_reason(cand("a/b", stars_week=60), blocked) == "slow"
    assert rising.exclusion_reason(cand("a/b", stars=90000, stars_week=4000, age_days=2000),
                                   blocked) == "established"
    assert rising.exclusion_reason(cand("a/b", stars=9000, stars_week=900, age_days=2000),
                                   blocked) is None
    assert rising.exclusion_reason(cand("a/ai-jailbreaks"), blocked) == "keyword"
    assert rising.exclusion_reason(cand("a/b", topics=["keygen"]), blocked) == "keyword"
    assert rising.exclusion_reason(cand("a/b"), blocked, {"a/b"}) == "blocklist"
    assert rising.exclusion_reason(cand("a/b"), blocked, {"a/*"}) == "blocklist"
    assert rising.exclusion_reason(cand("a/b"), blocked) is None


def test_load_blocklist(tmp_path, monkeypatch):
    path = tmp_path / "blocklist.txt"
    path.write_text("# comment\nSpam/Repo  # why\n\nfarm/*\n", encoding="utf-8")
    monkeypatch.setattr(config, "BLOCKLIST_FILE", path)
    assert rising.load_blocklist() == {"spam/repo", "farm/*"}


def test_blocked_includes_recent_ranks_and_recommendations(data_dir):
    store.save_week({"week": "2026-W42", "entries": [{"repo": "old/ranked", "rank": 1}]})
    store.save_week({"week": "2026-W43", "entries": [{"repo": "now/ranked", "rank": 1}]})
    store.write_json(store.rising_path("2026-W42"),
                     {"categories": [{"repos": [{"repo": "was/rising"}]}]})
    assert rising.blocked_repos("2026-W43") == {"old/ranked", "now/ranked", "was/rising"}


def test_shortlist_caps_per_category_and_owner(data_dir, monkeypatch):
    monkeypatch.setattr(config, "SHORTLIST_PER_CATEGORY", 2)
    cands = [cand(f"o{i}/r", guess_category="web") for i in range(5)]
    cands += [cand("o0/second", guess_category="data"), cand("b/1", guess_category="data")]
    picked = rising.shortlist(cands, "2026-W43")
    assert [c["repo"] for c in picked] == ["o0/r", "o1/r", "b/1"]


def test_finalize_uses_claude_category_and_prefers_summarized(data_dir, monkeypatch):
    monkeypatch.setattr(config, "RISING_PER_CATEGORY", 1)
    cands = [
        {**cand("top/unsummarized", guess_category="web"), "score": 9.0},
        {**cand("next/summarized", guess_category="web"), "score": 5.0},
        {**cand("moved/to-data", guess_category="web"), "score": 4.0},
    ]
    store.write_json(store.snapshot_path("2026-W43"), {"week": "2026-W43", "candidates": cands})
    store.save_repo({"repo": "next/summarized", "ko": {"category": "web"}})
    store.save_repo({"repo": "moved/to-data", "ko": {"category": "data"}})

    doc = rising.finalize("2026-W43")
    picks = {c["key"]: [r["repo"] for r in c["repos"]] for c in doc["categories"]}
    assert picks["web"] == ["next/summarized"]
    assert picks["data"] == ["moved/to-data"]
    assert store.load_repo("next/summarized")["ko"] == {"category": "web"}
    assert store.rising_path("2026-W43").exists()


def test_finalize_one_repo_per_owner(data_dir):
    cands = [
        {**cand("same/a", guess_category="web"), "score": 9.0},
        {**cand("same/b", guess_category="data"), "score": 8.0},
        {**cand("other/c", guess_category="data"), "score": 7.0},
    ]
    store.write_json(store.snapshot_path("2026-W43"), {"week": "2026-W43", "candidates": cands})
    doc = rising.finalize("2026-W43")
    picks = {c["key"]: [r["repo"] for r in c["repos"]] for c in doc["categories"]}
    assert picks["web"] == ["same/a"]
    assert picks["data"] == ["other/c"]


def test_reason_text():
    text = rising.reason_text(cand("a/b", stars=1000, stars_week=400, age_days=21))
    assert text == "이번 주 ★ +400 · 전체 스타의 40%가 이번 주 유입 · 공개 21일 차"
    est = rising.reason_text(cand("a/b", stars_week=90, stars_week_estimated=True, age_days=400))
    assert est == "최근 7일 ★ 약 +90 (추정) · 2026년 시작"
