import os
import json
import random
import tweepy
import re
from datetime import datetime
from googletrans import Translator

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
def pick_headline(headlines):
    weighted_list = []
    for h in headlines:
        weighted_list.extend([h]*max(h.get('score',1),1))
    if weighted_list:
        return random.choice(weighted_list)
    return None

# ------------------------ Optional Reason & Impact ------------------------
def get_reason_impact(headline_obj, chance=0.2):
    reason = headline_obj.get("reason")
    impact = headline_obj.get("impact")
    
    if not reason and not impact and random.random() <= chance:
        words = re.findall(r'\w+', headline_obj['title'].lower())
        
        # Reason
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
        
        # Impact
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

    # Add reason + impact if present
    extra = ""
    if reason: extra += f", {reason}"
    if impact: extra += f", {impact}"

    base_text = f"{emoji} {prefix} {new_title}{extra}."
    
    if len(base_text)>275:
        base_text = base_text[:272]+"..."
    elif len(base_text)<250:
        base_text += " Stay updated."
    return base_text

# ------------------------ Post Tweet ------------------------
def post_tweet(headline_obj):
    try:
        reason, impact = get_reason_impact(headline_obj)
        text_en = advanced_rephrase_specific(headline_obj['title'], reason, impact)
        
        # Translate to Hindi
        try:
            text_hi = translator.translate(text_en, src='en', dest='hi').text
        except:
            text_hi = text_en

        api.update_status(text_hi)
        print(f"[{datetime.now()}] ✅ Posted: {text_hi}")

        # Update IR count if needed
        if headline_obj.get('topic')=='International Relations':
            posted_today["IR_count"] = posted_today.get("IR_count",0)+1

        # Save posted_today
        with open(posted_today_file,"w") as f:
            json.dump(posted_today,f)
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to post tweet: {e}")

# ------------------------ Main ------------------------
current_hour = datetime.now().hour
file_to_use = morning_file if 6 <= current_hour < 12 else evening_file

# Load all headlines
all_headlines = load_headlines(file_to_use) + load_headlines(ir_file)

# Separate IR and domestic
ir_headlines = [h for h in all_headlines if h.get('topic')=='International Relations']
domestic_headlines = [h for h in all_headlines if h.get('topic')!='International Relations']

# Apply IR limit: max 3/day
if posted_today.get("IR_count",0) >=3:
    eligible_headlines = domestic_headlines
else:
    eligible_headlines = domestic_headlines + ir_headlines

# Pick headline
if eligible_headlines:
    headline = pick_headline(eligible_headlines)
    if headline:
        post_tweet(headline)
    else:
        print(f"[{datetime.now()}] ⚠️ No headline picked")
else:
    print(f"[{datetime.now()}] ⚠️ No headlines available to post")
