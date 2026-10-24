import json
import re
from pathlib import Path

from pipeline import config, merge_summaries, prepare_summaries, store

SKILL = Path(__file__).resolve().parent.parent / ".claude/skills/summarize-repos/SKILL.md"

GOOD = {
    "repo": "a/b",
    "one_liner": "터미널에서 코딩 에이전트를 관리하는 도구",
    "summary": "여러 코딩 에이전트를 한 화면에서 실행하고 상태를 확인할 수 있게 해 주는 오픈소스 도구다.",
    "features": ["에이전트 동시 실행", "작업 상태 확인"],
    "use_cases": "여러 에이전트를 함께 쓰는 개발자에게 맞다.",
    "category": "devtools",
}


def test_clean_readme_strips_noise():
    raw = ('<p align="center"><img src="logo.png"></p>\n'
           "[![CI](https://x/badge.svg)](https://x)\n"
           "# Title\n<!-- hidden -->\nSome <b>bold</b> text.\n\n\n\nMore.")
    text, truncated = prepare_summaries.clean_readme(raw)
    assert text == "# Title\n\nSome bold text.\n\nMore."
    assert not truncated


def test_clean_readme_truncates_on_heading(monkeypatch):
    monkeypatch.setattr(config, "README_MAX_CHARS", 100)
    raw = "# A\n" + "x" * 60 + "\n# B\n" + "y" * 60
    text, truncated = prepare_summaries.clean_readme(raw)
    assert truncated
    assert text == "# A\n" + "x" * 60


def test_validate_accepts_good_output():
    assert merge_summaries.validate(GOOD, "a/b") == []


def test_validate_rejects_bad_output():
    assert merge_summaries.validate({**GOOD, "category": "music"}, "a/b")
    assert merge_summaries.validate({**GOOD, "one_liner": "An English sentence"}, "a/b")
    assert merge_summaries.validate({**GOOD, "repo": "other/repo"}, "a/b")
    assert merge_summaries.validate({k: v for k, v in GOOD.items() if k != "features"}, "a/b")


def test_merge_writes_summary(data_dir):
    store.save_repo({"repo": "a/b", "description": "x"})
    store.save_repo({"repo": "c/d", "description": "y"})
    store.write_json(config.WORK_DIR / "manifest.json", {
        "a__b": {"repo": "a/b", "readme_sha": "s1", "readme_truncated": False, "chunk": "chunk-00"},
        "c__d": {"repo": "c/d", "readme_sha": "s2", "readme_truncated": False, "chunk": "chunk-00"},
    })
    out = config.WORK_DIR / "out"
    out.mkdir(parents=True)
    (out / "a__b.json").write_text(json.dumps(GOOD, ensure_ascii=False), encoding="utf-8")
    (out / "c__d.json").write_text("{not json", encoding="utf-8")

    assert merge_summaries.main() == 0
    ko = store.load_repo("a/b")["ko"]
    assert ko["one_liner"] == GOOD["one_liner"]
    assert ko["readme_sha"] == "s1"
    assert "ko" not in store.load_repo("c/d")


def test_skill_lists_every_category():
    keys = set(re.findall(r"^\| `([a-z-]+)` \|", SKILL.read_text(encoding="utf-8"), re.M))
    assert keys == set(config.CATEGORY_KEYS)
