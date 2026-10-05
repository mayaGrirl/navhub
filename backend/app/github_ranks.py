import re
import threading
import time

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import GithubRank

PERIODS = {
    "past_24_hours": "daily",
    "past_week": "weekly",
    "past_month": "monthly",
}


def _stars(text: str) -> str:
    match = re.search(r"([0-9,.]+)\s+stars", text)
    return match.group(1) if match else ""


def fetch_period(since: str) -> list[dict]:
    response = httpx.get(
        "https://github.com/trending",
        params={"since": since},
        timeout=25,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows = []
    for index, article in enumerate(soup.select("article.Box-row"), start=1):
        link = article.select_one("h2 a")
        if not link:
            continue
        name = link.get_text(" ", strip=True).replace(" ", "")
        description = article.select_one("p")
        language = article.select_one("[itemprop='programmingLanguage']")
        rows.append(
            {
                "repo_name": name,
                "description": description.get_text(" ", strip=True) if description else "",
                "stars": _stars(article.get_text(" ", strip=True)),
                "language": language.get_text(strip=True) if language else "",
                "position": index,
            }
        )
    return rows


def fetch_total() -> list[dict]:
    response = httpx.get(
        "https://api.github.com/search/repositories",
        params={"q": "stars:>1000", "sort": "stars", "order": "desc", "per_page": 20},
        timeout=25,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "NavhubBot"},
    )
    response.raise_for_status()
    rows = []
    for index, item in enumerate(response.json().get("items", []), start=1):
        rows.append(
            {
                "repo_name": item.get("full_name") or "",
                "description": (item.get("description") or "")[:300],
                "stars": f"{item.get('stargazers_count', 0):,}",
                "language": item.get("language") or "",
                "position": index,
            }
        )
    return rows


def refresh_ranks() -> dict:
    db = SessionLocal()
    saved = {}
    try:
        for period, since in PERIODS.items():
            rows = fetch_period(since)
            if not rows:
                continue
            db.execute(delete(GithubRank).where(GithubRank.period == period))
            for row in rows:
                db.add(GithubRank(period=period, **row))
            saved[period] = len(rows)
        total = fetch_total()
        if total:
            db.execute(delete(GithubRank).where(GithubRank.period == "total"))
            for row in total:
                db.add(GithubRank(period="total", **row))
            saved["total"] = len(total)
        db.commit()
    finally:
        db.close()
    return saved


def _star_count(text: str) -> int:
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits or 0)


def load_ranks(period: str) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.scalars(select(GithubRank).where(GithubRank.period == period)).all()
        ordered = sorted(rows, key=lambda row: _star_count(row.stars), reverse=True)
        return [
            {
                "repo_name": row.repo_name,
                "description": row.description,
                "stars": row.stars,
                "language": row.language,
            }
            for row in ordered
        ]
    finally:
        db.close()


def schedule_daily() -> None:
    def loop():
        while True:
            try:
                print("github ranks", refresh_ranks())
            except Exception as exc:
                print("github ranks failed", exc.__class__.__name__)
            time.sleep(60 * 60 * 24)

    threading.Thread(target=loop, daemon=True).start()
