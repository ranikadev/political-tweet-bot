import os
import re
import json
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter

# ------------------------ Paths ------------------------
base_dir = os.path.join(os.getcwd(), "scraped_tweets")
os.makedirs(base_dir, exist_ok=True)
morning_file = os.path.join(base_dir, "morning.json")
evening_file = os.path.join(base_dir, "evening.json")
ir_file = os.path.join(base_dir, "international.json")

# ------------------------ Config ------------------------
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/127.0.0.1 Safari/537.36"
}

keywords = [
    "bjp", "congress", "rahul", "modi", "india", "election", "violence",
    "lynching", "corruption", "protest", "china", "pakistan", "usa",
    "cricket", "sports", "discrimination", "reservation", "scandal"
]

topic_weights = {
    "BJP": 3,
    "Congress": 3,
    "corruption": 3,
    "lynching": 3,
    "cricket": 2,
    "sports": 1,
    "China": 2,
    "Pakistan": 2,
    "USA": 2,
    "election": 3,
    "violence": 2,
    "discrimination": 2,
}

# ------------------------ Scraping functions ------------------------
def extract_headlines(url):
    """Scrape h1/h2/h3/h4 text from URL."""
    headlines = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {url} -> HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        tags = soup.find_all(["h1", "h2", "h3", "h4"])
        for t in tags:
            text = t.get_text(strip=True)
            if 25 < len(text) < 180:
                headlines.append({"title": text, "url": url})
        print(f"✅ {url}: {len(headlines)} headlines")
    except Exception as e:
        print(f"❌ {url}: {e}")
    return headlines

def scrape_domestic():
    urls = [
        "https://timesofindia.indiatimes.com/",
        "https://www.ndtv.com/latest",
        "https://www.indiatoday.in/",
        "https://www.jagran.com/",
        "https://www.aajtak.in/",
        "https://www.abplive.com/news",
        "https://www.bhaskar.com/national/"
    ]
    headlines = []
    for url in urls:
        headlines += extract_headlines(url)
    return headlines[:80]  # limit for safety

def scrape_international():
    urls = [
        "https://www.thehindu.com/news/international/",
        "https://www.bbc.com/news/world/asia/india",
        "https://indianexpress.com/section/world/",
        "https://timesofindia.indiatimes.com/world"
    ]
    headlines = []
    for url in urls:
        headlines += extract_headlines(url)
    return headlines[:50]

# ------------------------ Scoring ------------------------
def assign_scores(headlines):
    all_words = []
    for h in headlines:
        all_words += re.findall(r'\w+', h['title'].lower())
    freq = Counter(all_words)

    for h in headlines:
        h_score = 1
        for w in re.findall(r'\w+', h['title'].lower()):
            if w in keywords:
                h_score += freq[w]
        for k, v in topic_weights.items():
            if k.lower() in h['title'].lower():
                h_score += v
        h['score'] = h_score
    return headlines

# ------------------------ Save JSON lines ------------------------
def save_json(headlines, file_path, min_items=15):
    sorted_headlines = sorted(headlines, key=lambda x: x.get('score', 1), reverse=True)
    
    # Ensure minimum items
    if len(sorted_headlines) < min_items:
        for i in range(min_items - len(sorted_headlines)):
            sorted_headlines.append({
                "title": f"Placeholder news {i+1}",
                "score": 1,
                "topic": "Misc",
                "url": ""
            })

    top_items = sorted_headlines[:min_items]

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        for item in top_items:
            json.dump(item, f, ensure_ascii=False)
            f.write("\n")

    print(f"💾 Saved {len(top_items)} -> {file_path}")

# ------------------------ Main ------------------------
if __name__ == "__main__":
    print(f"\n🕒 Fetch started at {datetime.now()}\n")

    morning_headlines = assign_scores(scrape_domestic())
    evening_headlines = assign_scores(scrape_domestic())
    ir_headlines = assign_scores(scrape_international())

    save_json(morning_headlines, morning_file)
    save_json(evening_headlines, evening_file)
    save_json(ir_headlines, ir_file)

    print(f"\n✅ Completed at {datetime.now()}\n")
