#!/usr/bin/env python3
"""
Scraper för MA-RegOnline
Körs i GitHub Actions – undviker Imunify360 bot-protection
Sparar data till data/maregonline.json
"""
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
import urllib.request
import urllib.error

BASE_URL    = "https://www.ma-regonline.com"
LIST_URL    = "https://www.ma-regonline.com/"
OUTPUT_FILE = "data/maregonline.json"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5,  "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10,"nov": 11, "dec": 12,
}


def fetch_html(url: str) -> str | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if "Imunify360" in body:
                print(f"  ⚠ Imunify360 blockerar från GitHub Actions-IP", file=sys.stderr)
                return None
            return body
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Fel: {e}", file=sys.stderr)
        return None


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def parse_date(s: str) -> str | None:
    """Parsar '1 March 2026' → '2026-03-01' (ISO 8601)"""
    s = s.strip()
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if not m:
        return None
    day, mon, year = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
    if mon not in MONTH_MAP:
        return None
    try:
        return datetime(year, MONTH_MAP[mon], day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def main():
    print("Hämtar MA-RegOnline events...")
    body = fetch_html(LIST_URL)

    if not body:
        print("Kunde inte hämta MA-RegOnline (blockerad)", file=sys.stderr)
        # Skriv tom fil ändå för att undvika "filen saknas"-fel i WordPress
        output = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": 0,
            "events": [],
            "error": "Blocked by Imunify360 bot-protection",
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)
        sys.exit(0)

    events  = []
    offset  = 0

    # Matcha alla tournament-länkar (inkl attribut som kan ha radbrytningar)
    link_pat = re.compile(
        r'<a[\s\S]*?href=["\'](/tournaments/(\d+)/([^"\']+))["\'][\s\S]*?>([^<]+)</a>',
        re.IGNORECASE
    )

    for m in link_pat.finditer(body):
        href  = m.group(1)
        name  = unescape(m.group(4)).strip()
        pos   = m.end()

        if not name or len(name) < 3:
            continue

        # Text efter länken (300 tecken)
        after_raw = body[pos:pos+300]
        after     = unescape(strip_tags(after_raw))

        # Datum
        date_m = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})", after)
        if not date_m:
            continue
        event_date = parse_date(date_m.group(1))
        if not event_date:
            continue

        # Skippa passerade events
        try:
            if datetime.strptime(event_date, "%Y-%m-%d") < datetime.now():
                continue
        except ValueError:
            pass

        # Deadline
        deadline = None
        dl_m = re.search(r"Deadline:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", after, re.IGNORECASE)
        if dl_m:
            deadline = parse_date(dl_m.group(1))

        # Land från flagg-img precis FÖRE länken
        before = body[max(0, m.start()-300):m.start()]
        country = ""
        flag_m = re.search(
            r'<img[\s\S]*?alt=["\']([^"\']+)["\'][\s\S]*?flags[\s\S]*?>|<img[\s\S]*?flags[\s\S]*?alt=["\']([^"\']+)["\'][\s\S]*?>',
            before, re.IGNORECASE
        )
        if flag_m:
            country = flag_m.group(1) or flag_m.group(2) or ""
            country = unescape(country).strip()

        events.append({
            "name":     name,
            "url":      BASE_URL + href,
            "date":     event_date,
            "deadline": deadline,
            "location": country,
            "country":  country,
            "source":   "MA-RegOnline",
        })

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count":      len(events),
        "events":     events,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Sparade {len(events)} events till {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
