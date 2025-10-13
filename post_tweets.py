import os
import json
import random
import tweepy
import re
from datetime import datetime
from googletrans import Translator
from collections import Counter

# ------------------------ Twitter Credentials ------------------------
API_KEY = os.environ['API_KEY']
API_SECRET = os.environ['API_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_SECRET = os.environ['ACCESS_SECRET']

auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ------------------------ Translator ------------------------
translator = Translator()

# ------------------------ Files ------------------------
morning_file = "scraped_tweets/morning.json"
evening_file = "scraped_tweets/evening.json"
ir_file = "scraped_tweets/international.json"
posted_today_file = "posted_today.json"

# ------------------------ Prefixes & Emojis ------------------------
prefixes = [
    "Did you notice?", "Controversy:", "People are asking:", "Alert:",
    "Breaking news:", "Shocking update:", "Uncovered:", "Experts question:",
    "What’s happening?:", "Public outrage:", "Revealed today:", "Top story:", "Hot topic:"
]

emojis = ["🚨","⚠️","🔥","❗","📰","👀"]

# Track used prefix/emoji to avoid repetition >2/day, IR_count
if os.path.exists(posted_today_file):
    with open(posted_today_file,"r") as f:
        posted_today = json.load(f)
else:
    posted_today = {"prefix":{},"emoji":{},"IR_count":0}

# ------------------------ Synonyms ------------------------
synonyms = {
    "Corruption":["Fraud","Misuse of power","Scam"],
    "Protest":["Demonstration","Rally","Strike"],
    "Government":["Regime","Administration","Cabinet"],
    "Criticism":["Blame","Accusations","Controversy"],
    "Election":["Vote","Poll","Ballot"],
    "BJP":["Ruling Party"], "Congress":["Opposition Party"],
    "Modi":["PM Modi"], "Rahul Gandhi":["Rahul G."],
    "Farmers":["Agricultural workers"]
}

# Keyword → impacted group mapping
keyword_impact_map = {
    "farmers": "thousands of farmers",
    "protest": "local citizens",
    "election": "voters nationwide",
    "China": "regional security",
    "Pakistan": "border communities",
    "corruption": "public trust",
    "BJP": "supporters and opposition",
    "Congress": "political parties"
}

# ------------------------ Load Headlines ------------------------
def load_headlines(file_path):
    headlines = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    headlines.append(json.loads(line))
                except:
                    continue
    return headlines

# ------------------------ Pick Headline Weighted by Score ------------------------
def pick_headline_weighted(headlines):
    weighted_list = []
    for h in headlines:
        weighted_list.extend([h]*max(int(h.get('score',1)),1))
    if weighted_list:
        return random.choice(weighted_list)
    return None

# ------------------------ Optional Reason & Impact ------------------------
def get_reason_impact(headline_obj, chance=0.2):
    reason = headline_obj.get("reason")
    impact = headline_obj.get("impact")
    
    if not reason and not impact and random.random() <= chance:
        words = re.findall(r'\w+', headline_obj['title'].lower())
        reason_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        if reason_kw:
            reason_templates = [
                f"due to {reason_kw}",
                f"following {reason_kw}",
                f"amid {reason_kw}"
            ]
            reason = random.choice(reason_templates)
        else:
            reason = "due to recent developments"
        impact_kw = next((k for k in keyword_impact_map if k.lower() in words), None)
        impact = keyword_impact_map.get(impact_kw,"affecting the concerned groups")
    
    return reason, impact

# ------------------------ Advanced Rephraser ------------------------
def advanced_rephrase_specific(headline, reason, impact):
    # Prefix
    available_prefixes = [p for p in prefixes if posted_today["prefix"].get(p,0)<2]
    prefix = random.choice(available_prefixes) if available_prefixes else random.choice(prefixes)
    posted_today["prefix"][prefix] = posted_today["prefix"].get(prefix,0)+1

    # Emoji
    available_emojis = [e for e in emojis if posted_today["emoji"].get(e,0)<2]
    emoji = random.choice(available_emojis) if available_emojis else random.choice(emojis)
    posted_today["emoji"][emoji] = posted_today["emoji"].get(emoji,0)+1

    # Synonyms replacement
    words = headline.split()
    new_words = []
    for w in words:
        key = w.strip(".,!?")
        if key in synonyms and random.random()<0.3:
            new_words.append(random.choice(synonyms[key]))
        else:
            new_words.append(w)
    new_title = " ".join(new_words)

    # Final headline construction
    full_text = f"{prefix} {emoji} {new_title}"
    if reason:
        full_text += f" ({reason})"
    if impact:
        full_text += f", impacting {impact}"

    # Truncate if longer than 275 chars
    if len(full_text)>275:
        full_text = full_text[:272]+"..."

    return full_text

# ------------------------ Post Tweet ------------------------
def post_tweet(text):
    try:
        api.update_status(status=text)
        print(f"[{datetime.now()}] ✅ Tweet posted successfully")
    except tweepy.TweepError as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
def main():
    # Load headlines
    morning = load_headlines(morning_file)
    evening = load_headlines(evening_file)
    international = load_headlines(ir_file)

    all_headlines = morning + evening + international
    tweet_obj = None
    tries = 0

    # Pick headline respecting IR limit
    while tries<10:
        candidate = pick_headline_weighted(all_headlines)
        if not candidate:
            break
        if candidate['topic']=="International Relations" and posted_today.get("IR_count",0)>=3:
            tries +=1
            continue
        tweet_obj = candidate
        break

    if not tweet_obj:
        print(f"[{datetime.now()}] ⚠️ No suitable headline found")
        return

    reason, impact = get_reason_impact(tweet_obj)
    tweet_text = advanced_rephrase_specific(tweet_obj['title'], reason, impact)

    # Post tweet
    post_tweet(tweet_text)

    # Update IR count
    if tweet_obj['topic']=="International Relations":
        posted_today["IR_count"] = posted_today.get("IR_count",0)+1

    # Save posted_today.json
    with open(posted_today_file,"w",encoding="utf-8") as f:
        json.dump(posted_today,f,ensure_ascii=False, indent=2)

if __name__=="__main__":
    main()
