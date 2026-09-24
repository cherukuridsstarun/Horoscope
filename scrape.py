"""Daily Taurus page data. Every line shown is verbatim from a source site; nothing is generated.
Each dated source is checked against India's date so the page never shows the wrong day."""
import json, re, math, datetime, requests, ephem
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

IST = ZoneInfo("Asia/Kolkata")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-IN,en;q=0.9"}
NOW = datetime.datetime.now(IST)
TODAY = NOW.date()
US_DAY = "today" if datetime.datetime.now(ZoneInfo("America/New_York")).date() == TODAY else "tomorrow"

def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if not r.ok:
            print(f"  ! {url} -> HTTP {getattr(r, 'status_code', '?')}")
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  ! {url} -> {type(e).__name__}")
        return None

def txt(el):
    return el.get_text(" ", strip=True) if el else ""

def parse_date(s):
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d-%m-%Y", "%A, %B %d, %Y", "%a, %d %b %Y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None

# ---------------- GaneshaSpeaks (Indian) ----------------
GS = "https://www.ganeshaspeaks.com/horoscopes/"
GS_AREAS = {"health": "daily-health-and-well-being-horoscope",
            "money": "daily-money-and-finance-horoscope", "career": "daily-career-and-business-horoscope"}

def ganesha():
    url = GS + "daily-horoscope/taurus/"
    res = {"name": "GaneshaSpeaks", "url": url, "ok": False, "source_date": None, "text": None, "lucky": {}, "areas": {}}
    soup = get(url)
    if not soup:
        return res
    h = next((h for h in soup.find_all(["h2", "h1"]) if "Horoscope Today" in txt(h)), None)
    paras = []
    if h:
        for el in h.find_all_next(["p", "h3"]):
            t = txt(el)
            if el.name == "h3" or "Areas of Life" in t:
                break
            if not t:
                continue
            if re.fullmatch(r"\d{2}-\d{2}-\d{4}", t):
                res["source_date"] = t; continue
            m = re.match(r"Lucky Colou?r\s*(.+)", t, re.I)
            if m: res["lucky"]["color"] = m.group(1).strip(); continue
            m = re.match(r"Lucky Number\s*(.+)", t, re.I)
            if m: res["lucky"]["number"] = m.group(1).strip(); continue
            if t not in paras:
                paras.append(t)
    d = parse_date(res["source_date"] or "")
    if d and d != TODAY:
        return res  # wrong day: show nothing rather than something stale
    if paras:
        seen, keep = set(), []
        for s in re.split(r"(?<=[.!?])\s+", " ".join(paras)):
            k = s.strip().lower()
            if k and k not in seen:
                seen.add(k); keep.append(s.strip())
        res["text"], res["ok"] = " ".join(keep), True
    for topic, slug in GS_AREAS.items():
        a = next((a for a in soup.find_all("a", href=True)
                  if slug + "/taurus" in a["href"] and "read more" not in txt(a).lower()), None)
        t = txt(a.find_next("p")) if a else ""
        if len(t) > 40:
            res["areas"][topic] = {"text": t, "url": GS + slug + "/taurus/", "src": "GaneshaSpeaks"}
    return res

# ---------------- Horoscope.com ----------------
HC = "https://www.horoscope.com/us/horoscopes/{c}/horoscope-{c}-daily-{d}.aspx?sign=2"

def hc_reading(c):
    """Try the page matching India's date; verify the printed date."""
    for day in (US_DAY, "tomorrow" if US_DAY == "today" else "today"):
        url = HC.format(c=c, d=day)
        soup = get(url)
        p = soup.select_one("div.main-horoscope p") if soup else None
        t = txt(p)
        m = re.match(r"^([A-Z][a-z]{2} \d{1,2}, \d{4})\s*-\s*", t)
        if m and parse_date(m.group(1)) == TODAY:
            return {"text": t[m.end():], "date": m.group(1), "url": url}
    return None

# ---------------- Astrology.com ----------------
AC = "https://www.astrology.com/horoscope/{kind}/" + ("tomorrow/" if US_DAY == "tomorrow" else "") + "taurus.html"

def ac_page(kind):
    url = AC.format(kind=kind)
    soup = get(url)
    if not soup:
        return None, url
    date_h = next((h for h in soup.find_all(["h4", "h3", "span"]) if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", txt(h))), None)
    if not date_h or parse_date(txt(date_h)) != TODAY:
        return None, url
    return soup, url

def ac_main(soup):
    ps = [txt(p) for p in soup.select("#content p, #content span")]
    ps = [t for t in ps if len(t) > 80]
    return ps[0] if ps else None

def ac_extras(soup):
    out = []
    for label in ("Bonus",):
        h = next((h for h in soup.find_all(["h4", "h3", "h5"]) if txt(h).startswith(f"Daily {label} ")), None)
        if not h:
            continue
        t = txt(h.find_next_sibling())
        if len(t) < 20 and h.parent:  # text sits in the same container as the heading
            t = txt(h.parent).replace(txt(h), "", 1).strip()
        if 20 < len(t) < 600 and not t.startswith("Daily "):
            out.append({"title": label, "text": t, "src": "Astrology.com"})
    texts = [x["text"] for x in out]
    return [x for x in out if texts.count(x["text"]) == 1]  # identical text under different headings = wrong grab

# ---------------- AstroSage (Indian) ----------------
AS_TODAY = "https://www.astrosage.com/horoscope/daily-taurus-horoscope.asp"
AS_TOMORROW = "https://www.astrosage.com/horoscope/taurus-tomorrow-horoscope.asp?ref=tomorrow"
RATING_LABELS = ["Health", "Wealth", "Family", "Love Matters", "Occupation", "Married Life"]

def astrosage():
    for url in (AS_TODAY, AS_TOMORROW):
        soup = get(url)
        if not soup:
            continue
        page = soup.get_text(" ", strip=True)
        m = re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), ([A-Z][a-z]+ \d{1,2}, \d{4})", page)
        date = m.group(0) if m else None
        if not date or parse_date(m.group(2)) != TODAY:
            continue
        main = [txt(e) for e in soup.select(".ui-large-content")]
        main = [t for t in main if len(t) > 80]
        text = main[0] if main else None
        if text:
            text = re.split(r"\s*To get your accurate horoscope", text)[0]
        lucky, ratings = {}, []
        if url != AS_TODAY:
            # the tomorrow page's rating/lucky block still belongs to the previous day, so skip it
            return {"name": "AstroSage", "url": url, "ok": bool(text), "source_date": date, "text": text,
                    "lucky": {}, "ratings": []}
        for key, pat in (("number", r"Lucky Number\s*:-\s*(\d[\d ,]*)"),
                         ("color", r"Lucky Colou?r\s*:-\s*(.+?)\s+Remedy"),
                         ("remedy", r"Remedy\s*:-\s*(.+?)\s+Today.s Rating")):
            mm = re.search(pat, page)
            if mm:
                lucky[key] = mm.group(1).strip()
        for b in soup.find_all(["b", "strong"]):
            label = txt(b).rstrip(":").strip()
            if label in RATING_LABELS and label not in [r["label"] for r in ratings]:
                stars, sib = 0, b.next_sibling
                while sib is not None and getattr(sib, "name", None) not in ("b", "strong"):
                    for img in ([sib] if getattr(sib, "name", None) == "img" else (sib.find_all("img") if hasattr(sib, "find_all") else [])):
                        if "star2" in img.get("src", ""):
                            stars += 1
                    sib = sib.next_sibling
                ratings.append({"label": label.replace(" Matters", ""), "stars": stars})
        if ratings and not any(r["stars"] for r in ratings):
            ratings = []
        return {"name": "AstroSage", "url": url, "ok": bool(text), "source_date": date, "text": text,
                "lucky": lucky, "ratings": ratings}
    return {"name": "AstroSage", "url": AS_TODAY, "ok": False, "source_date": None, "text": None, "lucky": {}, "ratings": []}


# ---------------- Gold rates (Hyderabad + national benchmark) ----------------
def num(s):
    return int(re.sub(r"[^\d]", "", s)) if s and re.search(r"\d", s) else None

def gold_goodreturns():
    url = "https://www.goodreturns.in/gold-rates/hyderabad.html"
    soup = get(url)
    if not soup:
        return None, []
    t = soup.get_text(" ", strip=True)
    m = re.search(r"stands at ₹\s*([\d,]+) per gram for 24 karat.*?₹\s*([\d,]+) per gram for 22 karat", t)
    d = re.search(r"Gold Price on (\d{1,2} [A-Z][a-z]+ \d{4})", txt(soup.title)) or re.search(r"(\d{1,2} [A-Z][a-z]+ \d{4})", t)
    hist = re.findall(r"([A-Z][a-z]{2} \d{1,2}, \d{4})\s*₹\s*([\d,]+)\s*\(\s*([+-]?[\d,]+)\s*\)\s*₹\s*([\d,]+)\s*\(\s*([+-]?[\d,]+)\s*\)", t)
    trend = []
    for dt, k24, c24, k22, c22 in hist[:10]:
        if dt not in [x["date"] for x in trend]:
            trend.append({"date": dt, "k22": num(k22), "k24": num(k24)})
    if not m:
        return None, trend
    ch = None
    if hist:
        ch = int(hist[0][4].replace(",", "").replace("+", "")) if hist[0][4] else None
    return {"src": "GoodReturns", "label": "Hyderabad jewellers", "k24": num(m.group(1)), "k22": num(m.group(2)),
            "change22": ch, "date": d.group(1) if d else None, "url": url}, list(reversed(trend))

def gold_policybazaar():
    url = "https://www.policybazaar.com/gold-rate/hyderabad/"
    soup = get(url)
    if not soup:
        return None
    t = soup.get_text(" ", strip=True)
    m = re.search(r"Rs\.?\s*([\d,]+) per gram for 22 karat gold and Rs\.?\s*([\d,]+) per gram for 24 karat gold today \(as on (\d{1,2} [A-Z][a-z]+ \d{4})\)", t)
    if m:
        k22, k24, date = m.group(1), m.group(2), m.group(3)
    else:
        a = re.search(r"22 karat gold rate in Hyderabad is Rs\.?\s*([\d,]+) per gram today (\d{1,2} [A-Z][a-z]+ \d{4})", t)
        b = re.search(r"price for 24 karat gold in Hyderabad is Rs\.?\s*([\d,]+) per gram", t)
        if not (a and b):
            print("  ! PolicyBazaar: page loaded but rate sentence not found")
            return None
        k22, date, k24 = a.group(1), a.group(2), b.group(1)
    return {"src": "PolicyBazaar", "label": "Hyderabad retail", "k22": num(k22), "k24": num(k24),
            "change22": None, "date": date, "url": url}

def gold_ibja():
    url = "https://ibjarates.com/"
    soup = get(url)
    if not soup:
        return None
    t = soup.get_text(" ", strip=True)
    k24 = re.search(r"999 Purity\s*([\d,]+)\s*\(1 Gram\)", t)
    k22 = re.search(r"916 Purity\s*([\d,]+)\s*\(1 Gram\)", t)
    if not (k24 and k22):
        return None
    top = num(k24.group(1))
    # history rows look like: 22/09/2026 152132 151523 139353 ... (999 per 10 g first)
    rows = re.findall(r"(\d{2}/\d{2}/\d{4})\s+(\d{5,7})", t)
    date = None
    for d, v in rows:
        if abs(round(int(v) / 10) - top) <= 1:          # headline = a published past rate
            date = d; break
    if date is None and rows and NOW.weekday() < 5:    # headline is newer than every past row = today's rate
        date = NOW.strftime("%d/%m/%Y")
    if date is None:
        return None                                    # can't tell which day it is -> don't show it
    date = datetime.datetime.strptime(date, "%d/%m/%Y").strftime("%d %B %Y").lstrip("0")
    return {"src": "IBJA", "label": "India benchmark (wholesale)", "k22": num(k22.group(1)), "k24": top,
            "change22": None, "date": date, "url": url}

def purity_check(r):
    """Real 24K/22K is 999/916 = 1.09. If a source's pair is far off, its 24K is a different product."""
    if r["k22"] and r["k24"] and not (1.075 <= r["k24"] / r["k22"] <= 1.105):
        r["k24"] = None
        r["label"] += " · 22K only"
    return r


# ================= Her city (weather + Panchang are calculated for this place) =================
CITY, LAT, LON = "Hyderabad", 17.3850, 78.4867
PLACES = [  # weather is fetched for each of these; coordinates rounded to ~1 km and no place names, since the repo is public
    {"key": "home",   "name": "Home",   "area": "", "lat": 17.47, "lon": 78.57},
    {"key": "office", "name": "Office", "area": "", "lat": 17.44, "lon": 78.38},
]
PERIODS = [("Morning", 6, 12), ("Afternoon", 12, 17), ("Evening", 17, 21), ("Night", 21, 30)]  # IST hours; night runs to 6 AM

# ---------------- Panchang (astronomical calculation, Lahiri ayanamsa, IST) ----------------
TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami",
          "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
NAKS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
        "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
        "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
        "Uttara Bhadrapada", "Revati"]
RAHU_SEG = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}   # Mon..Sun: which 1/8th of daytime is Rahu Kaal
UTC = datetime.timezone.utc

def _lon(body, t):
    body.compute(ephem.Date(t))
    return math.degrees(ephem.Ecliptic(body, epoch=ephem.Date(t)).lon)

def _lahiri(t):
    return 23.85306 + (ephem.Date(t) - ephem.Date("2000/1/1 12:00")) / 365.25 * 50.2388475 / 3600

def _tithi(t):
    return int(((_lon(ephem.Moon(), t) - _lon(ephem.Sun(), t)) % 360) // 12)

def _nak(t):
    return int(((_lon(ephem.Moon(), t) - _lahiri(t)) % 360) // (360 / 27))

def _next_change(fn, start):
    v0, t, step = fn(start), start, datetime.timedelta(minutes=30)
    for _ in range(96):
        t2 = t + step
        if fn(t2) != v0:
            lo, hi = t, t2
            while hi - lo > datetime.timedelta(seconds=30):
                mid = lo + (hi - lo) / 2
                lo, hi = (mid, hi) if fn(mid) == v0 else (lo, mid)
            return hi
        t = t2
    return None

def _tithi_name(i):
    return ("Shukla " if i < 15 else "Krishna ") + ("Purnima" if i == 14 else "Amavasya" if i == 29 else TITHIS[i % 15])

def panchang_for(day):
    obs = ephem.Observer(); obs.lat, obs.lon, obs.elevation = str(LAT), str(LON), 500
    obs.pressure, obs.horizon = 0, "-0:50"     # upper limb + refraction, the Indian panchang convention
    start = datetime.datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(UTC).replace(tzinfo=None)
    obs.date = ephem.Date(start)
    rise = obs.next_rising(ephem.Sun()).datetime()
    obs.date = ephem.Date(rise)
    sset = obs.next_setting(ephem.Sun()).datetime()
    ist = lambda t: t.replace(tzinfo=UTC).astimezone(IST)
    hm = lambda t: ist(t).strftime("%I:%M %p").lstrip("0")
    when = lambda t: hm(t) + ("" if ist(t).date() == day else ", " + ist(t).strftime("%d %b").lstrip("0"))
    ti, ni = _tithi(rise), _nak(rise)
    tend, nend = _next_change(_tithi, rise), _next_change(_nak, rise)
    part = (sset - rise) / 8
    rk_s = rise + part * (RAHU_SEG[day.weekday()] - 1); rk_e = rk_s + part
    return {"city": CITY, "date": day.isoformat(),
            "sunrise": hm(rise), "sunset": hm(sset),
            "sunrise_iso": ist(rise).isoformat(timespec="minutes"), "sunset_iso": ist(sset).isoformat(timespec="minutes"),
            "tithi": _tithi_name(ti), "tithi_until": when(tend), "tithi_next": _tithi_name((ti + 1) % 30),
            "nakshatra": NAKS[ni], "nak_until": when(nend), "nak_next": NAKS[(ni + 1) % 27],
            "paksha": "Shukla Paksha · waxing moon" if ti < 15 else "Krishna Paksha · waning moon",
            "rahu": f"{hm(rk_s)} to {hm(rk_e)}",
            "rahu_start": ist(rk_s).isoformat(timespec="minutes"), "rahu_end": ist(rk_e).isoformat(timespec="minutes"),
            "_tithi_rise": ti, "_tithi_set": _tithi(sset)}

# ---------------- Festivals & holidays ----------------
# 2026 dates from the official Telangana High Court notification (ROC No. 2083/SO/2025, 11-12-2025),
# general + optional holidays. * = date depends on moon sighting. Add a 2027 block when it's published.
FESTIVALS = {
 "2026-01-01": "New Year's Day", "2026-01-03": "Birthday of Hazrath Ali (R.A.)*", "2026-01-13": "Bhogi",
 "2026-01-14": "Sankranti / Pongal", "2026-01-15": "Kanumu", "2026-01-17": "Shab-e-Meraj*", "2026-01-23": "Sri Panchami",
 "2026-01-26": "Republic Day", "2026-02-04": "Shab-e-Barat*", "2026-02-15": "Maha Shivaratri", "2026-03-04": "Holi",
 "2026-03-10": "Shahadat Hazrat Ali (R.A.)*", "2026-03-13": "Jumu'atul Wida*", "2026-03-17": "Shab-e-Qadr*",
 "2026-03-19": "Ugadi · Telugu New Year", "2026-03-21": "Ramzan (Eid-ul-Fitr)*", "2026-03-27": "Sri Rama Navami",
 "2026-03-31": "Mahaveer Jayanthi", "2026-04-03": "Good Friday", "2026-04-05": "Babu Jagjivan Ram's Birthday",
 "2026-04-14": "Dr. B.R. Ambedkar's Birthday", "2026-04-20": "Basava Jayanthi", "2026-05-01": "Buddha Purnima",
 "2026-05-27": "Bakrid (Eid-ul-Adha)*", "2026-06-04": "Eid-e-Ghadeer*", "2026-06-25": "9th Muharram*",
 "2026-06-26": "Muharram*", "2026-07-16": "Ratha Yathra", "2026-08-04": "Arbaeen*", "2026-08-10": "Bonalu",
 "2026-08-15": "Independence Day", "2026-08-26": "Eid Milad-un-Nabi*", "2026-08-28": "Raksha Bandhan · Varalakshmi Vratham",
 "2026-09-04": "Sri Krishna Ashtami", "2026-09-14": "Vinayaka Chavithi", "2026-09-23": "Yaz Dahum Shareef*",
 "2026-10-02": "Gandhi Jayanthi", "2026-10-11": "Bathukamma begins", "2026-10-19": "Durgashtami · Maha Navami",
 "2026-10-20": "Vijaya Dasami · Dussehra", "2026-10-26": "Birthday of Hazrat Syed Mohammed Juvanpuri Mahdi*",
 "2026-11-07": "Naraka Chaturdashi", "2026-11-08": "Deepavali", "2026-11-24": "Karthika Purnima · Guru Nanak Jayanthi",
 "2026-12-24": "Christmas Eve", "2026-12-25": "Christmas",
}

def observances(p):
    """Monthly tithi-based observances, from the calculated Panchang."""
    out, tr, ts = [], p["_tithi_rise"], p["_tithi_set"]
    if tr % 15 == 10: out.append("Ekadashi")
    if ts % 15 == 12: out.append("Pradosh Vrat")
    if tr == 14: out.append("Purnima · full moon")
    if tr == 29: out.append("Amavasya · new moon")
    return out

def festivals_block(today):
    todays = []
    if today.isoformat() in FESTIVALS:
        todays.append({"name": FESTIVALS[today.isoformat()].rstrip("*"), "moon": FESTIVALS[today.isoformat()].endswith("*"), "kind": "festival"})
    upcoming = None
    for i in range(1, 46):
        d = today + datetime.timedelta(days=i)
        if d.isoformat() in FESTIVALS:
            n = FESTIVALS[d.isoformat()]
            upcoming = {"name": n.rstrip("*"), "moon": n.endswith("*"), "date": d.isoformat(),
                        "label": d.strftime("%a, %d %b").replace(" 0", " "), "days": i}
            break
    if not any(k.startswith(str(today.year)) for k in FESTIVALS):
        print(f"  ! festival list has no {today.year} dates yet; add them to FESTIVALS")
    return {"today": todays, "next": upcoming}

# ---------------- Weather (Open-Meteo, free, no key; dates in IST) ----------------
WMO = {0: ("Clear sky", "☀️"), 1: ("Mostly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Cloudy", "☁️"),
       45: ("Fog", "🌫️"), 48: ("Fog", "🌫️"), 51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
       56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"), 61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"),
       65: ("Heavy rain", "🌧️"), 66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"), 71: ("Light snow", "🌨️"),
       73: ("Snow", "🌨️"), 75: ("Heavy snow", "🌨️"), 77: ("Snow grains", "🌨️"), 80: ("Light showers", "🌦️"),
       81: ("Showers", "🌧️"), 82: ("Heavy showers", "⛈️"), 85: ("Snow showers", "🌨️"), 86: ("Snow showers", "🌨️"),
       95: ("Thunderstorms", "⛈️"), 96: ("Thunderstorms with hail", "⛈️"), 99: ("Thunderstorms with hail", "⛈️")}

def _wx(code):
    return WMO.get(code, ("", "🌡️"))

def weather_place(pl):
    r = requests.get("https://api.open-meteo.com/v1/forecast", headers=UA, timeout=20, params={
        "latitude": pl["lat"], "longitude": pl["lon"], "timezone": "Asia/Kolkata", "forecast_days": 2,
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"})
    if not r.ok:
        print(f"  ! weather {pl['key']} -> HTTP {r.status_code}")
        return None
    j = r.json(); d, h = j.get("daily", {}), j.get("hourly", {})
    if not d.get("time") or d["time"][0] != TODAY.isoformat():          # must be India's today
        print(f"  ! weather {pl['key']}: forecast date isn't today in India")
        return None
    hours = []                                                          # (hours since today 00:00 IST, temp, rain%, code)
    for t, temp, rain, code in zip(h.get("time", []), h.get("temperature_2m", []),
                                   h.get("precipitation_probability", []), h.get("weather_code", [])):
        dt = datetime.datetime.fromisoformat(t)
        off = (dt.date() - TODAY).days * 24 + dt.hour
        hours.append((off, temp, rain, code))
    periods = []
    for name, a, b in PERIODS:
        hs = [x for x in hours if a <= x[0] < b and x[1] is not None]
        if not hs:
            continue
        code = max(x[3] for x in hs if x[3] is not None)                   # the most significant weather in that window
        rains = [x[2] for x in hs if x[2] is not None]
        lab, icon = _wx(code)
        if name == "Night" and code in (0, 1):
            icon = "🌙"
        periods.append({"name": name, "from": a, "to": b, "icon": icon, "label": lab,
                        "temp": round(sum(x[1] for x in hs) / len(hs)), "rain": max(rains) if rains else None})
    c, now = j.get("current", {}), None
    if c.get("time", "").startswith(TODAY.isoformat()) and c.get("temperature_2m") is not None:
        ct = datetime.datetime.fromisoformat(c["time"])
        cl, ci = _wx(c.get("weather_code"))
        if not c.get("is_day", 1) and c.get("weather_code") in (0, 1):
            ci = "🌙"
        now = {"iso": c["time"], "time": ct.strftime("%I:%M %p").lstrip("0"), "hour": ct.hour + ct.minute / 60,
               "temp": round(c["temperature_2m"]), "feels": round(c["apparent_temperature"]),
               "humidity": c.get("relative_humidity_2m"), "label": cl, "icon": ci}
    lab, icon = _wx(d["weather_code"][0])
    return {"key": pl["key"], "name": pl["name"], "area": pl["area"], "label": lab, "icon": icon, "now": now,
            "high": round(d["temperature_2m_max"][0]), "low": round(d["temperature_2m_min"][0]),
            "rain": d.get("precipitation_probability_max", [None])[0], "uv": d.get("uv_index_max", [None])[0],
            "periods": periods}

# ---------------- sorting (verbatim sentences only) ----------------
def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text or "") if len(s.strip()) > 20]

def has(s, words):
    s = s.lower()
    return any(re.search(r"\b" + re.escape(w), s) for w in words)

TODO_START = ("be ", "head ", "keep ", "take ", "make ", "try ", "let ", "find ", "trust ", "go ", "give ",
              "avoid ", "focus ", "spend ", "invite ", "stay ", "get ", "start ", "reach ", "remember ",
              "listen ", "treat ", "plan ", "say ", "ask ", "call ", "share ", "enjoy ", "don't ", "do ",
              "before you", "use ", "put ", "set ", "tell ", "slow ", "pay ", "watch ", "consider ", "allow ",
              "exercise ", "carry ", "reach out")
TODO_WORDS = ["you are advised", "advises you", "suggests you", "you must", "you have to", "it is advisable",
              "all you need is", "you need to", "you should", "make sure", "it's best to", "it's wise to", "you'd do well",
              "are required to", "stay away from", "it is important to"]
CAUTION = ["avoid", "careful", "keep an eye", "problem", "difficult", "resist", "beware", "tension",
           "mood swing", "conflict", "stress", "mistake", "delay", "doomscroll", "argument", "trouble",
           "caution", "hard ", "tough", "frustrat", "worry", "loss", "overspend", "impulsive", "drain",
           "not always", "won't provide", "setback", "challeng", "blame", "get into a fix", "more than you can handle",
           "overdo", "uptight", "too many things", "lose your patience", "tense", "negative", "not be in favour",
           "vulnerable", "get hurt", "miss", "suffer", "bad habit"]
GOOD = ["love", "luck", "perfect", "grow", "better", "success", "romantic", "confiden", "opportunit",
        "help", "strong", "good", "happ", "joy", "bode well", "special", "charm", "bless", "gain",
        "advance", "shower", "reward", "win", "bright", "fulfil", "comfort", "chemistry", "remember this",
        "easy", "carefree", "no woes", "no worries", "favour", "favor", "auspicious", "smooth", "peace", "calm",
        "positive", "prosper", "optimistic", "satisf", "appreciat", "progress", "encourage", "best", "harmon"]
TOPICS = {
    "career": ["career", "work", "job", "boss", "business", "colleague", "project", "advancement",
               "office", "professional", "promotion", "deadline", "teamwork", "meeting"],
    "money": ["money", "spend", "spent", "finan", "income", "invest", "budget", "cash", "wealth", "expense", "deal"],
    "health": ["health", "energy", "body", "rest", "sleep", "stress", "wellness", "mood", "outside",
               "nature", "breathe", "exercise", "screen time", "doomscroll", "smoking", "habit", "tired"],
}

LOVE_WORDS = ["love", "lover", "romanc", "romantic", "relationship", "partner", "sweetheart", "beloved",
              "companion", "date", "dating", "crush", "cupid", "chemistry", "flirt", "soulmate", "single", "heart",
              "sex", "intimate", "intimacy", "boyfriend", "girlfriend", "valentine", "affection", "passion",
              "attraction", "admirer", "proposal", "courtship"]
MARRIAGE_WORDS = ["married", "marriage", "marital", "wedding", "husband", "wife", "spouse", "in-law", "in law",
                  "life partner", "better half", "matrimon"]

def no_love(text):
    """Remove dating/romance sentences but keep anything about marriage. Returns what's left (verbatim), or None."""
    if not text:
        return None
    keep = [s for s in re.split(r"(?<=[.!?])\s+", text.strip())
            if s and (has(s, MARRIAGE_WORDS) or not has(s, LOVE_WORDS))]
    t = " ".join(keep).strip()
    return t if len(t) > 10 else None

def bucket(s):
    if s.lower().startswith(TODO_START) or has(s, TODO_WORDS):
        return "todo"
    if has(s, CAUTION):
        return "heads"
    if has(s, GOOD):
        return "good"
    return None

# ---------------- build ----------------
def safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        print(f"  ! {fn.__name__}{args} crashed: {type(e).__name__}: {e}")
        return None

try:
    PREV = json.load(open("today.json"))
    PREV_RAW = PREV.get("_raw", {}) if PREV.get("date_key") == NOW.strftime("%Y-%m-%d") else {}
except Exception:
    PREV_RAW = {}

def keep(key, fresh, good):
    """Use the fresh result if it's good; otherwise fall back to earlier today's good result."""
    if good(fresh):
        return fresh
    old = PREV_RAW.get(key)
    if good(old):
        print(f"  ~ {key}: fetch failed now, kept this morning's copy")
        return old
    return fresh

ok_text = lambda r: bool(r and r.get("text"))
raw = {}
raw["ganesha"] = keep("ganesha", safe(ganesha), lambda r: bool(r and r.get("ok")))
raw["hc_general"] = keep("hc_general", safe(hc_reading, "general"), ok_text)
for cat in ("career", "wellness"):
    raw["hc_" + cat] = keep("hc_" + cat, safe(hc_reading, cat), ok_text)

def hc_money():
    url = "https://www.horoscope.com/us/horoscopes/money/horoscope-money-weekly.aspx?sign=2"
    wk = get(url)
    t = txt(wk.select_one("div.main-horoscope p")) if wk else ""
    t = re.sub(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}\s*-\s*[A-Z][a-z]{2} \d{1,2}, \d{4}\s*-\s*", "", t)
    return {"text": t, "url": url} if len(t) > 60 else None
raw["hc_money"] = keep("hc_money", safe(hc_money), ok_text)

def astrology_daily():
    soup, url = ac_page("daily")
    text = ac_main(soup) if soup else None
    return {"text": text, "url": url, "extras": ac_extras(soup) if text else []} if text else {"text": None, "url": url, "extras": []}
def astrology_love():
    soup, url = ac_page("daily-love")
    text = ac_main(soup) if soup else None
    return {"text": text, "url": url} if text else None
raw["ac"] = keep("ac", safe(astrology_daily), ok_text)
raw["astrosage"] = keep("astrosage", safe(astrosage), lambda r: bool(r and r.get("ok")))

for pl in PLACES:
    raw["wx_" + pl["key"]] = keep("wx_" + pl["key"], safe(weather_place, pl), lambda r: bool(r and r.get("periods")))
    log = dict(PREV_RAW.get("wxlog_" + pl["key"], {}))          # {period name: reading}, today only
    n = (raw["wx_" + pl["key"]] or {}).get("now")
    if n:
        for name, a, b in PERIODS:
            if a <= n["hour"] < b:                                   # before 6 AM is last night, so it isn't logged
                if name not in log or log[name]["iso"] <= n["iso"]:
                    log[name] = {k: n[k] for k in ("iso", "time", "temp", "feels", "humidity", "label", "icon")}
    raw["wxlog_" + pl["key"]] = log
    if raw["wx_" + pl["key"]]:
        raw["wx_" + pl["key"]] = {**raw["wx_" + pl["key"]], "log": log}

# gold: each source independently, each keeps its own date
gr = safe(gold_goodreturns) or (None, [])
gold_rows = {"GoodReturns": gr[0], "PolicyBazaar": safe(gold_policybazaar), "IBJA": safe(gold_ibja)}
prev_gold = PREV_RAW.get("gold", {})
for k in gold_rows:
    if not gold_rows[k] and prev_gold.get("rows", {}).get(k):
        print(f"  ~ gold {k}: fetch failed now, kept this morning's copy")
        gold_rows[k] = prev_gold["rows"][k]
raw["gold"] = {"rows": gold_rows, "trend": gr[1] or prev_gold.get("trend", [])}

# ---- assemble the page data from raw
out = {"sign": "Taurus", "date_ist": NOW.strftime("%A, %d %B %Y"), "date_key": NOW.strftime("%Y-%m-%d"),
       "fetched_ist": NOW.strftime("%d %b %Y, %I:%M %p IST"), "sources": [],
       "glance": {"good": [], "heads": [], "todo": []},
       "topics": {k: {"readings": [], "bits": []} for k in TOPICS},
       "lucky": [], "ratings": None, "extras": [], "gold": None, "_raw": raw,
       "panchang": None, "festivals": None,
       "weather": {"date": TODAY.isoformat(), "places": [raw["wx_" + pl["key"]] for pl in PLACES if raw.get("wx_" + pl["key"])]}}
if not out["weather"]["places"]:
    out["weather"] = None

pc = safe(panchang_for, TODAY)
if pc:
    fest = festivals_block(TODAY)
    fest["today"] += [{"name": n, "moon": False, "kind": "tithi"} for n in observances(pc)]
    out["festivals"] = fest
    out["panchang"] = {k: v for k, v in pc.items() if not k.startswith("_")}
else:
    out["festivals"] = safe(festivals_block, TODAY)

def add_text(name, text):
    for s in sentences(no_love(text)):
        b = bucket(s)
        if b:
            out["glance"][b].append({"t": s, "src": name})
        for topic, words in TOPICS.items():
            if has(s, words):
                out["topics"][topic]["bits"].append({"t": s, "src": name})

g = raw["ganesha"] or {"name": "GaneshaSpeaks", "url": GS + "daily-horoscope/taurus/", "ok": False, "source_date": None, "text": None, "lucky": {}, "areas": {}}
out["sources"].append({k: g.get(k) for k in ("name", "url", "ok", "source_date", "text")})
if g.get("lucky"):
    out["lucky"].append({"src": "GaneshaSpeaks", **g["lucky"]})
for topic, r in (g.get("areas") or {}).items():
    out["topics"][topic]["readings"].append(r)
if g.get("ok"):
    add_text("GaneshaSpeaks", g["text"])

hc = raw["hc_general"]
out["sources"].append({"name": "Horoscope.com", "url": (hc or {}).get("url") or HC.format(c="general", d=US_DAY),
                       "ok": ok_text(hc), "source_date": (hc or {}).get("date"), "text": (hc or {}).get("text")})
if ok_text(hc):
    add_text("Horoscope.com", hc["text"])
for topic, cat in (("career", "career"), ("health", "wellness")):
    r = raw["hc_" + cat]
    if ok_text(r):
        out["topics"][topic]["readings"].append({"text": r["text"], "url": r["url"], "src": "Horoscope.com"})
if ok_text(raw["hc_money"]):
    out["topics"]["money"]["readings"].append({**raw["hc_money"], "src": "Horoscope.com · this week"})

ac = raw["ac"] or {"text": None, "url": AC.format(kind="daily"), "extras": []}
out["sources"].append({"name": "Astrology.com", "url": ac["url"], "ok": ok_text(ac),
                       "source_date": NOW.strftime("%B %d, %Y").replace(" 0", " ") if ok_text(ac) else None, "text": ac["text"]})
if ok_text(ac):
    add_text("Astrology.com", ac["text"])
    out["extras"] = ac.get("extras") or []

a = raw["astrosage"] or {"name": "AstroSage", "url": AS_TODAY, "ok": False, "source_date": None, "text": None, "lucky": {}, "ratings": []}
out["sources"].append({k: a.get(k) for k in ("name", "url", "ok", "source_date", "text")})
if a.get("ok"):
    add_text("AstroSage", a["text"])
if a.get("lucky"):
    out["lucky"].append({"src": "AstroSage", **a["lucky"]})
if a.get("ratings"):
    out["ratings"] = {"src": "AstroSage", "items": a["ratings"]}

rows = [purity_check(dict(r)) for r in raw["gold"]["rows"].values() if r and r.get("k22")]
if len(rows) >= 3:  # drop any source more than 10% away from the others on 22K
    med = sorted(r["k22"] for r in rows)[len(rows) // 2]
    rows = [r for r in rows if abs(r["k22"] - med) / med <= 0.10]
out["gold"] = {"city": "Hyderabad", "rows": rows, "trend": raw["gold"]["trend"]} if rows else None

def dedupe(lst):
    seen, res = set(), []
    for x in lst:
        k = (x.get("t") or x.get("text", "")).strip().lower()
        if k and k not in seen:
            seen.add(k); res.append(x)
    return res
# final love/relationship filter over everything shown
for s in out["sources"]:
    if s.get("text"):
        s["text"] = no_love(s["text"])
        s["ok"] = bool(s["text"]) and s["ok"]
for t in out["topics"].values():
    t["readings"] = [dict(r, text=no_love(r["text"])) for r in t["readings"] if no_love(r.get("text"))]
out["extras"] = [dict(e, text=no_love(e["text"])) for e in out["extras"] if no_love(e.get("text"))]
if out["ratings"]:
    out["ratings"]["items"] = [r for r in out["ratings"]["items"] if r["label"] != "Love"]
    if not out["ratings"]["items"]:
        out["ratings"] = None
for b in out["glance"]:
    out["glance"][b] = dedupe(out["glance"][b])
for t in out["topics"].values():
    t["bits"], t["readings"] = dedupe(t["bits"]), dedupe(t["readings"])

print("sources ok:", {s["name"]: s["ok"] for s in out["sources"]})
print("lucky:", out["lucky"])
print("gold:", [(r["src"], r["k22"], r["k24"], r["date"]) for r in (out["gold"] or {}).get("rows", [])])
print("ratings:", out["ratings"], "| extras:", [e["title"] for e in out["extras"]])
print("panchang:", {k: out["panchang"][k] for k in ("tithi", "tithi_until", "nakshatra", "sunrise", "sunset", "rahu")} if out["panchang"] else None)
print("weather:", [(w["name"], w["high"], w["low"], w["rain"], [(x["name"], x["temp"], x["rain"]) for x in w["periods"]]) for w in (out["weather"] or {}).get("places", [])])
print("weather now:", [(w["name"], (w.get("now") or {}).get("time"), (w.get("now") or {}).get("temp"), sorted(w.get("log", {}))) for w in (out["weather"] or {}).get("places", [])])
print("festivals:", out["festivals"])
json.dump(out, open("today.json", "w"), indent=2, ensure_ascii=False)
