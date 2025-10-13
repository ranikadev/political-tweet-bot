import tweepy
from googletrans import Translator
from transformers import pipeline
import json
import random
import datetime

# ================= 1. Twitter API Setup =================
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
ACCESS_SECRET = "YOUR_ACCESS_SECRET"

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ================= 2. File Setup =================
POSTED_FILE = "posted.json"
ARCHIVE_FILE = "tweet_archive.json"

# Load posted IDs
try:
    with open(POSTED_FILE, "r") as f:
        posted_ids = json.load(f)
except FileNotFoundError:
    posted_ids = []

# Load archive
try:
    with open(ARCHIVE_FILE, "r") as f:
        archive = json.load(f)
except FileNotFoundError:
    archive = {"BJP": [], "Congress": []}

# ================= 3. Define Accounts =================
PARTIES = {
    "BJP": ["BJP4India", "narendramodi"],
    "Congress": ["INCIndia", "RahulGandhi"]
}

# ================= 4. Fetch New Tweets =================
for party, accounts in PARTIES.items():
    for acc in accounts:
        tweets = api.user_timeline(screen_name=acc, count=10, tweet_mode="extended")
        for t in tweets:
            if not hasattr(t, "retweeted_status") and t.id not in posted_ids:
                tweet_text = t.full_text
                archive[party].append({"id": t.id, "text": tweet_text})

# Save archive for rotation
with open(ARCHIVE_FILE, "w") as f:
    json.dump(archive, f)

# ================= 5. Prepare Tweets to Post =================
# Separate BJP & Congress
bjp_tweets = archive["BJP"].copy()
congress_tweets = archive["Congress"].copy()

# Alternate 15 tweets
tweets_to_post = []
for i in range(15):
    if i % 2 == 0 and bjp_tweets:
        tweets_to_post.append(bjp_tweets.pop(0))
    elif i % 2 != 0 and congress_tweets:
        tweets_to_post.append(congress_tweets.pop(0))

# Shuffle remaining if less than 15
if len(tweets_to_post) < 15:
    tweets_to_post += random.sample(bjp_tweets + congress_tweets, 15 - len(tweets_to_post))

# ================= 6. Rephrase + Translate =================
rephraser = pipeline("text2text-generation", model="google/flan-t5-small")
translator = Translator()

for t in tweets_to_post:
    # Rephrase in English (critical tone)
    prompt = f"Rephrase this tweet in English with a critical political tone:\n{t['text']}"
    result = rephraser(prompt, max_length=280)
    t["rephrased"] = result[0]["generated_text"]
    # Translate to Hindi
    t["hindi"] = translator.translate(t["rephrased"], src="en", dest="hi").text

# ================= 7. Post Tweets =================
for t in tweets_to_post:
    try:
        api.update_status(t["hindi"])
        print(f"Posted: {t['hindi']}")
        posted_ids.append(t["id"])
    except Exception as e:
        print("Error posting:", e)

# ================= 8. Save Posted IDs =================
with open(POSTED_FILE, "w") as f:
    json.dump(posted_ids, f)
