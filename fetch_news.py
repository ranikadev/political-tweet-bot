import os
import json
import feedparser
from datetime import datetime

os.makedirs("scraped_tweets", exist_ok=True)

feeds = {
    "ANI": "https://www.aninews.in/rssfeed.xml",
    "NDTV": "https://feeds.feedburner.com/ndtvnews-politics",
    "Hindu": "https://www.thehindu.com/news/national/feeder/default.rss",
    "IE": "https://indianexpress.com/section/india/feed/"
}

keywords = [
    "BJP", "Congress", "Modi", "Rahul Gandhi", "election", "corruption",
    "lynching", "discrimination", "cricket", "policy", "government"
]

# Determine morning or evening scrape
hour = datetime.now().hour
if 5 <= hour < 17:
    filename = "morning.json"
else:
    filename = "evening.json"

all_headlines = []

def categorize_headline(title):
    title_lower = title.lower()
    if any(k in title_lower for k in ["bjp", "modi"]):
        return "BJP"
    elif any(k in title_lower for k in ["congress", "rahul gandhi"]):
        return "Congress"
    else:
        return "Other"

for name, url in feeds.items():
    feed = feedparser.parse(url)
    filtered = []
    for entry in feed.entries[:30]:  # latest 30 headlines
        headline = entry.title
        if any(k.lower() in headline.lower() for k in keywords):
            filtered.append({
                "title": headline,
                "link": entry.link,
                "source": name,
                "topic": categorize_headline(headline)
            })
    all_headlines.extend(filtered)
    print(f"[{datetime.now()}] ✅ {len(filtered)} headlines from {name}")

# Save combined headlines
filepath = f"scraped_tweets/{filename}"
with open(filepath, "w", encoding="utf-8") as f:
    for item in all_headlines:
        json.dump(item, f, ensure_ascii=False)
        f.write("\n")

print(f"[{datetime.now()}] ✅ Saved total {len(all_headlines)} headlines to {filename}")
