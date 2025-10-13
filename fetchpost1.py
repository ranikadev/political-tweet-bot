import os
import re
import json
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
import tweepy
from googletrans import Translator

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(base_dir, exist_ok=True)
morning_file = os.path.join(base_dir, "morning.json")
evening_file = os.path.join(base_dir, "evening.json")
ir_file = os.path.join(base_dir, "international.json")
posted_today_file = "posted_today.json"

# ------------------------ Twitter API ------------------------
BEARER_TOKEN = os.environ['BEARER_TOKEN']
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ------------------------ Config ------------------------
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/127.0.0.1 Safari/537.36"
}

keywords = [
    "bjp", "congress", "rahul", "modi", "india", "election", "violence",
    "lynching", "corruption", "protest", "china", "pakistan", "usa",
    "cricket", "sports", "discrimination", "reservation", "scandal"
]

topic_weights = {
    "BJP": 3,
    "Congress": 3,
    "corruption": 3,
    "lynching": 3,
    "cricket": 2,
    "sports": 1,
    "China": 2,
    "Pakistan": 2,
    "USA": 2,
    "election": 3,
    "violence": 2,
    "discrimination": 2,
}

prefixes = ["Breaking", "Alert", "Update", "Exclusive", "Trending", "Latest", "Must Know", "Shocking", "Urgent"]
emojis = ["🚨","🔥","⚡","🛑","❗","⚠️"]
synonyms = {}  # add your synonyms here
keyword_impact_map = {}  # add your keyword-impact mapping

translator = Translator()

# ------------------------ Load posted_today ------------------------
if os.path.exists(posted_today_file):
    with open(posted_today_file, "r", encoding="utf-8") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix": {}, "emoji": {}, "IR_count": 0}

# ------------------------ Scraping ------------------------
def extract_headlines(url):
    headlines = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {url} -> HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        tags = soup.find_all(["h1", "h2", "h3", "h4"])
        for t in tags:
            text = t.get_text(strip=True)
            if 25 < len(text) < 180:
                headlines.append({"title": text, "url": url})
    except Exception as e:
        print(f"❌ {url}: {e}")
    return headlines

def scrape_domestic():
    urls = [
        "https://timesofindia.indiatimes.com/",
        "https://www.ndtv.com/latest",
        "https://www.indiatoday.in/",
        "https://www.jagran.com/",
        "https://www.aajtak.in/",
        "https://www.abplive.com/news",
        "https://www.bhaskar.com/national/"
    ]
    headlines = []
    for url in urls:
        headlines += extract_headlines(url)
    return headlines[:80]

def scrape_international():
    urls = [
        "https://www.thehindu.com/news/international/",
        "https://www.bbc.com/news/world/asia/india",
        "https://indianexpress.com/section/world/",
        "https://timesofindia.indiatimes.com/world"
    ]
    headlines = []
    for url in urls:
        headlines += extract_headlines(url)
    return headlines[:50]

# ------------------------ Scoring ------------------------
def assign_scores(headlines):
    all_words = []
    for h in headlines:
        all_words += re.findall(r'\w+', h['title'].lower())
    freq = Counter(all_words)
    for h in headlines:
        h_score = 1
        for w in re.findall(r'\w+', h['title'].lower()):
            if w in keywords:
                h_score += freq[w]
        for k, v in topic_weights.items():
            if k.lower() in h['title'].lower():
                h_score += v
        h['score'] = h_score
    return headlines

def save_json(headlines, file_path):
    top_items = sorted(headlines, key=lambda x: x['score'], reverse=True)[:max(15, len(headlines)//3)]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(top_items, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved {len(top_items)} -> {file_path}")

# ------------------------ Helpers ------------------------
def load_headlines(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []

def pick_headline_weighted(headlines):
    weighted = [h for h in headlines if h.get('score', 0) > 0]
    if weighted:
        return random.choices(weighted, weights=[h['score'] for h in weighted], k=1)[0]
    return None

def get_reason_impact(headline_obj, chance=0.2):
    reason = headline_obj.get("reason")
    impact = headline_obj.get("impact")
    if not reason and not impact and random.random() <= chance:
        words = re.findall(r'\w+', headline_obj['title'].lower())
        reason_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        if reason_kw:
            reason_templates = [f"इस वजह से {reason_kw}", f"{reason_kw} के चलते", f"{reason_kw} को लेकर"]
            reason = random.choice(reason_templates)
        else:
            reason = "हालिया घटनाओं के कारण"
        impact_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        impact = keyword_impact_map.get(impact_kw, "सम्बंधित पक्षों को प्रभावित करता है")
    return reason, impact

def advanced_rephrase_specific(headline, reason, impact):
    available_prefixes = [p for p in prefixes if posted_today["prefix"].get(p, 0) < 2]
    prefix = random.choice(available_prefixes) if available_prefixes else random.choice(prefixes)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix, 0) + 1

    available_emojis = [e for e in emojis if posted_today["emoji"].get(e, 0) < 2]
    emoji = random.choice(available_emojis) if available_emojis else random.choice(emojis)
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji, 0) + 1

    words = headline.split()
    new_words = []
    for w in words:
        key = w.strip(".,!?")
        if key in synonyms and random.random() < 0.3:
            new_words.append(random.choice(synonyms[key]))
        else:
            new_words.append(w)
    new_title = " ".join(new_words)

    # Expand short headline to ~250 characters
    if len(new_title) < 200:
        new_title += " | " + reason + ". यह विकास महत्वपूर्ण है और इससे सम्बंधित पक्ष प्रभावित हो सकते हैं। अधिक विवरण बताते हैं प्रभाव और संदर्भ।"

    # Translate to Hindi
    translated = translator.translate(new_title, dest="hi").text

    full_text = f"{prefix} {emoji} {translated}"
    if reason:
        full_text += f" ({reason})"
    if impact:
        full_text += f", प्रभाव: {impact}"

    if len(full_text) > 280:
        full_text = full_text[:277] + "..."

    return full_text
