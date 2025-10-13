#!/usr/bin/env python3
# fetchpost_ultimate.py
# Ultimate single-file scraper + human-like tweet composer + poster (Hindi final tweets)
# Posting method unchanged: uses tweepy.Client.create_tweet(...)

import os
import re
import json
import time
import random
import html
import traceback
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
from googletrans import Translator
import tweepy

# ------------------------ Configuration ------------------------
# Files & directories
BASE_DIR = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(BASE_DIR, exist_ok=True)
MORNING_FILE = os.path.join(BASE_DIR, "morning.json")
EVENING_FILE = os.path.join(BASE_DIR, "evening.json")
IR_FILE = os.path.join(BASE_DIR, "international.json")
POSTED_FILE = os.path.join(BASE_DIR, "posted_today.json")

# Twitter credentials - posting method unchanged: client.create_tweet(...)
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")  # optional

# create Tweepy Client (we will use .create_tweet)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# HTTP session with retries
session = requests.Session()
retries = Retry(total=2, backoff_factor=0.8, status_forcelist=[429,500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; FetchPostBot/2.0; +https://example.com/bot)"
})

# translator
translator = Translator()

# scraping sources (English + Hindi)
DOMESTIC_SOURCES = [
    "https://www.ndtv.com/latest",
    "https://www.indiatoday.in/",
    "https://www.abplive.com/news",
    "https://www.aajtak.in/",        # Hindi
    "https://www.jagran.com/",      # Hindi
    "https://www.bhaskar.com/national/",  # Hindi
    "https://www.hindustantimes.com/india-news",
    "https://www.livemint.com/latest-news"
]

INTERNATIONAL_SOURCES = [
    "https://www.thehindu.com/news/international/",
    "https://www.bbc.com/news/world/asia/india",
    "https://indianexpress.com/section/world/",
    "https://timesofindia.indiatimes.com/world"
]

# scraping constraints
MIN_LEN = 25
MAX_LEN = 400

# keywords and weights for scoring
KEYWORDS = [
    "bjp", "congress", "rahul", "modi", "india", "election", "violence",
    "lynching", "corruption", "protest", "china", "pakistan", "usa",
    "cricket", "sports", "discrimination", "reservation", "scandal",
    "police", "govt", "government", "cabinet", "mla", "mp"
]

TOPIC_WEIGHTS = {
    "BJP": 3, "Congress": 3, "corruption": 3, "lynching": 3,
    "cricket": 2, "sports": 1, "china": 2, "pakistan": 2,
    "usa": 2, "election": 3, "violence": 2, "discrimination": 2
}

# prefixes / emojis in Hindi-tone
PREFIXES = [
    "🚨 ताज़ा:", "⚡ अब:", "🔥 बड़ा खुलासा:", "💥 Exclusive:", "📢 Update:",
    "🧩 क्या हुआ:", "🔴 स्कैंडल:", "📣 Must Read:", "🛑 ध्यान:", "💬 जनता कह रही है:"
]

EMOJIS = ["🚨","🔥","⚡","💥","⚠️","📰","💣","📢","🔍","🧨"]

# filler lines (English) used to expand text then translate
FILLERS = [
    "This development is drawing widespread attention and may affect many stakeholders.",
    "Experts say this could have significant consequences for related groups.",
    "Public reaction is strong; official responses are awaited.",
    "This links to earlier reports and could alter the political narrative.",
    "Preliminary data suggests the situation may escalate in coming days."
]

# synonyms map (small sample; extend as needed)
SYNONYMS = {
    "allegations": ["accusations", "claims"],
    "protest": ["demonstration", "uproar"],
    "scandal": ["controversy", "exposé"]
}

# optional: keyword -> impact mapping (extend)
KEYWORD_IMPACT_MAP = {
    "election": "political landscape may shift",
    "corruption": "trust in institutions may erode",
    "cricket": "sports fans will react strongly"
}

# ------------------------ State (persisted) ------------------------
if os.path.exists(POSTED_FILE):
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            posted_state = json.load(f)
    except Exception:
        posted_state = {"prefix":{}, "emoji":{}, "IR_count":0, "last_text":""}
else:
    posted_state = {"prefix":{}, "emoji":{}, "IR_count":0, "last_text":""}

# helper to save posted_state
def save_posted_state():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_state, f, ensure_ascii=False, indent=2)

# ------------------------ Utilities ------------------------
def sanitize(text):
    if not text:
        return ""
    t = html.unescape(text)
    # remove extra whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def safe_get(url, timeout=10):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        # print minimal to avoid flooding logs
        print(f"[WARN] GET failed: {url} -> {e}")
        return None

def try_text(tag):
    try:
        return sanitize(tag.get_text(" ", strip=True))
    except Exception:
        return ""

def smart_truncate(text, max_chars=280):
    if len(text) <= max_chars:
        return text
    # try to cut at punctuation close to end
    cut = text[:max_chars-3]
    idx = max(cut.rfind('.'), cut.rfind('।'), cut.rfind('!'), cut.rfind('?'), cut.rfind(';'))
    if idx and idx > int(0.5 * len(cut)):
        return text[:idx+1]
    # else cut at last space
    last_space = cut.rfind(' ')
    if last_space > int(0.4 * len(cut)):
        return cut[:last_space] + "..."
    return cut + "..."

# ------------------------ Scraping & extraction ------------------------
def extract_page_items(url):
    html_text = safe_get(url)
    if not html_text:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    items = []

    # find headline tags and candidate article containers
    # Approach: collect h1-h4, then try to get sibling <p> or meta description
    candidates = soup.find_all(["h1","h2","h3","h4"])
    for t in candidates:
        title = try_text(t)
        if not title or len(title) < MIN_LEN or len(title) > MAX_LEN:
            continue

        subtitle = ""
        # next sibling paragraph or a short desc within parent
        nxt = t.find_next_sibling()
        if nxt and nxt.name in ("p","div","span"):
            s = try_text(nxt)
            if 15 <= len(s) <= 260:
                subtitle = s

        # check parent <article> or parent p
        if not subtitle:
            parent = t.parent
            if parent:
                p = parent.find("p")
                if p:
                    s = try_text(p)
                    if 15 <= len(s) <= 260:
                        subtitle = s

        # try meta description
        if not subtitle:
            meta = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
            if meta and meta.get("content"):
                s = sanitize(meta.get("content"))
                if 15 <= len(s) <= 260:
                    subtitle = s

        # try a time tag
        time_text = ""
        time_tag = t.find_next("time") or soup.find("time")
        if time_tag:
            time_text = try_text(time_tag)

        items.append({
            "title": title,
            "subtitle": subtitle,
            "url": url,
            "time": time_text,
            "topic": detect_topic(title)
        })

    # dedupe within page by normalized title
    seen = set()
    unique = []
    for it in items:
        key = re.sub(r'\W+', ' ', it['title']).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique

# small topic detector
def detect_topic(title):
    t = title.lower()
    if any(k in t for k in ["bjp","congress","modi","rahul","election","minister","government","cabinet","mla","mp","party"]):
        return "Politics"
    if any(k in t for k in ["china","pakistan","usa","russia","international","world","global"]):
        return "International Relations"
    if any(k in t for k in ["cricket","match","ipl","football","sports","hockey","player"]):
        return "Sports"
    return "General"

def scrape_sources(urls, limit=120):
    all_items = []
    for u in urls:
        tries = 0
        while tries < 2:
            tries += 1
            try:
                items = extract_page_items(u)
                if items:
                    all_items.extend(items)
                    break
                else:
                    time.sleep(0.4)
            except Exception as e:
                print(f"[WARN] extract error {u}: {e}")
                time.sleep(0.5)
    # dedupe across sources
    normalized = {}
    for h in all_items:
        key = re.sub(r'\W+', ' ', h['title']).strip().lower()
        if key in normalized:
            # keep one with subtitle if possible
            if not normalized[key].get("subtitle") and h.get("subtitle"):
                normalized[key] = h
        else:
            normalized[key] = h
    out = list(normalized.values())
    return out[:limit]

# ------------------------ Scoring ------------------------
def assign_scores(headlines):
    words = []
    for h in headlines:
        words += re.findall(r'\w+', h['title'].lower())
    freq = Counter(words)
    for h in headlines:
        score = 1
        for w in re.findall(r'\w+', h['title'].lower()):
            if w in KEYWORDS:
                score += freq[w]
        for k, v in TOPIC_WEIGHTS.items():
            if k.lower() in h['title'].lower():
                score += v
        h['score'] = score
    return headlines

def save_headlines(headlines, filepath):
    top = sorted(headlines, key=lambda x: x.get('score',0), reverse=True)[:max(15, len(headlines)//3)]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Saved {len(top)} -> {filepath}")

def load_headlines(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] load failed {filepath}: {e}")
        return []

# ------------------------ Pick headline ------------------------
def pick_headline_weighted(headlines):
    weighted = [h for h in headlines if h.get('score',0) > 0]
    if not weighted:
        return None
    weights = [h['score'] for h in weighted]
    try:
        return random.choices(weighted, weights=weights, k=1)[0]
    except Exception:
        return random.choice(weighted)

# ------------------------ Reason & impact generation ------------------------
def infer_reason_impact(headline_obj):
    # Try map based on keywords; otherwise generic
    title = headline_obj.get('title','').lower()
    reason = ""
    impact = ""
    for kw in KEYWORD_IMPACT_MAP:
        if kw in title:
            reason = f"इसका कारण: {kw}"
            impact = KEYWORD_IMPACT_MAP[kw]
            break
    if not reason:
        # small heuristics
        if any(w in title for w in ["protest","protests","demonstration","violence","riot","clash"]):
            reason = "स्थानीय विरोध और तनाव के कारण"
            impact = "स्थानीय सुरक्षा व प्रशासन प्रभावित हो सकते हैं"
        elif any(w in title for w in ["election","vote","poll"]):
            reason = "चुनावी प्रक्रियाओं व रणनीतियों से जुड़ा"
            impact = "राजनैतिक समीकरण बदल सकते हैं"
        else:
            reason = "हालिया घटनाओं के कारण"
            impact = "सम्बंधित पक्षों को प्रभावित कर सकता है"
    return reason, impact

# ------------------------ Compose / expand text ------------------------
def build_english_expansion(title, subtitle, reason, impact, target_chars=250):
    parts = [title]
    if subtitle:
        parts.append(subtitle)
    if reason:
        parts.append(reason)
    if impact:
        parts.append(impact)
    base = " | ".join([p for p in parts if p])
    base = sanitize(base)
    # add fillers until target approx
    filler_pool = FILLERS.copy()
    random.shuffle(filler_pool)
    i = 0
    while len(base) < target_chars and i < len(filler_pool):
        base += " " + filler_pool[i]
        i += 1
    # safety cap
    if len(base) > 275:
        base = base[:272] + "..."
    return base

def humanize_english(text):
    # small humanization: add opener sometimes, replace separators, adjust spacing
    if random.random() < 0.25:
        openers = ["Note:", "Update:", "Breaking:", "Report:"]
        text = random.choice(openers) + " " + text
    text = text.replace(" | ", " — ")
    return text

def compose_final_tweet(headline_obj, force_target=None):
    title = headline_obj.get('title','')
    subtitle = headline_obj.get('subtitle','')
    reason, impact = infer_reason_impact(headline_obj)
    target = force_target or random.randint(245,270)
    eng = build_english_expansion(title, subtitle, reason, impact, target_chars=target)
    eng = humanize_english(eng)

    # pick prefix and emoji with usage limits
    prefix = random.choice([p for p in PREFIXES if posted_state["prefix"].get(p,0) < 3] or PREFIXES)
    emoji = random.choice([e for e in EMOJIS if posted_state["emoji"].get(e,0) < 3] or EMOJIS)
    posted_state["prefix"][prefix] = posted_state["prefix"].get(prefix,0) + 1
    posted_state["emoji"][emoji] = posted_state["emoji"].get(emoji,0) + 1

    combined = f"{prefix} {emoji} {eng}"
    # translate to Hindi (preferred)
    try:
        trans = translator.translate(combined, src='en', dest='hi').text
        trans = sanitize(trans)
    except Exception as e:
        print(f"[WARN] translation failed: {e}")
        trans = sanitize(combined)

    # final safety: truncate <= 280 preserving sentences where possible
    final = smart_truncate(trans, 280)
    return final, reason, impact

# ------------------------ Posting (method unchanged) ------------------------
def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.utcnow().isoformat()}] ✅ Tweet posted (len={len(text)}): {text[:140]}...")
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] ❌ Failed to post tweet: {e}")
        traceback.print_exc()

# ------------------------ Main workflow ------------------------
def main():
    print(f"\n[START] fetchpost_ultimate run at {datetime.now().isoformat()}\n")

    # 1) Scrape
    print("[STEP] Scraping domestic sources...")
    domestic_items = scrape_sources(DOMESTIC_SOURCES, limit=160)
    print(f"[INFO] Domestic scraped: {len(domestic_items)} items")

    print("[STEP] Scraping international sources...")
    international_items = scrape_sources(INTERNATIONAL_SOURCES, limit=120)
    print(f"[INFO] International scraped: {len(international_items)} items")

    # 2) Score
    domestic_scored = assign_scores(domestic_items)
    international_scored = assign_scores(international_items)

    # 3) Save JSON (so poster can read same files)
    if domestic_scored:
        save_headlines(domestic_scored, MORNING_FILE)
        save_headlines(domestic_scored, EVENING_FILE)  # reuse for evening
    if international_scored:
        save_headlines(international_scored, IR_FILE)

    # 4) Load back
    morning = load_headlines(MORNING_FILE)
    evening = load_headlines(EVENING_FILE)
    ir_list = load_headlines(IR_FILE)
    all_headlines = morning + evening + ir_list
    print(f"[INFO] Total headlines available for posting: {len(all_headlines)}")

    if not all_headlines:
        print("[ERROR] No headlines available — aborting.")
        return

    # 5) choose headline, respect IR limit
    tries = 0
    chosen = None
    while tries < 12:
        tries += 1
        candidate = pick_headline_weighted(all_headlines)
        if not candidate:
            continue
        if candidate.get("topic") == "International Relations" and posted_state.get("IR_count",0) >= 3:
            continue
        chosen = candidate
        break

    if not chosen:
        chosen = random.choice(all_headlines)
        print("[WARN] fallback chosen randomly")

    # 6) compose
    final_text, reason, impact = compose_final_tweet(chosen)
    print(f"[DEBUG] Composed tweet (len={len(final_text)}): {final_text[:200]}...")

    # 7) quality checks
    # avoid identical to last posted
    last = posted_state.get("last_text","")
    if last and final_text.strip() == last.strip():
        print("[WARN] Final tweet identical to last posted — aborting to avoid duplicate.")
        return

    # avoid empty or too short
    if not final_text or len(final_text) < 30:
        print("[WARN] Final tweet too short or empty — aborting.")
        return

    # 8) Post
    post_tweet(final_text)

    # 9) update posted state
    posted_state["last_text"] = final_text
    posted_state["last_posted_at"] = datetime.utcnow().isoformat()
    if chosen.get("topic") == "International Relations":
        posted_state["IR_count"] = posted_state.get("IR_count",0) + 1

    save_posted_state()
    print(f"[DONE] Run finished at {datetime.now().isoformat()}")

# ------------------------ If run as script ------------------------
if __name__ == "__main__":
    main() 
