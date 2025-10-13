import os
import json
import random
from datetime import datetime
import tweepy
from googletrans import Translator
from transformers import pipeline
from collections import defaultdict

# ------------------- Twitter API -------------------
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

translator = Translator()

# ------------------- Load posted tweets -------------------
if os.path.exists("posted.json"):
    with open("posted.json", "r", encoding="utf-8") as f:
        posted = set(json.load(f))
else:
    posted = set()

# ------------------- Load appropriate news file -------------------
hour = datetime.now().hour
if 10 <= hour < 17:
    news_file = "scraped_tweets/morning.json"
else:
    news_file = "scraped_tweets/evening.json"

headlines = []
if os.path.exists(news_file):
    with open(news_file, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data["title"] not in posted:
                headlines.append(data)

if not headlines:
    print(f"[{datetime.now()}] ⚠️ No new headlines to post.")
    exit()

# ------------------- Scoring Function -------------------
def score_headline(headline):
    score = 0
    controversial_keywords = ["corruption", "lynching", "discrimination", "scandal"]
    political_keywords = ["BJP", "Congress", "Modi", "Rahul Gandhi", "election"]
    
    for kw in controversial_keywords:
        if kw.lower() in headline.lower():
            score += 2
    for kw in political_keywords:
        if kw.lower() in headline.lower():
            score += 1
    return score

# ------------------- Topic Categorization -------------------
def categorize_headline(title):
    title_lower = title.lower()
    if any(k in title_lower for k in ["bjp", "modi"]):
        return "BJP"
    elif any(k in title_lower for k in ["congress", "rahul gandhi"]):
        return "Congress"
    else:
        return "Other"

topic_dict = defaultdict(list)
for h in headlines:
    h["topic"] = categorize_headline(h["title"])
    topic_dict[h["topic"]].append(h)

rotation_order = ["BJP", "Congress", "Other"]

# ------------------- Select Headline -------------------
headline_to_post = None
for topic in rotation_order:
    if topic_dict[topic]:
        headlines_in_topic = topic_dict[topic]
        weights = [score_headline(h["title"]) for h in headlines_in_topic]
        headline_to_post = random.choices(headlines_in_topic, weights=weights, k=1)[0]["title"]
        break

if not headline_to_post:
    print(f"[{datetime.now()}] ⚠️ No headline selected.")
    exit()

# ------------------- GPT-2 Rephraser -------------------
generator = pipeline('text-generation', model='distilgpt2')
prompt = f"Rephrase in a critical, questioning political tone: {headline_to_post}"
result = generator(prompt, max_length=70, do_sample=True, temperature=0.7)
rephrased = result[0]['generated_text'].replace(prompt, '').strip()

# Translate to Hindi
translated = translator.translate(rephrased, src='en', dest='hi').text

# Enforce 280-character limit
if len(translated) > 280:
    translated = translated[:277] + "..."

# ------------------- Post to Twitter -------------------
try:
    api.update_status(translated)
    print(f"[{datetime.now()}] ✅ Posted: {translated}")
    posted.add(headline_to_post)
except tweepy.errors.TweepyException as e:
    print(f"[{datetime.now()}] ❌ Twitter error: {e}")
except Exception as e:
    print(f"[{datetime.now()}] ⚠️ Other error: {e}")

# Save posted list
with open("posted.json", "w", encoding="utf-8") as f:
    json.dump(list(posted), f, ensure_ascii=False)
