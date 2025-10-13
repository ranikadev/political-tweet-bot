import os
import json
import random
import re
from datetime import datetime
from collections import Counter
import feedparser
import tweepy
from googletrans import Translator

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(base_dir, exist_ok=True)
rss_file = os.path.join(base_dir, "rss_headlines.json")
posted_today_file = "posted_today.json"

# ------------------------ Twitter API v2 ------------------------
BEARER_TOKEN = os.environ.get('BEARER_TOKEN')
API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_SECRET = os.environ.get('ACCESS_SECRET')

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ------------------------ Load posted_today ------------------------
if os.path.exists(posted_today_file):
    with open(posted_today_file, "r", encoding="utf-8") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix": {}, "emoji": {}, "IR_count": 0}

# ------------------------ Config ------------------------
prefixes = [
    "Breaking", "Alert", "Exclusive", "Shocking", "Controversial",
    "Must Read", "Urgent", "Scandal", "Truth", "Explosive", "सावधान", "ताज़ा"
]
emojis = ["🚨","🔥","⚡","💥","⚠️","📰","💣"]
keywords = [
    "bjp", "congress", "rahul", "modi", "india", "election", "violence",
    "lynching", "corruption", "protest", "china", "pakistan", "usa",
    "cricket", "sports", "discrimination", "reservation", "scandal"
]
topic_weights = {
    "BJP": 3, "Congress": 3, "corruption": 3, "lynching": 3,
    "cricket": 2, "sports": 1, "China": 2, "Pakistan": 2,
    "USA": 2, "election": 3, "violence": 2, "discrimination": 2
}
synonyms = {}  # optional replacements
keyword_impact_map = {}  # optional impact mapping
translator = Translator()

# ------------------------ RSS Sources ------------------------
domestic_rss = [
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://www.ndtv.com/rss/ndtvlatest.xml",
    "https://www.indiatoday.in/rss/1206573",
    "https://www.jagran.com/rss/home.xml",
    "https://www.aajtak.in/rss-feed"
]
international_rss = [
    "https://www.thehindu.com/news/international/?service=rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://indianexpress.com/section/world/feed/",
    "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"
]

# ------------------------ Fetch & Process RSS ------------------------
def fetch_rss_headlines(urls):
    headlines = []
    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get('title', '').strip()
            description = entry.get('description', '').strip()
            if title and 30 < len(title) < 200:
                headlines.append({"title": title, "description": description, "url": entry.get("link", "")})
    return headlines

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
    top_items = sorted(headlines, key=lambda x: x['score'], reverse=True)[:max(20, len(headlines)//3)]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(top_items, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved {len(top_items)} -> {file_path}")

# ------------------------ Tweet Helpers ------------------------
def load_headlines(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

def pick_headline_weighted(headlines):
    weighted = [h for h in headlines if h.get('score',0) > 0]
    if weighted:
        return random.choices(weighted, weights=[h['score'] for h in weighted], k=1)[0]
    return None

def get_reason_impact(headline_obj, chance=0.3):
    reason = headline_obj.get("reason")
    impact = headline_obj.get("impact")
    if not reason and not impact and random.random() <= chance:
        reason = "हालिया घटनाओं के कारण"
        impact = "संबंधित पक्षों को प्रभावित करने वाला"
    return reason, impact

def advanced_rephrase_specific(headline, description, reason, impact):
    available_prefixes = [p for p in prefixes if posted_today["prefix"].get(p,0)<2]
    prefix = random.choice(available_prefixes) if available_prefixes else random.choice(prefixes)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0)+1

    available_emojis = [e for e in emojis if posted_today["emoji"].get(e,0)<2]
    emoji = random.choice(available_emojis) if available_emojis else random.choice(emojis)
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0)+1

    # Combine title + description
    new_title = headline
    if description:
        combined = f"{headline} | {description}"
        if len(combined) < 250:
            new_title = combined

    extra_text = ""
    if len(new_title) < 200:
        extra_text = f" | {reason}. यह विकास महत्वपूर्ण है और संबंधित पक्षों पर प्रभाव डाल सकता है। {impact}।"
        new_title += extra_text

    full_text = f"{prefix} {emoji} {new_title}"
    if len(full_text) > 280:
        full_text = full_text[:277] + "..."

    # Translate to Hindi
    try:
        full_text_hi = translator.translate(full_text, dest='hi').text
    except:
        full_text_hi = full_text

    return full_text_hi

def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Tweet posted successfully")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
def main():
    domestic_headlines = assign_scores(fetch_rss_headlines(domestic_rss))
    international_headlines = assign_scores(fetch_rss_headlines(international_rss))

    all_headlines = domestic_headlines + international_headlines
    if all_headlines:
        save_json(all_headlines, rss_file)
    else:
        print(f"[WARN {datetime.now()}] No headlines fetched.")

    loaded_headlines = load_headlines(rss_file)
    if not loaded_headlines:
        print(f"[ERROR {datetime.now()}] No headlines available for tweeting. Exiting.")
        return

    tweet_obj = pick_headline_weighted(loaded_headlines)
    if not tweet_obj:
        tweet_obj = random.choice(loaded_headlines)

    reason, impact = get_reason_impact(tweet_obj)
    tweet_text = advanced_rephrase_specific(tweet_obj['title'], tweet_obj.get('description',''), reason, impact)
    print(f"[DEBUG {datetime.now()}] Selected tweet: {tweet_text[:100]}...")

    post_tweet(tweet_text)

    with open(posted_today_file, "w", encoding="utf-8") as f:
        json.dump(posted_today, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
