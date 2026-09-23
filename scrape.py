"""Fetch today's Taurus horoscope from real sites and sort their sentences.
Every line shown on the page is verbatim from a source. Nothing is generated."""
import json, re, datetime, requests
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

IST = ZoneInfo("Asia/Kolkata")
UA = {"User-Agent": "Mozilla/5.0 (personal daily horoscope page)"}
# US sites publish on US time. Pick whichever of their pages matches India's date right now,
# so the page is correct no matter when (or how late) the job runs.
NOW_IST = datetime.datetime.now(IST)
NOW_US = datetime.datetime.now(ZoneInfo("America/New_York"))
US_DAY = "today" if NOW_US.date() == NOW_IST.date() else "tomorrow"
IST_LABEL = f"{NOW_IST:%b} {NOW_IST.day}, {NOW_IST.year}"          # e.g. "Sep 24, 2026"
HC = "https://www.horoscope.com/us/horoscopes/{c}/horoscope-{c}-daily-" + US_DAY + ".aspx?sign=2"

SOURCES = [
    {"name": "Horoscope.com", "url": HC.format(c="general"), "sel": "div.main-horoscope p"},
    {"name": "Astrology.com", "url": "https://www.astrology.com/horoscope/daily/" + ("tomorrow/" if US_DAY == "tomorrow" else "") + "taurus.html",
     "sel": "#content p, #content span"},
    {"name": "AstroSage", "url": "https://www.astrosage.com/horoscope/daily-taurus-horoscope.asp",
     "sel": ".ui-large-content"},
]
TOPIC_PAGES = {"love": HC.format(c="love"), "career": HC.format(c="career"),
               "money": HC.format(c="money"), "health": HC.format(c="wellness")}

def fetch(url, sel):
    """Return (text, source_date, full_page_text) or (None, None, None)."""
    try:
        soup = BeautifulSoup(requests.get(url, headers=UA, timeout=20).text, "html.parser")
        texts = [e.get_text(" ", strip=True) for e in soup.select(sel)]
        texts = [t for t in texts if len(t) > 80] or \
                [t for t in sorted((p.get_text(" ", strip=True) for p in soup.find_all("p")), key=len, reverse=True)[:1] if len(t) > 80]
        if not texts:
            return None, None, None
        text = texts[0]
        m = re.match(r"^([A-Z][a-z]{2} \d{1,2}, \d{4})\s*-\s*", text)
        return (text[m.end():] if m else text), (m.group(1) if m else None), soup.get_text(" ", strip=True)
    except Exception:
        return None, None, None

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text) if len(s.strip()) > 20]

def has(s, words):
    s = s.lower()
    return any(re.search(r"\b" + re.escape(w), s) for w in words)

TODO_START = ("be ", "head ", "keep ", "take ", "make ", "try ", "let ", "find ", "trust ", "go ", "give ",
              "avoid ", "focus ", "spend ", "invite ", "stay ", "get ", "start ", "reach ", "remember ",
              "listen ", "treat ", "plan ", "say ", "ask ", "call ", "share ", "enjoy ", "don't ", "do ",
              "before you", "use ", "put ", "set ", "tell ", "slow ", "pay ", "watch ", "consider ", "allow ")
TODO_WORDS = ["all you need is", "you need to", "you should", "make sure", "it's best to", "it's wise to", "you'd do well"]
CAUTION = ["avoid", "careful", "keep an eye", "problem", "difficult", "resist", "beware", "tension",
           "mood swing", "conflict", "stress", "mistake", "delay", "doomscroll", "argument", "trouble",
           "caution", "hard ", "tough", "frustrat", "worry", "loss", "overspend", "impulsive", "drain",
           "not always", "won't provide", "setback", "challeng"]
GOOD = ["love", "luck", "perfect", "grow", "better", "success", "romantic", "confiden", "opportunit",
        "help", "strong", "good", "happ", "joy", "bode well", "special", "charm", "bless", "gain",
        "advance", "shower", "reward", "win", "bright", "fulfil", "comfort", "chemistry", "remember this"]
TOPICS = {
    "love": ["love", "romanc", "romantic", "partner", "spouse", "sweetheart", "heart", "crush", "cupid",
             "date", "dating", "relationship", "married", "chemistry", "flirt", "soulmate"],
    "career": ["career", "work", "job", "boss", "business", "colleague", "project", "advancement",
               "office", "professional", "promotion", "deadline"],
    "money": ["money", "spend", "spent", "finan", "income", "invest", "budget", "cash", "wealth", "expense"],
    "health": ["health", "energy", "body", "rest", "sleep", "stress", "wellness", "mood", "outside",
               "nature", "breathe", "exercise", "screen time", "doomscroll"],
}

def bucket(s):
    if s.lower().startswith(TODO_START) or has(s, TODO_WORDS):
        return "todo"
    if has(s, CAUTION):
        return "heads"
    if has(s, GOOD):
        return "good"
    return None


GS_URL = "https://www.ganeshaspeaks.com/horoscopes/daily-horoscope/taurus/"
GS_AREAS = {"love": "daily-love-and-relationship-horoscope", "health": "daily-health-and-well-being-horoscope",
            "money": "daily-money-and-finance-horoscope", "career": "daily-career-and-business-horoscope"}

def ganesha():
    """Main reading (all paragraphs), date, lucky number/colour, and the 4 area readings."""
    res = {"name": "GaneshaSpeaks", "url": GS_URL, "ok": False, "source_date": None, "text": None,
           "lucky": {}, "areas": {}}
    try:
        soup = BeautifulSoup(requests.get(GS_URL, headers=UA, timeout=20).text, "html.parser")
        h2 = next((h for h in soup.find_all(["h2", "h1"]) if "Horoscope Today" in h.get_text()), None)
        paras = []
        if h2:
            for el in h2.find_all_next(["p", "h3", "div"]):
                t = el.get_text(" ", strip=True)
                if el.name == "h3" or "Areas of Life" in t:
                    break
                if el.name != "p" or not t:
                    continue
                if re.fullmatch(r"\d{2}-\d{2}-\d{4}", t):
                    res["source_date"] = t
                    continue
                m = re.match(r"Lucky Colou?r\s*(.+)", t, re.I)
                if m: res["lucky"]["color"] = m.group(1).strip(); continue
                m = re.match(r"Lucky Number\s*(.+)", t, re.I)
                if m: res["lucky"]["number"] = m.group(1).strip(); continue
                paras.append(t)
        page = soup.get_text(" ", strip=True)  # lucky fallback if they aren't in <p>
        for key, pat in (("number", r"Lucky Number\s*[:\-]?\s*(\d+)"), ("color", r"Lucky Colou?r\s*[:\-]?\s*([A-Za-z ]+?)(?=\s{1,}(?:Today|Lucky|$))")):
            if key not in res["lucky"]:
                m = re.search(pat, page)
                if m: res["lucky"][key] = m.group(1).strip()
        if paras:
            res["text"] = " ".join(paras); res["ok"] = True
        for topic, slug in GS_AREAS.items():
            a = next((a for a in soup.find_all("a", href=True)
                      if slug + "/taurus" in a["href"] and "read more" not in a.get_text(" ", strip=True).lower()), None)
            if a:
                nxt = a.find_next("p")
                t = nxt.get_text(" ", strip=True) if nxt else ""
                if len(t) > 40:
                    res["areas"][topic] = {"text": t, "url": "https://www.ganeshaspeaks.com/horoscopes/" + slug + "/taurus/"}
    except Exception as e:
        res["error"] = str(e)[:120]
    return res

now = NOW_IST
out = {"sign": "Taurus", "date_ist": now.strftime("%A, %d %B %Y"), "date_key": now.strftime("%Y-%m-%d"),
       "fetched_ist": now.strftime("%d %b %Y, %I:%M %p IST"),
       "sources": [], "glance": {"good": [], "heads": [], "todo": []},
       "topics": {k: {"readings": [], "bits": []} for k in TOPICS}, "lucky": {}}

g = ganesha()
out["sources"].append({k: g[k] for k in ("name", "url", "ok", "source_date", "text")})
out["lucky"].update(g["lucky"])
for topic, r in g["areas"].items():
    out["topics"][topic]["readings"].append({**r, "src": "GaneshaSpeaks"})
if g["ok"]:
    for s in sentences(g["text"]):
        b = bucket(s)
        if b:
            out["glance"][b].append({"t": s, "src": "GaneshaSpeaks"})
        for topic, words in TOPICS.items():
            if has(s, words):
                out["topics"][topic]["bits"].append({"t": s, "src": "GaneshaSpeaks"})

def other_day(url):
    return url.replace("daily-today", "daily-TMP").replace("daily-tomorrow", "daily-today").replace("daily-TMP", "daily-tomorrow")

for src in SOURCES:
    text, date, page = fetch(src["url"], src["sel"])
    if date and date != IST_LABEL and "horoscope.com" in src["url"]:
        alt = other_day(src["url"])
        t2, d2, p2 = fetch(alt, src["sel"])
        if d2 == IST_LABEL:
            text, date, page, src = t2, d2, p2, {**src, "url": alt}
        else:
            text = None  # never show a different day's horoscope
    out["sources"].append({"name": src["name"], "url": src["url"], "ok": bool(text),
                           "source_date": date, "text": text})
    if not text:
        continue
    for s in sentences(text):
        b = bucket(s)
        if b:
            out["glance"][b].append({"t": s, "src": src["name"]})
        for topic, words in TOPICS.items():
            if has(s, words):
                out["topics"][topic]["bits"].append({"t": s, "src": src["name"]})
    if src["name"] == "AstroSage" and page:  # only if AstroSage actually prints these
        for key, label in (("number", "Lucky Number"), ("color", "Lucky Colou?r"), ("remedy", "Remedy")):
            m = re.search(label + r"\s*[:\-]+\s*([^.|]{1,80}?)(?=\s+(?:Lucky|Remedy|$)|\.)", page, re.I)
            if m and key not in out["lucky"]:
                out["lucky"][key] = m.group(1).strip()

for topic, url in TOPIC_PAGES.items():
    text, date, _ = fetch(url, "div.main-horoscope p")
    if text:
        out["topics"][topic]["readings"].append({"text": text, "url": url, "src": "Horoscope.com"})

json.dump(out, open("today.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
