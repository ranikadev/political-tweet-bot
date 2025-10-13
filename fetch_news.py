import os
import json
import feedparser
from datetime import datetime
import random

# Create folder if not exists
os.makedirs("scraped_tweets", exist_ok=True)

# RSS feeds
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

# Determine file name based on current hour
hour = datetime.now().hour
filename = "morning.json" if 5 <= hour < 17 else "evening.json"
filepath = f"scraped_tweets/{filename}"

all_headlines = []

def categorize_headline(title):
    title_lower = title.lower()
    if any(k in title_lower for k in ["bjp", "modi"]):
        return "BJP"
    elif any(k in title_lower for k in ["congress", "rahul gandhi"]):
        return "Congress"
    else:
        return "Other"

# Fetch headlines
for name, url in feeds.items():
    feed = feedparser.parse(url)
    for entry in feed.entries[:30]:  # latest 30 headlines
        title = entry.title
        if any(k.lower() in title.lower() for k in keywords):
            all_headlines.append({
                "title": title,
                "link": entry.link,
                "source": name,
                "topic": categorize_headline(title)
            })

# Ensure at least 5 headlines
if len(all_headlines) < 5:
    # Take random headlines from feeds ignoring keywords if needed
    for name, url in feeds.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            candidate = {
                "title": entry.title,
                "link": entry.link,
                "source": name,
                "topic": categorize_headline(entry.title)
            }
            if candidate not in all_headlines:
                all_headlines.append(candidate)
            if len(all_headlines) >= 5:
                break
        if len(all_headlines) >= 5:
            break

# Save to JSON Lines file
with open(filepath, "w", encoding="utf-8") as f:
    for item in all_headlines:
        json.dump(item, f, ensure_ascii=False)
        f.write("\n")

print(f"[{datetime.now()}] ✅ Saved {len(all_headlines)} headlines to {filename}")
