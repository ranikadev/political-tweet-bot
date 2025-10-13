import os
import json
import random
from googletrans import Translator
import tweepy
from datetime import datetime
from transformers import pipeline

# ----------------------------
# Twitter API
# ----------------------------
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

translator = Translator()

# ----------------------------
# Load scraped tweets
# ----------------------------
accounts_files = [
    "scraped_tweets/AskAnshul.json",
    "scraped_tweets/sardesairajdeep.json",
    "scraped_tweets/cricketaakash.json",
    "scraped_tweets/talk2anuradha.json",
    "scraped_tweets/theskindoctor13.json",
    "scraped_tweets/ANI.json"
]

tweets_list = []
for file in accounts_files:
    try:
        with open(file, "r") as f:
            for line in f:
                tweet = json.loads(line)
                text = tweet.get("content")
                if text:
                    tweets_list.append(text)
    except Exception as e:
        print(f"[{datetime.now()}] Failed to read {file}: {e}")

# ----------------------------
# Load posted tweets
# ----------------------------
try:
    with open("posted.json", "r") as f:
        posted_tweets = json.load(f)
except:
    posted_tweets = []

# ----------------------------
# Pick a random tweet not posted yet
# ----------------------------
available_tweets = [t for t in tweets_list if t not in posted_tweets]

if not available_tweets:
    print(f"[{datetime.now()}] No new tweets available.")
    exit()

tweet_to_post = random.choice(available_tweets)

# ----------------------------
# Paraphrase and add questioning/controversial tone
# ----------------------------
paraphraser = pipeline("text2text-generation", model="Vamsi/T5_Paraphrase_Paws")
paraphrased = paraphraser(
    f"Paraphrase this in a questioning and slightly controversial tone, max 50 words: {tweet_to_post}",
    max_length=200
)
tweet_to_post_rephrased = paraphrased[0]['generated_text']

# ----------------------------
# Translate to Hindi
# ----------------------------
hindi_tweet = translator.translate(tweet_to_post_rephrased, dest='hi').text

# ----------------------------
# Ensure tweet ≤280 characters
# ----------------------------
if len(hindi_tweet) > 280:
    hindi_tweet = hindi_tweet[:277] + "…"

# ----------------------------
# Post tweet
# ----------------------------
try:
    api.update_status(hindi_tweet)
    print(f"[{datetime.now()}] Tweet posted: {hindi_tweet}")
    posted_tweets.append(tweet_to_post)
except tweepy.TweepError as e:
    print(f"[{datetime.now()}] Tweet failed: {e}")

# ----------------------------
# Save posted tweets
# ----------------------------
with open("posted.json", "w") as f:
    json.dump(posted_tweets, f)
