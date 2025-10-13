import os
import json
import random
from datetime import datetime
from googletrans import Translator
import tweepy

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

# ------------------------ Enforce 280 char limit ------------------------
translated = translated[:280]

# ------------------------ Post Tweet ------------------------
try:
    response = client.create_tweet(text=translated)
    if response.data:
        print(f"[{datetime.now()}] ✅ Posted tweet: {translated}")
        posted.add(title)
        with open(posted_file, "w", encoding="utf-8") as f:
            json.dump(list(posted), f, ensure_ascii=False)
    else:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: No response data")
except Exception as e:
    print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")
