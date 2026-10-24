"""Validate Claude's summaries in work/out/ and merge them into data/repos/.

    python -m pipeline.merge_summaries

Anything that fails validation is reported and left out; the repo keeps its
previous summary (or shows the original English description) and is retried
on the next run.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from . import config, store

SCHEMA = {
    "type": "object",
    "required": ["repo", "one_liner", "summary", "features", "use_cases", "category"],
    "properties": {
        "repo": {"type": "string"},
        "one_liner": {"type": "string", "minLength": 5, "maxLength": 120},
        "summary": {"type": "string", "minLength": 30, "maxLength": 1500},
        "features": {
            "type": "array", "minItems": 2, "maxItems": 8,
            "items": {"type": "string", "minLength": 2, "maxLength": 300},
        },
        "use_cases": {"type": "string", "minLength": 5, "maxLength": 600},
        "category": {"enum": config.CATEGORY_KEYS},
    },
}
VALIDATOR = Draft202012Validator(SCHEMA)
HANGUL = re.compile(r"[가-힣]")


def validate(obj, expected_repo: str) -> list[str]:
    errors = [e.message for e in VALIDATOR.iter_errors(obj)]
    if errors:
        return errors
    if obj["repo"].lower() != expected_repo.lower():
        errors.append(f"repo is {obj['repo']!r}, expected {expected_repo!r}")
    for field in ("one_liner", "summary", "use_cases"):
        if not HANGUL.search(obj[field]):
            errors.append(f"{field} is not Korean")
    return errors


def main() -> int:
    manifest = store.read_json(config.WORK_DIR / "manifest.json", {})
    out_dir = config.WORK_DIR / "out"
    today = datetime.now(timezone.utc).date().isoformat()

    merged, problems = 0, []
    for slug, info in manifest.items():
        path = out_dir / f"{slug}.json"
        if not path.exists():
            problems.append(f"{info['repo']}: no output")
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{info['repo']}: invalid JSON ({exc})")
            continue
        errors = validate(obj, info["repo"])
        if errors:
            problems.append(f"{info['repo']}: {'; '.join(errors)}")
            continue
        doc = store.load_repo(info["repo"])
        if doc is None:
            problems.append(f"{info['repo']}: repo file missing")
            continue
        doc["ko"] = {
            "one_liner": obj["one_liner"].strip(),
            "summary": obj["summary"].strip(),
            "features": [f.strip() for f in obj["features"]],
            "use_cases": obj["use_cases"].strip(),
            "category": obj["category"],
            "generated_at": today,
            "readme_sha": info["readme_sha"],
            "readme_truncated": info["readme_truncated"],
        }
        store.save_repo(doc)
        merged += 1

    report = [f"merged {merged}/{len(manifest)} summaries"] + [f"- {p}" for p in problems]
    print("\n".join(report))
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### 한국어 요약 반영 결과\n\n" + "\n".join(report) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
