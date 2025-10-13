import os
import re
import json
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
import tweepy

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

prefixes = ["Breaking", "Alert", "Update"]
emojis = ["🚨","🔥","⚡"]
synonyms = {}  # optional: your synonyms map
keyword_impact_map = {}  # optional: keyword->impact mapping

# ------------------------ Scraping Functions ------------------------
def extract_headlines(url, topic="Domestic"):
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
                sub = None
                next_tag = t.find_next_sibling(["p","span","div"])
                if next_tag:
                    sub_text = next_tag.get_text(strip=True)
                    if 15 < len(sub_text) < 120:
                        sub = sub_text
                headlines.append({
                    "title": text,
                    "sub": sub,
                    "url": url,
                    "topic": topic
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
    headlines = []
    for url in urls:
        headlines += extract_headlines(url, topic="Domestic")
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
        headlines += extract_headlines(url, topic="International Relations")
    return headlines[:50]

# ------------------------ Scoring & Save ------------------------
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

# ------------------------ Tweet Construction ------------------------
def get_reason_impact(headline_obj, chance=0.2):
    reason = headline_obj.get("reason")
    impact = headline_obj.get("impact")
    if not reason and not impact and random.random() <= chance:
        words = re.findall(r'\w+', headline_obj['title'].lower())
        reason_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        if reason_kw:
            reason_templates = [f"due to {reason_kw}", f"following {reason_kw}", f"amid {reason_kw}"]
            reason = random.choice(reason_templates)
        else:
            reason = "due to recent developments"
        impact_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        impact = keyword_impact_map.get(impact_kw,"affecting the concerned groups")
    return reason, impact

def advanced_rephrase_specific(headline, reason, impact):
    available_prefixes = [p for p in prefixes if posted_today["prefix"].get(p,0)<2]
    prefix = random.choice(available_prefixes) if available_prefixes else random.choice(prefixes)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0)+1

    available_emojis = [e for e in emojis if posted_today["emoji"].get(e,0)<2]
    emoji = random.choice(available_emojis) if available_emojis else random.choice(emojis)
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0)+1

    words = headline.split()
    new_words = []
    for w in words:
        key = w.strip(".,!?")
        if key in synonyms and random.random()<0.3:
            new_words.append(random.choice(synonyms[key]))
        else:
            new_words.append(w)
    new_title = " ".join(new_words)

    full_text = f"{prefix} {emoji} {new_title}"
    if reason:
        full_text += f" ({reason})"
    if impact:
        full_text += f", impacting {impact}"
    if len(full_text)>275:
        full_text = full_text[:272]+"..."
    return full_text

def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Tweet posted successfully")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
def main():
    # --- Scrape & Save ---
    morning_headlines = assign_scores(scrape_domestic())
    evening_headlines = assign_scores(scrape_domestic())
    ir_headlines = assign_scores(scrape_international())

    if morning_headlines:
        save_json(morning_headlines, morning_file)
    if evening_headlines:
        save_json(evening_headlines, evening_file)
    if ir_headlines:
        save_json(ir_headlines, ir_file)

    # --- Load all saved headlines ---
    all_headlines = load_headlines(morning_file) + load_headlines(evening_file) + load_headlines(ir_file)
    print(f"[DEBUG {datetime.now()}] Total headlines loaded: {len(all_headlines)}")

    tweet_obj = None
    tries = 0
    while tries<10:
        candidate = pick_headline_weighted(all_headlines)
        if not candidate:
            break
        if candidate.get('topic')=="International Relations" and posted_today.get("IR_count",0)>=3:
            tries +=1
            continue
        tweet_obj = candidate
        break

    if not tweet_obj and all_headlines:
        print(f"[WARN {datetime.now()}] Weighted pick failed, using fallback headline")
        tweet_obj = random.choice(all_headlines)

    if not tweet_obj:
        print(f"[ERROR {datetime.now()}] No headlines available at all. Exiting.")
        return

    reason, impact = get_reason_impact(tweet_obj)
    tweet_text = advanced_rephrase_specific(tweet_obj['title'], reason, impact)
    print(f"[DEBUG {datetime.now()}] Selected headline: {tweet_text[:100]}...")

    post_tweet(tweet_text)

    if tweet_obj.get('topic')=="International Relations":
        posted_today["IR_count"] = posted_today.get("IR_count",0)+1

    with open(posted_today_file,"w",encoding="utf-8") as f:
        json.dump(posted_today,f,ensure_ascii=False, indent=2)

if __name__=="__main__":
    main()
