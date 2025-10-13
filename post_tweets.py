import os
import json
import random
from datetime import datetime
import tweepy
from googletrans import Translator

# ------------------------ Twitter API ------------------------
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ------------------------ Translator ------------------------
translator = Translator()

# ------------------------ Posted Tracker ------------------------
posted_file = "scraped_tweets/posted.json"
if os.path.exists(posted_file):
    with open(posted_file, "r", encoding="utf-8") as f:
        posted = set(json.load(f))
else:
    posted = set()

# ------------------------ Select News File ------------------------
hour = datetime.now().hour
news_file = "scraped_tweets/morning.json" if 5 <= hour < 17 else "scraped_tweets/evening.json"

if not os.path.exists(news_file):
    print(f"[{datetime.now()}] ⚠️ News file {news_file} not found. Exiting.")
    exit()

# ------------------------ Load Headlines ------------------------
headlines = []
with open(news_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if data["title"] not in posted:
                headlines.append(data)
        except json.JSONDecodeError:
            print(f"[WARN] Skipping malformed line: {line[:50]} ...")

if not headlines:
    print(f"[{datetime.now()}] ⚠️ No new headlines to post.")
    exit()

# ------------------------ Pick One Headline ------------------------
headline = random.choice(headlines)
title = headline["title"]

# ------------------------ Rephrase / Questioning Tone ------------------------
# Simple rephrase: add "Did you notice?" or "Controversy:" etc.
# You can expand with more complex logic if needed
prefixes = [
    "Did you notice? ",
    "Controversy: ",
    "Questioning: ",
    "Latest: ",
    "Debate: "
]
rephrased = random.choice(prefixes) + title

# ------------------------ Translate to Hindi ------------------------
try:
    translated = translator.translate(rephrased, src='en', dest='hi').text
except Exception as e:
    print(f"[WARN] Translation failed: {e}. Using English text.")
    translated = rephrased

# ------------------------ Enforce Twitter 280 char limit ------------------------
translated = translated[:280]

# ------------------------ Post Tweet ------------------------
try:
    api.update_status(translated)
    print(f"[{datetime.now()}] ✅ Posted tweet: {translated}")
    # Save posted title
    posted.add(title)
    with open(posted_file, "w", encoding="utf-8") as f:
        json.dump(list(posted), f, ensure_ascii=False)
except Exception as e:
    print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")
