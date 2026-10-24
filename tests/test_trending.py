from pathlib import Path

from pipeline.trending import parse_trending, trending_url

FIXTURE = Path(__file__).parent / "fixtures" / "trending_weekly.html"


def test_parses_real_rows():
    rows = parse_trending(FIXTURE.read_text(encoding="utf-8"))
    assert [r["repo"] for r in rows] == [
        "cloudflare/security-audit-skill", "morluto/rea", "example/no-description"]
    first = rows[0]
    assert first == {
        "rank": 1,
        "repo": "cloudflare/security-audit-skill",
        "description": "A coding-agent skill for multi-phase security audits with "
                       "independently verified, machine-readable findings",
        "language": "JavaScript",
        "stars_total": 43755,
        "forks": 2730,
        "stars_period": 11223,
    }
    assert rows[1]["stars_total"] == 377278
    assert rows[1]["stars_period"] == 88243


def test_missing_fields_and_old_fork_link():
    row = parse_trending(FIXTURE.read_text(encoding="utf-8"))[2]
    assert row["description"] is None
    assert row["language"] is None
    assert row["forks"] == 9
    assert row["stars_period"] == 1


def test_empty_page():
    assert parse_trending("<html><body></body></html>") == []


def test_urls():
    assert trending_url() == "https://github.com/trending?since=weekly"
    assert trending_url("c%23", "daily") == "https://github.com/trending/c%23?since=daily"
