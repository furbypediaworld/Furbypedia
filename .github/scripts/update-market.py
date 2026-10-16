#!/usr/bin/env python3
"""Refresh FurbyMarket with active, recently published Mercado Libre Mexico listings."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "market-listings.json"
BASE = "https://api.mercadolibre.com/sites/MLM/search"
QUERIES = ["furby", "furblet", "furby vintage", "furby en caja"]
FRESH_DAYS = 30
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=FRESH_DAYS)


def get_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Furbypedia-FurbyMarket/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def main():
    found = {}
    successful_queries = 0
    for query in QUERIES:
        params = urllib.parse.urlencode({"q": query, "limit": 50, "sort": "relevance"})
        try:
            payload = get_json(f"{BASE}?{params}")
            successful_queries += 1
        except Exception as exc:
            print(f"Query failed ({query}): {exc}", file=sys.stderr)
            continue

        for item in payload.get("results", []):
            title = str(item.get("title") or "").strip()
            title_l = title.lower()
            if not title or not any(term in title_l for term in ("furby", "furblet")):
                continue
            if item.get("status") != "active" or not item.get("permalink"):
                continue
            created = parse_date(item.get("date_created"))
            if not created or created < CUTOFF or created > NOW + timedelta(hours=1):
                continue
            item_id = str(item.get("id") or item.get("permalink"))
            shipping = item.get("shipping") or {}
            found[item_id] = {
                "id": item_id,
                "title": title,
                "price": item.get("price"),
                "currency_id": item.get("currency_id") or "MXN",
                "condition": item.get("condition") or "used",
                "date_created": created.isoformat(),
                "last_updated": item.get("last_updated"),
                "last_verified_at": NOW.isoformat(),
                "permalink": item.get("permalink"),
                "thumbnail": (item.get("thumbnail") or "").replace("http://", "https://"),
                "shipping_free": bool(shipping.get("free_shipping")),
                "source": "Mercado Libre México",
            }

    if successful_queries == 0:
        raise RuntimeError("All Mercado Libre API queries failed; preserving the previous feed.")

    items = sorted(found.values(), key=lambda x: x["date_created"], reverse=True)
    payload = {
        "last_updated": NOW.isoformat(),
        "source": "Mercado Libre México API",
        "freshness_days": FRESH_DAYS,
        "items": items,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(items)} active listings published within {FRESH_DAYS} days.")
    if not items:
        print("No qualifying listings found; feed remains empty rather than showing stale items.")


if __name__ == "__main__":
    main()
