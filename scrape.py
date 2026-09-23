"""Fetch today's Taurus horoscope from real sites and sort their sentences.
Every line shown on the page is verbatim from a source. Nothing is generated."""
import json, re, datetime, requests
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

IST = ZoneInfo("Asia/Kolkata")
UA = {"User-Agent": "Mozilla/5.0 (personal daily horoscope page)"}
# US sites run a day behind India at 6 AM IST, so their "tomorrow" page = her today.
HC = "https://www.horoscope.com/us/horoscopes/{c}/horoscope-{c}-daily-tomorrow.aspx?sign=2"

SOURCES = [
    {"name": "Horoscope.com", "url": HC.format(c="general"), "sel": "div.main-horoscope p"},
    {"name": "Astrology.com", "url": "https://www.astrology.com/horoscope/daily/tomorrow/taurus.html",
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

now = datetime.datetime.now(IST)
out = {"sign": "Taurus", "date_ist": now.strftime("%A, %d %B %Y"),
       "fetched_ist": now.strftime("%d %b %Y, %I:%M %p IST"),
       "sources": [], "glance": {"good": [], "heads": [], "todo": []},
       "topics": {k: {"reading": None, "bits": []} for k in TOPICS}, "lucky": {}}

for src in SOURCES:
    text, date, page = fetch(src["url"], src["sel"])
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
            if m:
                out["lucky"][key] = m.group(1).strip()

for topic, url in TOPIC_PAGES.items():
    text, date, _ = fetch(url, "div.main-horoscope p")
    if text:
        out["topics"][topic]["reading"] = {"text": text, "url": url, "src": "Horoscope.com"}

json.dump(out, open("today.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
