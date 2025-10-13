import requests
from bs4 import BeautifulSoup
import json
import random
import re
from collections import Counter
import os
from datetime import datetime
import os

# Ensure folders exist for storing scraped data
os.makedirs("scraped_tweets", exist_ok=True)
# ------------------------ Files ------------------------
morning_file = "scraped_tweets/morning.json"
evening_file = "scraped_tweets/evening.json"
ir_file = "scraped_tweets/international.json"

# ------------------------ Sources ------------------------
domestic_sources = [
    "https://www.amarujala.com/", 
    "https://www.navbharattimes.indiatimes.com/",
    "https://www.bhaskar.com/",
    "https://www.jagran.com/"
]

international_sources = [
    "https://www.reuters.com/",
    "https://www.bbc.com/news",
    "https://www.aljazeera.com/",
    "https://www.cnn.com/"
]

keywords = ["corruption","protest","BJP","Congress","election","farmers","China","Pakistan","Modi","Rahul Gandhi"]

topic_weights = {
    "corruption":2,
    "protest":2,
    "BJP":2,
    "Congress":2,
    "election":2,
    "International Relations":1.5
}

# ------------------------ Scrape Headlines ------------------------
def scrape_domestic():
    all_headlines = []
    for url in domestic_sources:
        try:
            r = requests.get(url, timeout=5)
            soup = BeautifulSoup(r.text,"html.parser")
            for a in soup.find_all("a", href=True):
                text = a.get_text().strip()
                link = a['href']
                if text and len(text)>20:
                    all_headlines.append({"title":text, "topic":"Domestic Politics", "url":link})
        except:
            continue
    random.shuffle(all_headlines)
    return all_headlines[:15]

def scrape_international():
    all_headlines = []
    for url in international_sources:
        try:
            r = requests.get(url, timeout=5)
            soup = BeautifulSoup(r.text,"html.parser")
            for a in soup.find_all("a", href=True):
                text = a.get_text().strip()
                link = a['href']
                if text and len(text)>20:
                    all_headlines.append({"title":text, "topic":"International Relations", "url":link})
        except:
            continue
    random.shuffle(all_headlines)
    return all_headlines[:15]

# ------------------------ Compute Dynamic Score ------------------------
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
    with open(file_path,"w",encoding="utf-8") as f:
        for h in headlines:
            json.dump(h, f, ensure_ascii=False)
            f.write("\n")

# ------------------------ Main ------------------------
morning_headlines = assign_scores(scrape_domestic())
evening_headlines = assign_scores(scrape_domestic())
ir_headlines = assign_scores(scrape_international())

save_json(morning_headlines, morning_file)
save_json(evening_headlines, evening_file)
save_json(ir_headlines, ir_file)

print(f"[{datetime.now()}] ✅ Scraped & saved: {len(morning_headlines)} morning, {len(evening_headlines)} evening, {len(ir_headlines)} international headlines.")
