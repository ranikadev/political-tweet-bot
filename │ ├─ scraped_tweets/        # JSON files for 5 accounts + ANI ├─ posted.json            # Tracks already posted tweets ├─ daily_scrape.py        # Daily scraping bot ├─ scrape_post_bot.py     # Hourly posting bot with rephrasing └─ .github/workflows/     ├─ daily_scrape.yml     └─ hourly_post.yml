# political_live_archive_bot.py
import tweepy
import json
import random
from googletrans import Translator

# ----------------------------
# Twitter API credentials from GitHub Secrets
# ----------------------------
import os
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ----------------------------
# Political accounts to fetch tweets from
# ----------------------------
PARTIES = {
    "BJP": ["BJP4India", "narendramodi"],
    "Congress": ["INCIndia", "RahulGandhi"]
}

# ----------------------------
# Load posted tweets to avoid duplicates
# ----------------------------
try:
    with open("posted.json", "r") as f:
        posted_ids = json.load(f)
except:
    posted_ids = []

# ----------------------------
# Load or create tweet archive
# ----------------------------
try:
    with open("tweet_archive.json", "r") as f:
        tweet_archive = json.load(f)
except:
    tweet_archive = {party: [] for party in PARTIES}

translator = Translator()

# ----------------------------
# Fetch tweets for each party
# ----------------------------
for party, accounts in PARTIES.items():
    for account in accounts:
        try:
            tweets = api.user_timeline(screen_name=account, count=10, tweet_mode="extended")
            for t in tweets:
                if t.id not in posted_ids and t.full_text not in tweet_archive[party]:
                    tweet_archive[party].append({
                        "id": t.id,
                        "text": t.full_text
                    })
        except Exception as e:
            print(f"Failed to fetch from {account}: {e}")

# ----------------------------
# Select a random tweet from archive and post
# ----------------------------
for party in PARTIES:
    available_tweets = [t for t in tweet_archive[party] if t["id"] not in posted_ids]
    if available_tweets:
        tweet_to_post = random.choice(available_tweets)
        # Translate to Hindi
        hindi_text = translator.translate(tweet_to_post["text"], dest='hi').text
        # Truncate to 280 characters
        hindi_text = hindi_text[:280]
        try:
            api.update_status(hindi_text)
            print(f"Posted tweet for {party}: {hindi_text}")
            posted_ids.append(tweet_to_post["id"])
        except tweepy.TweepError as e:
            print(f"Tweet failed for {party}: {e}")

# ----------------------------
# Save updated posted_ids and archive
# ----------------------------
with open("posted.json", "w") as f:
    json.dump(posted_ids, f)

with open("tweet_archive.json", "w") as f:
    json.dump(tweet_archive, f)

print("Script completed successfully.")
