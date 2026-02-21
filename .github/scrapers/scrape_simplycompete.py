#!/usr/bin/env python3
"""
Scraper för World Taekwondo SimplyCompete
Körs i GitHub Actions (inte ett webbhotell-IP → Cloudflare blockerar ej)
Sparar data till data/simplycompete.json
"""
import json
import sys
import time
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import urllib.error

API_BASE = "https://worldtkd.simplycompete.com/eventList"
PAGE_SIZE = 50
OUTPUT_FILE = "data/simplycompete.json"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://worldtkd.simplycompete.com/events",
    "Origin": "https://worldtkd.simplycompete.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def fetch_page(page: int) -> list:
    params = urllib.parse.urlencode({
        "da": "true",
        "eventType": "All",
        "invitationStatus": "all",
        "isArchived": "false",
        "itemsPerPage": PAGE_SIZE,
        "pageNumber": page,
    })
    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                print(f"  HTTP {resp.status} på sida {page}", file=sys.stderr)
                return []
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if isinstance(data, list):
                return data
            # Försök extrahera items ur nycklat objekt
            for key in ["events", "data", "items", "results", "eventList"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            print(f"  Okänd JSON-struktur: {list(data.keys())[:5]}", file=sys.stderr)
            return []
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code} sida {page}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  Fel sida {page}: {e}", file=sys.stderr)
        return []


def normalize_event(raw: dict) -> dict | None:
    name = (raw.get("name") or raw.get("eventName") or raw.get("title") or "").strip()
    if not name:
        return None

    event_id  = raw.get("id") or raw.get("eventId") or raw.get("slug") or ""
    url       = f"https://worldtkd.simplycompete.com/events/{event_id}" if event_id else "https://worldtkd.simplycompete.com/events"

    start_date = None
    for f in ["startDate", "eventDate", "start_date", "date", "startDateTime", "eventStartDate"]:
        if raw.get(f):
            start_date = raw[f]
            break

    deadline = None
    for f in ["registrationDeadline", "deadline", "registrationClose", "closeDate", "regDeadline"]:
        if raw.get(f):
            deadline = raw[f]
            break

    city    = raw.get("city") or raw.get("venue") or ""
    country = raw.get("country") or raw.get("countryName") or ""
    location = ", ".join(filter(None, [city, country]))

    return {
        "name":     name,
        "url":      url,
        "date":     start_date,
        "deadline": deadline,
        "location": location,
        "country":  country,
        "source":   "World Taekwondo (SimplyCompete)",
    }


def main():
    print("Hämtar SimplyCompete events...")
    all_events = []
    page = 1

    while page <= 10:
        print(f"  Sida {page}...", end=" ")
        items = fetch_page(page)
        print(f"{len(items)} items")

        if not items:
            break

        for raw in items:
            if isinstance(raw, dict):
                ev = normalize_event(raw)
                if ev:
                    all_events.append(ev)

        if len(items) < PAGE_SIZE:
            break

        page += 1
        time.sleep(0.5)  # Vara snäll mot servern

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count":      len(all_events),
        "events":     all_events,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Sparade {len(all_events)} events till {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
