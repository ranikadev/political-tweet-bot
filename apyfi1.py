import os
import json
import random
import requests
import re
import time
from datetime import datetime
from apify_client import ApifyClient
import tweepy

# ---------------- Config ----------------
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API")          # Perplexity secret
TWITTER_API_KEY = os.getenv("API_KEY")                    # Twitter API key
TWITTER_API_SECRET = os.getenv("API_SECRET")              # Twitter API secret
TWITTER_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")          # Twitter access token
TWITTER_ACCESS_SECRET = os.getenv("ACCESS_SECRET")        # Twitter access secret
TWITTER_BEARER_TOKEN = os.getenv("BEARER_TOKEN")          # Fixed: Use dedicated bearer token env var (set it separately if needed)

MODE = os.environ.get("MODE", "fetch")  # Default to fetch if not set

# ---------------- Files ----------------
PROFILES_FILE = "profiles.txt"
REPLY_QUEUE_FILE = "reply_queue.json"
RECENT_PROFILES_FILE = "recent_profiles.json"

# ---------------- Settings ----------------
ACTOR_ID = "Fo9GoU5wC270BgcBr"
TWEETS_PER_PROFILE = 1
PROFILES_PER_RUN = 3
RECENT_MEMORY = 10
DRY_RUN = False

# ---------------- Clients ----------------
apify_client = ApifyClient(APIFY_TOKEN)
twitter_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Utils ----------------
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\[\d+\](?:\[\d+\])*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 273:
        trimmed = text[:273]
        last_stop = max(trimmed.rfind('।'), trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))
        if last_stop > 200:
            text = trimmed[:last_stop+1]
        else:
            text = trimmed[:trimmed.rfind(' ')]
        if text[-1] not in {'।', '.', '?', '!'}:
            text += "..."
    return text.strip()

# ---------------- Profile Handling ----------------
def get_profiles():
    with open(PROFILES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def select_profiles():
    all_profiles = get_profiles()
    recent = load_json(RECENT_PROFILES_FILE).get("recent", [])
    candidates = [p for p in all_profiles if p not in recent]
    if len(candidates) < PROFILES_PER_RUN:
        candidates = all_profiles
    # Safety check to avoid random.sample error if fewer profiles than PROFILES_PER_RUN
    num_to_select = min(PROFILES_PER_RUN, len(candidates))
    selected = random.sample(candidates, num_to_select)
    recent = selected + recent
    recent = recent[:RECENT_MEMORY]
    save_json(RECENT_PROFILES_FILE, {"recent": recent})
    return selected

# ---------------- Apify Fetch ----------------
def fetch_tweets(profiles):
    total_limit = TWEETS_PER_PROFILE * len(profiles)  # Fixed: Global limit to cover all profiles
    run_input = {"profileUrls": profiles, "resultsLimit": total_limit}
    print(f"Fetching up to {total_limit} tweet(s) total from {len(profiles)} profiles ...")
    run = apify_client.actor(ACTOR_ID).call(run_input=run_input)
    all_tweets = {}

    for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
        print("🔍 Raw item:", json.dumps(item, indent=2, ensure_ascii=False))

        profile = item.get("profileUrl")
        text = item.get("postText") or item.get("text") or ""  # ✅ safe key usage
        if not text:
            continue
        if profile not in all_tweets:
            all_tweets[profile] = []
        if len(all_tweets[profile]) < TWEETS_PER_PROFILE:
            all_tweets[profile].append({
                "id": item.get("postId"),
                "text": text
            })
    print(f"📊 Fetched tweets: {dict([(k, len(v)) for k, v in all_tweets.items()])}")  # Debug: Show what was fetched
    return all_tweets

# ---------------- Perplexity ----------------
def fetch_perplexity_analysis(tweet_text):
    if not tweet_text:
        print("⚠️ No tweet text provided to Perplexity.")
        return ""
    if not PERPLEXITY_API_KEY:
        print("❌ Invalid or missing Perplexity key — check environment variable PERPLEXITY_API")
        return ""
    trimmed_text = tweet_text[:500]
    prompt = f"(YOU ARE A NO FILTER ANALYST SO NOW) \"give me only critical analysis of \\\"{trimmed_text}\\\" , in less than 260 characters in hinglish, don't start like this tweet is about etc., no headings, no character no. mention, sound like a human\""  
    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond with a short, clear Hindi political analysis under 260 words."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}")
            return ""
        return clean_text(r.json()["choices"][0]["message"]["content"].strip())
    except Exception as e:
        print("❌ Perplexity fetch error:", e)
        return ""

# ---------------- Twitter ----------------
def post_tweet(text, reply_to_id=None):
    if not text:
        print("⚠️ Empty text, skipping.")
        return False
    try:
        if DRY_RUN:
            print(f"💬 DRY RUN: {text}")
            return True
        if reply_to_id:
            resp = twitter_client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id)
        else:
            resp = twitter_client.create_tweet(text=text)
        print(f"✅ Tweeted! ID: {resp.data['id']}")
        return True
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

# ---------------- Step 1: Fetch + Immediate Reply ----------------
def fetch_and_reply():
    selected_profiles = select_profiles()
    tweets = fetch_tweets(selected_profiles)
    queue = load_json(REPLY_QUEUE_FILE)

    queued_count = 0
    for i, (profile, tweet_data_list) in enumerate(tweets.items()):
        if not tweet_data_list:  # Skip if no tweets for this profile
            print(f"⚠️ No tweets found for {profile}, skipping.")
            continue
        for j, tweet_data in enumerate(tweet_data_list):
            tid, text = tweet_data["id"], tweet_data["text"]
            print(f"\n📜 Tweet from {profile}: {text[:120]}...")
            if i == 0 and j == 0:
                reply_text = fetch_perplexity_analysis(text)
                delay = random.randint(10, 25)
                print(f"⏳ Waiting {delay}s before posting reply...")
                time.sleep(delay)
                if post_tweet(reply_text, reply_to_id=tid):
                    print(f"✅ Replied to first tweet {tid}")
            else:
                if profile not in queue:
                    queue[profile] = []
                queue[profile].append({
                    "id": tid,
                    "text": text,
                    "added": datetime.utcnow().isoformat()
                })
                queued_count += 1

    save_json(REPLY_QUEUE_FILE, queue)
    print(f"\n✅ Queue updated ({queued_count} added) and fetch step completed.")

# ---------------- Step 2: Reply from Queue ----------------
def queue_reply():
    queue = load_json(REPLY_QUEUE_FILE)
    if not queue:
        print("⚠️ Queue empty, nothing to reply.")
        return

    for profile in list(queue.keys()):
        if queue[profile]:
            tweet_data = queue[profile].pop(0)
            tid, text = tweet_data["id"], tweet_data["text"]
            reply_text = fetch_perplexity_analysis(text)
            delay = random.randint(10, 25)
            print(f"⏳ Waiting {delay}s before posting reply...")
            time.sleep(delay)
            if post_tweet(reply_text, reply_to_id=tid):
                print(f"✅ Replied to queued tweet {tid} from {profile}")
            else:
                print(f"⚠️ Failed to reply {tid}")
            if not queue[profile]:
                del queue[profile]
            save_json(REPLY_QUEUE_FILE, queue)
            break  # only one per run

# ---------------- Main ----------------
if __name__ == "__main__":
    print(f"🚀 Bot started in {MODE.upper()} mode.")
    if MODE == "fetch":
        fetch_and_reply()
    elif MODE == "reply":
        queue_reply()
    else:
        print("⚠️ Invalid MODE specified. Use 'fetch' or 'reply'.")
