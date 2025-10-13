import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter

# ------------------------ File paths ------------------------
morning_file = "scraped_tweets/morning.json"
evening_file = "scraped_tweets/evening.json"
ir_file = "scraped_tweets/international.json"

# Ensure the folder exists
os.makedirs("scraped_tweets", exist_ok=True)

# ------------------------ Config ------------------------
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
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            titles = [t.get_text(strip=True) for t in soup.find_all(["h2", "h3", "h4"]) if len(t.get_text(strip=True)) > 20]
            for t in titles:
                headlines.append({"title": t, "url": url})
        except Exception as e:
            print(f"⚠️ Error scraping {url}: {e}")
    return headlines[:50]  # keep top 50 raw headlines


def scrape_international():
    urls = [
        "https://www.thehindu.com/news/international/",
        "https://www.bbc.com/news/world/asia/india",
        "https://indianexpress.com/section/world/",
        "https://timesofindia.indiatimes.com/world",
    ]
    headlines = []
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            titles = [t.get_text(strip=True) for t in soup.find_all(["h2", "h3", "h4"]) if len(t.get_text(strip=True)) > 20]
            for t in titles:
                headlines.append({"title": t, "url": url})
        except Exception as e:
            print(f"⚠️ Error scraping {url}: {e}")
    return headlines[:40]  # fewer for international


# ------------------------ Scoring ------------------------
def assign_scores(headlines):
    all_words = []
    for h in headlines:
        all_words += re.findall(r'\w+', h['title'].lower())
    freq = Counter(all_words)
    
    for h in headlines:
        h_score = 1
        # Keyword frequency score
        for w in re.findall(r'\w+', h['title'].lower()):
            if w in keywords:
                h_score += freq[w]
        # Topic weight
        for k, v in topic_weights.items():
            if k.lower() in h['title'].lower():
                h_score += v
        h['score'] = h_score
    return headlines


# ------------------------ Save JSON ------------------------
def save_json(headlines, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Sort and limit minimum 15 top-scored
    top_items = sorted(headlines, key=lambda x: x['score'], reverse=True)[:max(15, len(headlines)//3)]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(top_items, f, ensure_ascii=False, indent=2)


# ------------------------ Main ------------------------
if __name__ == "__main__":
    morning_headlines = assign_scores(scrape_domestic())
    evening_headlines = assign_scores(scrape_domestic())
    ir_headlines = assign_scores(scrape_international())

    save_json(morning_headlines, morning_file)
    save_json(evening_headlines, evening_file)
    save_json(ir_headlines, ir_file)

    print(f"[{datetime.now()}] ✅ Scraped & saved {len(morning_headlines)} domestic + {len(ir_headlines)} international headlines.")
