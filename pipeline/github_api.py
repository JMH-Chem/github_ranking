"""Minimal GitHub REST client: repo metadata, README, search."""

import base64
import os
import sys
import time
from datetime import datetime, timezone

import requests

from . import config

API = "https://api.github.com"


class GitHub:
    def __init__(self, token: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": config.USER_AGENT,
        })
        token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, params: dict | None = None) -> requests.Response | None:
        """GET with retries on rate limits and 5xx. Returns None on 404."""
        for attempt in range(4):
            resp = self.session.get(f"{API}{path}", params=params, timeout=30)
            if resp.status_code == 404:
                return None
            if resp.status_code in (403, 429) and _rate_limited(resp):
                wait = _rate_limit_wait(resp)
                print(f"rate limited on {path}, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    def repo(self, full_name: str) -> dict | None:
        resp = self._get(f"/repos/{full_name}")
        return resp.json() if resp is not None else None

    def readme(self, full_name: str) -> tuple[str | None, str | None]:
        """(text, sha) of the default-branch README, or (None, None)."""
        resp = self._get(f"/repos/{full_name}/readme")
        if resp is None:
            return None, None
        body = resp.json()
        if body.get("encoding") != "base64":
            return None, body.get("sha")
        text = base64.b64decode(body["content"]).decode("utf-8", errors="replace")
        return text, body.get("sha")

    def search_repos(self, query: str, per_page: int = 30) -> list[dict]:
        resp = self._get("/search/repositories",
                         {"q": query, "sort": "stars", "order": "desc", "per_page": per_page})
        # Search allows 30 requests/minute with a token.
        time.sleep(2.5)
        return resp.json().get("items", []) if resp is not None else []


def _rate_limited(resp: requests.Response) -> bool:
    return (resp.headers.get("X-RateLimit-Remaining") == "0"
            or "retry-after" in {k.lower() for k in resp.headers}
            or "rate limit" in resp.text.lower())


def _rate_limit_wait(resp: requests.Response) -> int:
    if "Retry-After" in resp.headers:
        return int(resp.headers["Retry-After"]) + 1
    reset = resp.headers.get("X-RateLimit-Reset")
    if reset:
        return max(1, min(int(reset) - int(time.time()) + 1, 900))
    return 60


def repo_meta(obj: dict) -> dict:
    """The fields we keep from a /repos or /search API object."""
    license_ = obj.get("license") or {}
    return {
        "repo": obj["full_name"],
        "url": obj["html_url"],
        "description": obj.get("description"),
        "homepage": obj.get("homepage") or None,
        "language": obj.get("language"),
        "topics": obj.get("topics") or [],
        "license": license_.get("spdx_id") if license_.get("spdx_id") != "NOASSERTION" else None,
        "stars": obj.get("stargazers_count"),
        "forks": obj.get("forks_count"),
        "open_issues": obj.get("open_issues_count"),
        "created_at": obj.get("created_at"),
        "pushed_at": obj.get("pushed_at"),
        "archived": bool(obj.get("archived")),
        "is_fork": bool(obj.get("fork")),
        "owner_avatar": (obj.get("owner") or {}).get("avatar_url"),
    }


def age_days(created_at: str | None, now: datetime | None = None) -> int | None:
    if not created_at:
        return None
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return max(0, (now - created).days)
