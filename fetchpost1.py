import os
import re
import json
import random
import requests
from datetime import datetime
from collections import Counter
from bs4 import BeautifulSoup
import tweepy
from googletrans import Translator

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(base_dir, exist_ok=True)
morning_file = os.path.join(base_dir, "morning.json")
evening_file = os.path.join(base_dir, "evening.json")
ir_file = os.path.join(base_dir, "international.json")
posted_today_file = "posted_today.json"

# ------------------------ Twitter API v2 ------------------------
BEARER_TOKEN = os.environ['BEARER_TOKEN']
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ------------------------ Load posted_today ------------------------
if os.path.exists(posted_today_file):
    with open(posted_today_file,"r",encoding="utf-8") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix": {}, "emoji": {}, "IR_count":0}

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
    "BJP": 3, "Congress": 3, "corruption": 3, "lynching": 3,
    "cricket": 2, "sports": 1, "China": 2, "Pakistan": 2,
    "USA": 2, "election": 3, "violence": 2, "discrimination": 2,
}

prefixes = [
    "Breaking", "Alert", "Update", "Exclusive", "Shocking", "Revealed", 
    "Controversial", "Must Read", "Explosive", "Unbelievable", 
    "Trending Now", "Urgent", "Caught on Camera", "Exposed", 
    "Critical", "Scandalous", "Alarming", "Sensational", 
    "Hot Topic", "Attention", "Bombshell", "Breaking News"
]

emoji_map = {
    "Shocking": ["😱", "⚡"],
    "Exclusive": ["📰", "👀"],
    "Explosive": ["💥", "🔥"],
    "Scandalous": ["😡", "💣"],
    "Trending Now": ["📈", "🔥"],
    "Breaking": ["🚨", "⚡"],
    "Alert": ["⚠️","🚨"]
}

synonyms = {}  # can expand for advanced rephrase
keyword_impact_map = {}  # can expand for reason/impact

translator = Translator()

# ------------------------ Scraping ------------------------
def extract_headlines(url):
    headlines = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {url} -> HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        tags = soup.find_all(["h1","h2","h3","h4","p"])
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
        score = 1
        for w in re.findall(r'\w+', h['title'].lower()):
            if w in keywords:
                score += freq[w]
        for k,v in topic_weights.items():
            if k.lower() in h['title'].lower():
                score += v
        h['score'] = score
    return headlines

# ------------------------ Save ------------------------
def save_json(headlines, file_path):
    top_items = sorted(headlines, key=lambda x:x['score'], reverse=True)[:max(15, len(headlines)//3)]
    with open(file_path,"w",encoding="utf-8") as f:
        json.dump(top_items, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved {len(top_items)} -> {file_path}")

# ------------------------ Headline helpers ------------------------
def load_headlines(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path,"r",encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data,list) else []
        except json.JSONDecodeError:
            return []

def pick_headline_weighted(headlines):
    weighted = [h for h in headlines if h.get('score',0)>0]
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
            reason = f"due to {reason_kw}"
        else:
            reason = "due to recent developments"
        impact_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        impact = keyword_impact_map.get(impact_kw,"affecting concerned groups")
    return reason, impact

def advanced_rephrase_specific(headline, reason, impact):
    # Prefix
    available_prefixes = [p for p in prefixes if posted_today["prefix"].get(p,0)<2]
    prefix = random.choice(available_prefixes) if available_prefixes else random.choice(prefixes)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0)+1
    # Emoji
    emojis_for_prefix = emoji_map.get(prefix,prefixes[:3])
    available_emojis = [e for e in emojis_for_prefix if posted_today["emoji"].get(e,0)<2]
    emoji = random.choice(available_emojis) if available_emojis else random.choice(emojis_for_prefix)
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0)+1
    # Synonyms replacement
    words = headline.split()
    new_words = [random.choice(synonyms.get(w.strip(".,!?"),[w])) if random.random()<0.3 else w for w in words]
    new_title = " ".join(new_words)
    # Expand to ~250 chars if short
    if len(new_title) < 200:
    new_title += (
        " | " + reason +
        ". This development is significant and may affect the related parties. "
        "Further details suggest impact and context."
    )
