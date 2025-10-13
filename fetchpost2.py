#!/usr/bin/env python3
"""
fetchpost_final.py
Combined scraper + headline scorer + human-like tweet generator + poster.
- Single-file: scrapes sources (EN + HI), extracts headline/sub/summary/time.
- Builds rich, human-like tweet ~250-280 chars, translates to Hindi, posts via Tweepy v2 create_tweet.
- Keeps posted_today.json to limit IR posts, prefix/emoji reuse.
- Does NOT change your tweet-post method: uses client.create_tweet(text=...)
"""

import os
import json
import random
import re
import time
import html
from datetime import datetime
from collections import Counter, defaultdict

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
import tweepy
from googletrans import Translator

# ------------------------ Config ------------------------
BASE_DIR = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(BASE_DIR, exist_ok=True)

MORNING_FILE = os.path.join(BASE_DIR, "morning.json")
EVENING_FILE = os.path.join(BASE_DIR, "evening.json")
IR_FILE = os.path.join(BASE_DIR, "international.json")
POSTED_TODAY = "posted_today.json"

# Twitter credentials: keep posting method unchanged (create_tweet)
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")  # optional

# Initialize tweepy client (we will use create_tweet)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Translation
translator = Translator()

# HTTP session with retries
session = requests.Session()
retries = Retry(total=2, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; FetchPostBot/1.0; +https://example.com/bot)"
})

# Keywords and weights for scoring
KEYWORDS = [
    "bjp", "congress", "rahul", "modi", "india", "election", "violence",
    "lynching", "corruption", "protest", "china", "pakistan", "usa",
    "cricket", "sports", "discrimination", "reservation", "scandal"
]

TOPIC_WEIGHTS = {
    "BJP": 3, "Congress": 3, "corruption": 3, "lynching": 3,
    "cricket": 2, "sports": 1, "China": 2, "Pakistan": 2,
    "USA": 2, "election": 3, "violence": 2, "discrimination": 2
}

PREFIXES = [
    "🚨 Breaking:", "⚡ ताज़ा:", "🔥 Exclusive:", "💥 Revealed:", "📢 Update:",
    "🧩 क्या हुआ:", "🔴 Scandal:", "📣 Must Read:", "🛑 Alert:", "💬 Trending:"
]

# prefix->emoji mapping fallback
EMOJIS = ["🚨","🔥","⚡","💥","⚠️","📰","💣","📢"]

# filler templates (English) for expansion (we translate later)
FILLERS = [
    "This development has sparked wide discussion and may affect many stakeholders.",
    "Experts say this could have significant consequences for the related groups.",
    "Reports and early data suggest the situation may escalate further.",
    "Public reaction is mixed; official responses are awaited.",
    "This builds on earlier reports and could change the political narrative."
]

# Sources (mix of English + Hindi sources). Add/remove as desired.
DOMESTIC_SOURCES = [
    "https://www.ndtv.com/latest",
    "https://www.indiatoday.in/",
    "https://www.aajtak.in/",                   # Hindi
    "https://www.jagran.com/",                  # Hindi
    "https://www.abplive.com/news",
    "https://www.bhaskar.com/national/"         # Hindi
]

INTERNATIONAL_SOURCES = [
    "https://www.thehindu.com/news/international/",
    "https://www.bbc.com/news/world/asia/india",
    "https://indianexpress.com/section/world/",
    "https://timesofindia.indiatimes.com/world"
]

# scraping constraints
MIN_LEN = 25
MAX_LEN = 350

# ------------------------ State ------------------------
if os.path.exists(POSTED_TODAY):
    with open(POSTED_TODAY, "r", encoding="utf-8") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix": {}, "emoji": {}, "IR_count": 0, "last_run": None}

# ------------------------ Utilities ------------------------
def sanitize(text):
    if not text:
        return ""
    t = html.unescape(text)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def safe_request(url, timeout=10):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[WARN] request failed {url}: {e}")
        return None

def try_extract_text(tag):
    try:
        return sanitize(tag.get_text(" ", strip=True))
    except Exception:
        return ""

def detect_topic(title):
    t = title.lower()
    if any(k in t for k in ["bjp","congress","modi","rahul","election","mla","mp","government","minister","polit"]):
        return "Politics"
    if any(k in t for k in ["china","pakistan","usa","us","russia","international","global","world"]):
        return "International Relations"
    if any(k in t for k in ["cricket","football","hockey","match","series","ipl","world cup","player"]):
        return "Sports"
    return "General"

def truncate_by_chars(text, max_chars=280):
    if len(text) <= max_chars:
        return text
    # try cut at sentence boundary before max_chars-3
    cut = text[:max_chars-3]
    idx = max(cut.rfind('.'), cut.rfind('।'), cut.rfind('!'), cut.rfind('?'))
    if idx and idx > int(0.6*len(cut)):
        return text[:idx+1]
    # else hard cut
    return text[:max_chars-3].rstrip() + "..."

# ------------------------ Scraping / Extraction ------------------------
def extract_from_page(url):
    html_text = safe_request(url)
    if not html_text:
        return []
    soup = BeautifulSoup(html_text, "html.parser")

    items = []

    # Common headline tags
    tags = soup.find_all(["h1","h2","h3","h4"])
    # Also include <article> summaries
    for t in tags:
        title = try_extract_text(t)
        if not title or len(title) < MIN_LEN or len(title) > MAX_LEN:
            continue

        # subheadline: check next sibling paragraph or a short summary within the same container
        sub = ""
        # try sibling p
        nxt = t.find_next_sibling(["p","div","span"])
        if nxt:
            s = try_extract_text(nxt)
            if 15 <= len(s) <= 220:
                sub = s

        # try parent paragraph / meta description
        if not sub:
            parent = t.parent
            if parent:
                p = parent.find("p")
                if p:
                    s = try_extract_text(p)
                    if 15 <= len(s) <= 220:
                        sub = s

        # try meta description
        if not sub:
            meta = soup.find("meta", {"name":"description"}) or soup.find("meta", {"property":"og:description"})
            if meta and meta.get("content"):
                s = sanitize(meta.get("content"))
                if 15 <= len(s) <= 220:
                    sub = s

        # timestamp if present
        time_text = ""
        time_tag = t.find_next("time") or soup.find("time")
        if time_tag:
            time_text = try_extract_text(time_tag)

        items.append({
            "title": title,
            "subtitle": sub,
            "url": url,
            "time": time_text,
            "topic": detect_topic(title)
        })

    # Deduplicate by title within page
    seen = set()
    unique = []
    for it in items:
        key = it["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique

def scrape_sources_list(urls, limit=80):
    headlines = []
    for u in urls:
        tries = 0
        while tries < 2:
            tries += 1
            page_items = extract_from_page(u)
            if page_items:
                headlines.extend(page_items)
                break
            else:
                time.sleep(1)
        # small delay between sources
        time.sleep(0.5)
    # dedupe across sources by normalized title
    normalized = {}
    for h in headlines:
        k = re.sub(r'\W+', ' ', h["title"]).strip().lower()
        if k in normalized:
            # prefer existing with subtitle or earlier one
            if not normalized[k].get("subtitle") and h.get("subtitle"):
                normalized[k] = h
        else:
            normalized[k] = h
    all_items = list(normalized.values())
    # limit
    return all_items[:limit]

# ------------------------ Scoring / selecting ------------------------
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
        for k,v in TOPIC_WEIGHTS.items():
            if k.lower() in h['title'].lower():
                score += v
        h['score'] = score
    return headlines

def save_list_json(headlines, path):
    top = sorted(headlines, key=lambda x: x.get('score',0), reverse=True)[:max(15, len(headlines)//3)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Saved {len(top)} -> {path}")

def load_list_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] failed to load {path}: {e}")
        return []

# ------------------------ Expand / humanize / translate ------------------------
def build_expanded_english(headline, subtitle, reason, impact, target_len=250):
    # start with headline + subtitle if available
    parts = [headline]
    if subtitle:
        parts.append(subtitle)
    # append reason/impact in short phrases (English)
    if reason:
        parts.append(reason if isinstance(reason, str) else f"Reason: {reason}")
    if impact:
        parts.append(impact if isinstance(impact, str) else f"Impact: {impact}")

    base = " | ".join([p for p in parts if p])
    base = sanitize(base)
    # add filler sentences until close to target_len (characters)
    filler_pool = FILLERS.copy()
    random.shuffle(filler_pool)
    i = 0
    while len(base) < target_len and i < 6:
        base += " " + filler_pool[i % len(filler_pool)]
        i += 1
    # final cleanup
    base = re.sub(r'\s+', ' ', base).strip()
    if len(base) > 275:
        base = base[:272] + "..."
    return base

def human_tone_english(text):
    # minor humanization: punctuation spacing, short sentence splits, rhetorical phrase occasionally
    text = text.strip()
    # small chance to add rhetorical opener
    if random.random() < 0.25:
        openers = ["Note:", "Update:", "Remember:", "Important:"]
        text = random.choice(openers) + " " + text
    # replace sequences of ' | ' with em dashes for human feel
    text = text.replace(" | ", " — ")
    return text

def compose_final_text(headline_obj, force_target_len=None):
    title = headline_obj.get("title","")
    subtitle = headline_obj.get("subtitle","")
    reason, impact = get_reason_impact(headline_obj, chance=0.28)
    # build English expanded text to approximate target length (target between 245-270)
    target = force_target_len or random.randint(245,270)
    eng = build_expanded_english(title, subtitle, reason, impact, target_len=target)
    eng = human_tone_english(eng)
    # add prefix + emoji
    prefix = random.choice([p for p in PREFIXES if posted_today["prefix"].get(p,0) < 3] or PREFIXES)
    emoji = random.choice([e for e in EMOJIS if posted_today["emoji"].get(e,0) < 3] or EMOJIS)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0) + 1
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0) + 1

    combined = f"{prefix} {emoji} {eng}"
    # translate to Hindi
    try:
        hi = translator.translate(combined, src='en', dest='hi').text
        hi = sanitize(hi)
    except Exception as e:
        print(f"[WARN] translation failed: {e}")
        hi = sanitize(combined)
    # ensure <=280 chars, try smart truncate to sentence boundary
    if len(hi) > 280:
        hi = truncate_by_chars(hi, 280)
    return hi, reason, impact

# ------------------------ Post (keeps method unchanged) ------------------------
def post_tweet(text):
    # Posting method unchanged: use client.create_tweet(text=...)
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Tweet posted (len={len(text)}): {text[:120]}...")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Workflow (main) ------------------------
def main():
    print(f"\n[START] Fetch & Post run at {datetime.now()}")

    # 1) Scrape sources (domestic and international)
    domestic = scrape_sources_list(DOMESTIC_SOURCES, limit=120)
    international = scrape_sources_list(INTERNATIONAL_SOURCES, limit=80)

    # 2) Score
    domestic_scored = assign_scores(domestic)
    international_scored = assign_scores(international)

    # 3) Save
    if domestic_scored:
        save_list_json(domestic_scored, MORNING_FILE)
        save_list_json(domestic_scored, EVENING_FILE)  # optional: same list for both slots
    if international_scored:
        save_list_json(international_scored, IR_FILE)

    # 4) Load for posting (use saved files to be robust)
    morning = load_list_json(MORNING_FILE)
    evening = load_list_json(EVENING_FILE)
    ir_list = load_list_json(IR_FILE)

    all_headlines = morning + evening + ir_list
    print(f"[INFO] Total headlines available: {len(all_headlines)}")

    if not all_headlines:
        print("[ERROR] No headlines, aborting post.")
        return

    # 5) Pick a headline weighted by score, respecting IR limit
    attempts = 0
    chosen = None
    while attempts < 12:
        attempts += 1
        candidate = pick_headline_weighted(all_headlines)
        if not candidate:
            break
        # detect topic (if absent)
        if "topic" not in candidate:
            candidate["topic"] = detect_topic(candidate.get("title",""))
        if candidate.get("topic") == "International Relations" and posted_today.get("IR_count",0) >= 3:
            continue
        chosen = candidate
        break

    if not chosen:
        chosen = random.choice(all_headlines)
        print("[WARN] Weighted selection failed; using random fallback.")

    # 6) Compose final human-like Hindi tweet around 250-280 chars
    final_text, reason, impact = compose_final_text(chosen)
    print(f"[DEBUG] Final tweet (len={len(final_text)}): {final_text[:200]}...")

    # 7) Quality checks: duplicates, banned chars, length
    if len(final_text) > 280:
        final_text = truncate_by_chars(final_text, 280)

    # avoid repeating the exact same tweet posted_today (basic check)
    # simple: check posted_today contains last text (store last_text)
    last_text = posted_today.get("last_text")
    if last_text and final_text.strip() == last_text.strip():
        print("[WARN] Tweet identical to last posted; aborting this run to avoid duplicate.")
        return

    # 8) Post
    post_tweet(final_text)

    # 9) Update counters and save posted_today
    if chosen.get("topic") == "International Relations":
        posted_today["IR_count"] = posted_today.get("IR_count",0) + 1
    posted_today["last_text"] = final_text
    posted_today["last_posted_at"] = datetime.utcnow().isoformat()

    with open(POSTED_TODAY, "w", encoding="utf-8") as f:
        json.dump(posted_today, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Run finished at {datetime.now()}")

if __name__ == "__main__":
    main()
