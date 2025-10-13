import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import random

# ------------------------ Folders ------------------------
os.makedirs("scraped_tweets", exist_ok=True)
morning_file = "scraped_tweets/morning.json"
evening_file = "scraped_tweets/evening.json"

# ------------------------ Keyword Scoring ------------------------
keyword_scores = {
    # Political Leaders & Parties
    "BJP":2, "Modi":2, "Amit Shah":2, "Congress":2, "Rahul Gandhi":2, "Sonia Gandhi":2,
    "Opposition":2, "PM":2, "CM":2, "Ministers":2, "MPs":2,

    # Scandal / Corruption
    "Corruption":3, "Scam":3, "Bribery":3, "Nepotism":3, "Cronyism":3,
    "Mismanagement":3, "Fraud":3, "Embezzlement":3, "Criticism":3, "Accusations":3,
    "Blame":3, "Exposed":3, "Shocking":3,

    # Social Issues
    "Lynching":3, "Communal":3, "Religious tension":3, "Caste":3, "Discrimination":3,
    "Inequality":3, "Farmers":3, "Unemployment":3, "Poverty":3, "Rights":3, "Freedom":3,
    "Protest":3, "Violence":3,

    # Policy & Governance
    "Election":2, "Vote":2, "Parliament":2, "Bill":2, "Policy":2, "Reform":2, "Law":2,
    "Regulation":2, "Ban":2, "Restriction":2, "Controversial law":2, "Government order":2,

    # Events & Current Affairs
    "Protests":2, "Rallies":2, "Strikes":2, "Sports":2, "Cricket":2, "Olympics":2,
    "Natural disaster":2, "Flood":2, "Cyclone":2, "Earthquake":2, "Government response":2,

    # Emotive / Attention-grabbing
    "Questioning":1, "Must know":1, "People are asking":1, "Alert":1,
    "Controversy":1, "Uncovered":1, "Breaking":1
}

# ------------------------ Scrape function ------------------------
def fetch_news_from_url(url):
    headlines = []
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        # Example: take all <h3> or <a> tags depending on site
        for h in soup.find_all(['h3','a']):
            text = h.get_text().strip()
            if len(text) > 20:  # skip too short headlines
                headlines.append(text)
    except Exception as e:
        print(f"[{datetime.now()}] ⚠️ Failed to fetch {url}: {e}")
    return headlines

# ------------------------ Scoring ------------------------
def score_headline(title):
    score = 0
    for k, v in keyword_scores.items():
        if k.lower() in title.lower():
            score += v
    return score

# ------------------------ Main ------------------------
def fetch_and_save(file_path, min_count=15):
    urls = [
        "https://www.ndtv.com/latest-news",
        "https://timesofindia.indiatimes.com/india",
        "https://www.indiatoday.in/news",
        "https://www.hindustantimes.com/india-news"
    ]

    all_headlines = []
    for url in urls:
        headlines = fetch_news_from_url(url)
        for h in headlines:
            s = score_headline(h)
            all_headlines.append({
                "title": h,
                "link": url,
                "topic": "Politics/Current Affairs",
                "score": s
            })

    # Remove duplicates & sort by score descending
    seen = set()
    unique_headlines = []
    for h in sorted(all_headlines, key=lambda x: x['score'], reverse=True):
        if h['title'] not in seen:
            unique_headlines.append(h)
            seen.add(h['title'])
        if len(unique_headlines) >= min_count:
            break

    # Save JSON
    with open(file_path, "w", encoding="utf-8") as f:
        for h in unique_headlines:
            json.dump(h, f, ensure_ascii=False)
            f.write("\n")
    print(f"[{datetime.now()}] ✅ Saved {len(unique_headlines)} headlines to {file_path}")

# ------------------------ Run ------------------------
fetch_and_save(morning_file, min_count=15)
fetch_and_save(evening_file, min_count=15)
