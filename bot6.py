import os  
import requests  
import tweepy  
import re  
import json  
import random  
from datetime import datetime, timedelta  
import sys  

# ---------------- Environment Variables ----------------  
PERPLEXITY_API = os.getenv("PERPLEXITY_API")  
API_KEY = os.getenv("API_KEY")  
API_SECRET = os.getenv("API_SECRET")  
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  
ACCESS_SECRET = os.getenv("ACCESS_SECRET")  

# ---------------- Files ----------------  
POSTED_FILE = "posted_news.json"  
LAST_CATEGORY_FILE = "last_category.txt"  

# ---------------- Categories ----------------  
CATEGORIES = [
    "Politics & Governance",
    "Economy & Finance",
    "Sports & Events",
    "Crime & Law & Order",
    "Social Issues & Human Interest Stories"
]

def get_prompt(category):
    return f"Give today's most controversy news regarding '{category}', exactly in 260 characters, in Hinglish, only news ( no mention of word count or date , headline, source etc.) just news."

# ---------------- Twitter Setup ----------------  
client = tweepy.Client(  
    consumer_key=API_KEY,  
    consumer_secret=API_SECRET,  
    access_token=ACCESS_TOKEN,  
    access_token_secret=ACCESS_SECRET  
)  

# ---------------- Global Flag ----------------  
DRY_RUN = False  # Set True for manual (no tweet)

# ---------------- Helper Functions ----------------  

def fetch_news(prompt):  
    url = "https://api.perplexity.ai/chat/completions"  
    headers = {  
        "Authorization": f"Bearer {PERPLEXITY_API}",  
        "Content-Type": "application/json"  
    }  
    data = {  
        "model": "sonar",  
        "messages": [  
            {"role": "system", "content": "Respond only with one news item in Hindi, exactly 260 characters."},  
            {"role": "user", "content": prompt}  
        ],  
        "max_tokens": 180  
    }  
    try:  
        response = requests.post(url, headers=headers, json=data, timeout=20)  
        if response.status_code != 200:  
            print(f"❌ API returned status {response.status_code}")  
            return ""  
        resp_json = response.json()  
        news_text = resp_json["choices"][0]["message"]["content"]  
        return news_text.strip()  
    except Exception as e:  
        print("❌ Fetch error:", e)  
        return ""  

def split_news(raw_news):  
    if not raw_news:  
        return []  
    raw_news = re.sub(r'\[\d+\](?:\[\d+\])*', '', raw_news)  
    raw_news = re.sub(r'\s+', ' ', raw_news).strip()  
    if len(raw_news) > 273:  
        trimmed = raw_news[:273].strip()  
        last_sentence = max(trimmed.rfind('।'), trimmed.rfind('?'), trimmed.rfind('!'), -1)  
        if last_sentence > 200:  
            raw_news = trimmed[:last_sentence + 1].strip()  
        else:  
            last_space = trimmed.rfind(' ')  
            if last_space > 200:  
                raw_news = trimmed[:last_space].strip()  
            else:  
                raw_news = trimmed  
        if raw_news[-1] not in {'।', '.', '?', '!'}:  
            raw_news += "..."  
    return [raw_news] if len(raw_news) >= 20 else []  

def save_news(news_list, filename):  
    with open(filename, "w", encoding="utf-8") as f:  
        for n in news_list:  
            f.write(n + "\n")  

def load_posted():  
    if os.path.exists(POSTED_FILE):  
        with open(POSTED_FILE, "r", encoding="utf-8") as f:  
            try:  
                return json.load(f)  
            except:  
                return {}  
    return {}  

def save_posted(posted):  
    with open(POSTED_FILE, "w", encoding="utf-8") as f:  
        json.dump(posted, f, ensure_ascii=False, indent=2)  

def cleanup_posted(days=5):  
    posted = load_posted()  
    cutoff = datetime.utcnow() + timedelta(hours=5, minutes=30) - timedelta(days=days)  
    new_posted = {k: v for k, v in posted.items() if datetime.strptime(v, "%Y-%m-%d") >= cutoff}  
    save_posted(new_posted)  

def post_tweet(text):  
    global DRY_RUN  
    if not DRY_RUN and (API_KEY is None or API_SECRET is None or ACCESS_TOKEN is None or ACCESS_SECRET is None):  
        print("❌ Twitter env vars missing!")  
        return False  
    print(f"[{datetime.now()}] 🔄 Attempting to post ({len(text)} chars): {text[:50]}...")  
    if DRY_RUN:  
        print(f"[{datetime.now()}] ℹ️ DRY RUN: Would post tweet.")  
        return True  
    try:  
        response = client.create_tweet(text=text)  
        print(f"[{datetime.now()}] ✅ Posted successfully! Tweet ID: {response.data['id']}")  
        return True  
    except Exception as e:  
        print(f"❌ Error posting tweet: {e}")  
        return False  

def post_next(news_list=None):  
    posted = load_posted()  
    all_news = news_list if news_list else []
    for news in all_news:    
        if news not in posted:    
            if post_tweet(news):    
                posted[news] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")    
                save_posted(posted)    
            return    
    if all_news:    
        fallback_news = random.choice(all_news)    
        print(f"[{datetime.now()}] ℹ️ All news posted. Posting random again.")    
        post_tweet(fallback_news)  

def get_random_category():
    last_cat = None
    if os.path.exists(LAST_CATEGORY_FILE):
        with open(LAST_CATEGORY_FILE, "r", encoding="utf-8") as f:
            last_cat = f.read().strip()
    available = [c for c in CATEGORIES if c != last_cat]
    if not available:
        available = CATEGORIES
    selected = random.choice(available)
    with open(LAST_CATEGORY_FILE, "w", encoding="utf-8") as f:
        f.write(selected)
    return selected

# ---------------- Main Auto Mode ----------------
if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    cleanup_posted(days=5)

    if mode == "manual":
        DRY_RUN = True
        category_arg = sys.argv[2] if len(sys.argv) > 2 else random.choice(CATEGORIES)
        print(f"Manual fetch for category: {category_arg}")
        raw_news = fetch_news(get_prompt(category_arg))
        news_list = split_news(raw_news)
        if news_list:
            filename = f"{category_arg.replace(' & ', '_').replace(' ', '_').lower()}_news.txt"
            save_news(news_list, filename)
            post_next(news_list)
        sys.exit()

    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hour = now_ist.hour

    # Post hourly between 9 AM – 1 AM IST
    if 9 <= hour <= 23 or 0 <= hour <= 1:
        selected_category = get_random_category()
        print(f"[{now_ist}] 🔄 Fetching news for '{selected_category}'")
        prompt = get_prompt(selected_category)
        raw_news = fetch_news(prompt)
        if not raw_news:
            print(f"⚠️ API returned empty news for {selected_category}")
        else:
            news_list = split_news(raw_news)
            if news_list:
                filename = f"{selected_category.replace(' & ', '_').replace(' ', '_').lower()}_news.txt"
                save_news(news_list, filename)
                post_next(news_list)
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–1 AM IST). No post.")
