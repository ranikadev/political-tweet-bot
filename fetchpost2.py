import os
import json
import random
import re
from datetime import datetime
from collections import Counter
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
import tweepy

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(base_dir, exist_ok=True)
morning_file = os.path.join(base_dir, "morning.json")
evening_file = os.path.join(base_dir, "evening.json")
ir_file = os.path.join(base_dir, "international.json")
posted_today_file = "posted_today.json"

# ------------------------ Twitter API v2 ------------------------
BEARER_TOKEN = os.environ['BEARER_TOKEN']      # Required for client
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

prefixes = [
    "Breaking", "Alert", "Update", "Exclusive", "Must Know", "Heads Up",
    "Trending", "Hot Topic", "Controversy", "Latest"
]

emojis = ["🚨","🔥","⚡","📰","🔴","⚠️"]

synonyms = {
    # example: "corruption":["bribery","misconduct"], expand as needed
}

keyword_impact_map = {
    # example: "election":"affecting political landscape"
}

translator = Translator()

# ------------------------ Load posted_today ------------------------
if os.path.exists(posted_today_file):
    with open(posted_today_file,"r",encoding="utf-8") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix": {}, "emoji": {}, "IR_count":0}

# ------------------------ Scraping ------------------------
def extract_headlines(url):
    headlines = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {url} -> HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        tags = soup.find_all(["h1","h2","h3","h4"])
        for t in tags:
            title = t.get_text(strip=True)
            if 25 < len(title) < 180:
                # try to get subtitle/next sibling paragraph
                sub = ""
                next_p = t.find_next("p")
                if next_p:
                    sub = next_p.get_text(strip=True)
                headlines.append({
                    "title": title,
                    "subtitle": sub,
                    "url": url,
                    "topic": detect_topic(title)
                })
        print(f"✅ {url}: {len(headlines)} headlines")
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
    all_h = []
    for u in urls:
        all_h += extract_headlines(u)
    return all_h[:80]

def scrape_international():
    urls = [
        "https://www.thehindu.com/news/international/",
        "https://www.bbc.com/news/world/asia/india",
        "https://indianexpress.com/section/world/",
        "https://timesofindia.indiatimes.com/world"
    ]
    all_h = []
    for u in urls:
        all_h += extract_headlines(u)
    return all_h[:50]

def detect_topic(title):
    title_l = title.lower()
    if any(k.lower() in title_l for k in ["bjp","congress","modi","rahul","election","politics"]):
        return "Politics"
    if any(k.lower() in title_l for k in ["china","pakistan","usa"]):
        return "International Relations"
    if any(k.lower() in title_l for k in ["cricket","sports","football","hockey"]):
        return "Sports"
    return "General"

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
        for k,v in topic_weights.items():
            if k.lower() in h['title'].lower():
                h_score += v
        h['score'] = h_score
    return headlines

def save_json(headlines, file_path):
    top_items = sorted(headlines, key=lambda x:x['score'], reverse=True)[:max(15,len(headlines)//3)]
    with open(file_path,"w",encoding="utf-8") as f:
        json.dump(top_items,f,ensure_ascii=False, indent=2)
    print(f"💾 Saved {len(top_items)} -> {file_path}")

# ------------------------ Load headlines ------------------------
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

# ------------------------ Text enhancement ------------------------
def get_reason_impact(headline_obj, chance=0.2):
    reason = headline_obj.get("reason","")
    impact = headline_obj.get("impact","")
    if not reason and not impact and random.random() <= chance:
        words = re.findall(r'\w+', headline_obj['title'].lower())
        reason_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        reason = f"due to {reason_kw}" if reason_kw else "due to recent developments"
        impact_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        impact = keyword_impact_map.get(impact_kw,"affecting concerned parties")
    return reason, impact

def expand_text(title, subtitle, reason, impact):
    text = title
    if subtitle:
        text += " | " + subtitle
    if len(text)<200:
        extras = []
        if reason: extras.append(f"Reason: {reason}")
        if impact: extras.append(f"Impact: {impact}")
        extras.append("Recent developments suggest this may influence related parties.")
        text += " | " + " ".join(extras)
    return text[:275]

def humanize_text(text):
    words = text.split()
    new_words = []
    for w in words:
        key = w.strip(".,!?")
        if key in synonyms and random.random()<0.3:
            new_words.append(random.choice(synonyms[key]))
        else:
            new_words.append(w)
    return " ".join(new_words)

def advanced_rephrase(headline_obj):
    reason, impact = get_reason_impact(headline_obj)
    text = expand_text(headline_obj['title'], headline_obj.get('subtitle',''), reason, impact)
    text = humanize_text(text)
    prefix = random.choice([p for p in prefixes if posted_today["prefix"].get(p,0)<2] or prefixes)
    emoji = random.choice([e for e in emojis if posted_today["emoji"].get(e,0)<2] or emojis)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0)+1
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0)+1
    final_text = f"{prefix} {emoji} {text}"
    if len(final_text)>280:
        final_text = final_text[:277]+"..."
    try:
        final_text_hi = translator.translate(final_text, dest='hi').text
    except:
        final_text_hi = final_text
    return final_text_hi

# ------------------------ Post ------------------------
def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Tweet posted successfully")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
def main():
    print(f"\n🕒 Fetch & Post started at {datetime.now()
