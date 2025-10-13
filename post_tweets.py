import os
import json
import random
import re
from datetime import datetime
import tweepy

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
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

# ------------------------ Helpers ------------------------
def load_headlines(file_path):
    """Load headlines saved as full JSON array."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path,"r",encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data,list) else []
    except json.JSONDecodeError as e:
        print(f"[WARN {datetime.now()}] Failed to load {file_path}: {e}")
        return []

def pick_headline_weighted(headlines):
    """Randomly pick weighted headline based on score."""
    weighted = [h for h in headlines if h.get('score',0)>0]
    if weighted:
        return random.choices(weighted, weights=[h['score'] for h in weighted], k=1)[0]
    return None

# ------------------------ Dummy placeholders ------------------------
prefixes = ["Breaking", "Alert", "Update"]
emojis = ["🚨","🔥","⚡"]
synonyms = {}  # your synonyms map
keyword_impact_map = {}  # your keyword-impact map

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

def advanced_rephrase_specific(headline, reason, impact, sub_headline=None):
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
    if sub_headline:
        full_text += f" – {sub_headline}"
    if reason:
        full_text += f" ({reason})"
    if impact:
        full_text += f", impacting {impact}"

    if len(full_text)>275:
        full_text = full_text[:272]+"..."
    return full_text

# ------------------------ Post Tweet ------------------------
def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Tweet posted successfully")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
def main():
    morning = load_headlines(morning_file)
    evening = load_headlines(evening_file)
    international = load_headlines(ir_file)

    all_headlines = morning + evening + international
    print(f"[DEBUG {datetime.now()}] Total headlines loaded: {len(all_headlines)}")

    if not all_headlines:
        print(f"[ERROR {datetime.now()}] No headlines available at all. Exiting.")
        return

    tweet_obj = None
    tries = 0

    while tries<10:
        candidate = pick_headline_weighted(all_headlines)
        if not candidate:
            break
        if candidate.get('topic')=="International Relations" and posted_today.get("IR_count",0)>=3:
            tries+=1
            continue
        tweet_obj = candidate
        break

    if not tweet_obj:
        print(f"[WARN {datetime.now()}] Weighted pick failed, using fallback headline")
        tweet_obj = random.choice(all_headlines)

    reason, impact = get_reason_impact(tweet_obj)
    tweet_text = advanced_rephrase_specific(
        tweet_obj['title'], 
        reason, 
        impact,
        sub_headline=tweet_obj.get("sub")
    )
    print(f"[DEBUG {datetime.now()}] Selected headline: {tweet_text[:100]}...")

    post_tweet(tweet_text)

    if tweet_obj.get('topic')=="International Relations":
        posted_today["IR_count"] = posted_today.get("IR_count",0)+1

    with open(posted_today_file,"w",encoding="utf-8") as f:
        json.dump(posted_today,f,ensure_ascii=False, indent=2)

if __name__=="__main__":
    main()
