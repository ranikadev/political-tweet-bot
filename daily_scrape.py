import os
import json
import subprocess
from datetime import datetime
import tweepy

# ----------------------------
# Twitter API (for ANI)
# ----------------------------
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ----------------------------
# Other 5 accounts
# ----------------------------
accounts = [
    "AskAnshul",
    "sardesairajdeep",
    "cricketaakash",
    "talk2anuradha",
    "theskindoctor13"
]

os.makedirs("scraped_tweets", exist_ok=True)

# Scrape last 5 tweets per account
for account in accounts:
    output_file = f"scraped_tweets/{account}.json"
    cmd = f"snscrape --jsonl --max-results 5 twitter-user {account} > {output_file}"
    subprocess.run(cmd, shell=True)
    print(f"[{datetime.now()}] Scraped last 5 tweets from @{account}")

# ----------------------------
# Fetch last 5 tweets from @ANI via API
# ----------------------------
ani_file = "scraped_tweets/ANI.json"
try:
    ani_tweets = api.user_timeline(screen_name="ANI", count=5, tweet_mode='extended')
    ani_texts = [{"content": t.full_text} for t in ani_tweets]
    with open(ani_file, "w") as f:
        for t in ani_texts:
            json.dump(t, f)
            f.write("\n")
    print(f"[{datetime.now()}] Fetched last 5 tweets from @ANI")
except tweepy.TweepError as e:
    print(f"[{datetime.now()}] Failed to fetch @ANI tweets: {e}")
