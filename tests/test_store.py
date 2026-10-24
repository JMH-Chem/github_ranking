from datetime import date, datetime, timezone

from pipeline import store


def test_monday_capture_labels_previous_week():
    # Monday 2026-10-26 09:00 KST = 00:00 UTC -> week of Sunday 10-25 (W43)
    assert store.week_label(datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)) == "2026-W43"


def test_midweek_run_labels_current_week():
    # Saturday 2026-10-24 -> W43, later overwritten by Monday's capture
    assert store.week_label(datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)) == "2026-W43"


def test_year_boundary():
    # Monday 2027-01-04 09:00 KST -> Sunday 2027-01-03 is in ISO 2026-W53
    assert store.week_label(datetime(2027, 1, 4, 0, 0, tzinfo=timezone.utc)) == "2026-W53"


def test_week_range():
    assert store.week_range("2026-W43") == (date(2026, 10, 19), date(2026, 10, 25))


def test_slug_roundtrip():
    assert store.slug("owner/my__repo") == "owner__my__repo"
    assert store.unslug("owner__my__repo") == "owner/my__repo"


def test_upsert_keeps_summary(data_dir):
    store.save_repo({"repo": "a/b", "first_seen": "2026-W40", "ko": {"one_liner": "요약"}})
    doc = store.upsert_repo({"repo": "a/b", "stars": 10, "ko": None}, "2026-W43")
    assert doc["ko"] == {"one_liner": "요약"}
    assert doc["first_seen"] == "2026-W40"
    assert doc["last_seen"] == "2026-W43"
    assert doc["stars"] == 10
