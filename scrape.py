"""Fetch today's Taurus horoscope from real sites. Verbatim text only, nothing generated."""
import json, re, datetime, requests
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

IST = ZoneInfo("Asia/Kolkata")
UA = {"User-Agent": "Mozilla/5.0 (personal daily horoscope page)"}

# US sites are a day behind India at 6 AM IST, so we take their "tomorrow" page = her today.
SOURCES = [
    {"name": "Horoscope.com",
     "url": "https://www.horoscope.com/us/horoscopes/general/horoscope-general-daily-tomorrow.aspx?sign=2",
     "sel": "div.main-horoscope p"},
    {"name": "Astrology.com",
     "url": "https://www.astrology.com/horoscope/daily/tomorrow/taurus.html",
     "sel": "#content p, #content span"},
    {"name": "AstroSage (Indian)",
     "url": "https://www.astrosage.com/horoscope/daily-taurus-horoscope.asp",
     "sel": ".ui-large-content"},
]

def grab(src):
    try:
        html = requests.get(src["url"], headers=UA, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        texts = [e.get_text(" ", strip=True) for e in soup.select(src["sel"])]
        texts = [t for t in texts if len(t) > 80]
        if not texts:  # fallback: longest real paragraph on the page
            texts = sorted((p.get_text(" ", strip=True) for p in soup.find_all("p")), key=len, reverse=True)[:1]
            texts = [t for t in texts if len(t) > 80]
        if not texts:
            return {**src, "ok": False}
        text = texts[0]
        m = re.match(r"^([A-Z][a-z]{2} \d{1,2}, \d{4})\s*-\s*", text)  # e.g. "Sep 24, 2026 - "
        return {"name": src["name"], "url": src["url"], "ok": True,
                "source_date": m.group(1) if m else None,
                "text": text[m.end():] if m else text}
    except Exception as e:
        return {"name": src["name"], "url": src["url"], "ok": False, "error": str(e)[:120]}

now = datetime.datetime.now(IST)
out = {"sign": "Taurus", "date_ist": now.strftime("%A, %d %B %Y"),
       "fetched_ist": now.strftime("%d %b %Y, %I:%M %p IST"),
       "sources": [grab(s) for s in SOURCES]}
json.dump(out, open("today.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
