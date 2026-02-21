import json, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

OUT_FILE  = "data/simplycompete.json"
PAGE_SIZE = 50
BASE      = "https://worldtkd.simplycompete.com"

ENDPOINTS = [
    f"{BASE}/api/events",
    f"{BASE}/api/v1/events",
    f"{BASE}/api/v2/events",
    f"{BASE}/events/list",
    f"{BASE}/eventList",
    f"{BASE}/api/eventList",
]

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE}/events",
    "Origin": BASE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

def try_endpoint(url):
    params = urllib.parse.urlencode({"da":"true","eventType":"All","invitationStatus":"all","isArchived":"false","itemsPerPage":PAGE_SIZE,"pageNumber":1})
    req = urllib.request.Request(f"{url}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status != 200:
                return None, f"HTTP {r.status}"
            body = r.read().decode("utf-8")
            first = body.lstrip()[0] if body.strip() else ""
            if first not in ("[", "{"):
                return None, f"Inte JSON: {body.strip()[:60]}"
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        return None, f"HTTPError {e.code}"
    except Exception as e:
        return None, str(e)

def extract_items(data):
    if isinstance(data, list): return data
    for k in ["events","data","items","results","eventList","list"]:
        if k in data and isinstance(data[k], list): return data[k]
    return []

def norm(raw):
    name = (raw.get("name") or raw.get("eventName") or raw.get("title") or "").strip()
    if not name: return None
    eid  = raw.get("id") or raw.get("eventId") or raw.get("slug") or ""
    url  = f"{BASE}/events/{eid}" if eid else f"{BASE}/events"
    date = next((raw[f] for f in ["startDate","eventDate","start_date","date","startDateTime"] if raw.get(f)), None)
    dl   = next((raw[f] for f in ["registrationDeadline","deadline","registrationClose","closeDate"] if raw.get(f)), None)
    city    = raw.get("city") or raw.get("venue") or ""
    country = raw.get("country") or raw.get("countryName") or ""
    return {"name":name,"url":url,"date":date,"deadline":dl,"location":", ".join(filter(None,[city,country])),"country":country,"source":"World Taekwondo (SimplyCompete)"}

# Hitta fungerande endpoint
working_endpoint = None
for ep in ENDPOINTS:
    data, err = try_endpoint(ep)
    if data is not None:
        items = extract_items(data)
        if items:
            working_endpoint = ep
            print(f"Fungerande endpoint: {ep} ({len(items)} items)")
            break
        else:
            print(f"  {ep}: OK men inga items. Struktur: {list(data.keys())[:5] if isinstance(data,dict) else type(data)}", file=sys.stderr)
    else:
        print(f"  {ep}: {err}", file=sys.stderr)

if not working_endpoint:
    print("Ingen endpoint fungerade", file=sys.stderr)
    out = {"updated_at": datetime.now(timezone.utc).isoformat(), "count": 0, "events": [], "error": "no working endpoint"}
    json.dump(out, open(OUT_FILE,"w"), indent=2)
    sys.exit(0)

all_events = []
page = 1
while page <= 10:
    params = urllib.parse.urlencode({"da":"true","eventType":"All","invitationStatus":"all","isArchived":"false","itemsPerPage":PAGE_SIZE,"pageNumber":page})
    req = urllib.request.Request(f"{working_endpoint}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            items = extract_items(json.loads(r.read().decode("utf-8")))
    except Exception as e:
        print(f"Sida {page} fel: {e}", file=sys.stderr)
        break
    if not items: break
    all_events += [e for e in (norm(r) for r in items if isinstance(r,dict)) if e]
    if len(items) < PAGE_SIZE: break
    page += 1
    time.sleep(0.3)

out = {"updated_at": datetime.now(timezone.utc).isoformat(), "count": len(all_events), "events": all_events}
json.dump(out, open(OUT_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Sparade {len(all_events)} events")
