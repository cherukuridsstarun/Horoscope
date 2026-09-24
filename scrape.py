"""Daily Taurus page data. Every line shown is verbatim from a source site; nothing is generated.
Each dated source is checked against India's date so the page never shows the wrong day."""
import json, re, datetime, requests
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
GS_AREAS = {"love": "daily-love-and-relationship-horoscope", "health": "daily-health-and-well-being-horoscope",
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
    for label in ("Bonus", "Food", "Home"):
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
        "positive", "prosper", "optimistic", "satisf", "appreciat", "progress", "encourage"]
TOPICS = {
    "love": ["love", "romanc", "romantic", "partner", "spouse", "sweetheart", "heart", "crush", "cupid",
             "date", "dating", "relationship", "married", "chemistry", "flirt", "soulmate", "companion", "beloved"],
    "career": ["career", "work", "job", "boss", "business", "colleague", "project", "advancement",
               "office", "professional", "promotion", "deadline", "teamwork", "meeting"],
    "money": ["money", "spend", "spent", "finan", "income", "invest", "budget", "cash", "wealth", "expense", "deal"],
    "health": ["health", "energy", "body", "rest", "sleep", "stress", "wellness", "mood", "outside",
               "nature", "breathe", "exercise", "screen time", "doomscroll", "smoking", "habit", "tired"],
}

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
for cat in ("love", "career", "wellness"):
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
raw["ac_love"] = keep("ac_love", safe(astrology_love), ok_text)
raw["astrosage"] = keep("astrosage", safe(astrosage), lambda r: bool(r and r.get("ok")))

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
       "lucky": [], "ratings": None, "extras": [], "gold": None, "_raw": raw}

def add_text(name, text):
    for s in sentences(text):
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
for topic, cat in (("love", "love"), ("career", "career"), ("health", "wellness")):
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
if ok_text(raw["ac_love"]):
    out["topics"]["love"]["readings"].append({**raw["ac_love"], "src": "Astrology.com"})

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
for b in out["glance"]:
    out["glance"][b] = dedupe(out["glance"][b])
for t in out["topics"].values():
    t["bits"], t["readings"] = dedupe(t["bits"]), dedupe(t["readings"])

print("sources ok:", {s["name"]: s["ok"] for s in out["sources"]})
print("lucky:", out["lucky"])
print("gold:", [(r["src"], r["k22"], r["k24"], r["date"]) for r in (out["gold"] or {}).get("rows", [])])
print("ratings:", out["ratings"], "| extras:", [e["title"] for e in out["extras"]])
json.dump(out, open("today.json", "w"), indent=2, ensure_ascii=False)
