import os
import json
import feedparser
from datetime import datetime
import random

# ------------------------ Setup ------------------------
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

# Minimum headlines to ensure per scrape
MIN_HEADLINES = 15

# ------------------------ Determine File ------------------------
hour = datetime.now().hour
filename = "morning.json" if 5 <= hour < 17 else "evening.json"
filepath = f"scraped_tweets/{filename}"

all_headlines = []

# ------------------------ Categorize Headline ------------------------
def categorize_headline(title):
    title_lower = title.lower()
    if any(k in title_lower for k in ["bjp", "modi"]):
        return "BJP"
    elif any(k in title_lower for k in ["congress", "rahul gandhi"]):
        return "Congress"
    else:
        return "Other"

# ------------------------ Fetch Headlines ------------------------
for name, url in feeds.items():
    feed = feedparser.parse(url)
    for entry in feed.entries[:50]:  # fetch more entries
        title = entry.title
        all_headlines.append({
            "title": title,
            "link": entry.link,
            "source": name,
            "topic": categorize_headline(title),
            "keyword_match": any(k.lower() in title.lower() for k in keywords)
        })

# ------------------------ Prioritize Keyword Matches ------------------------
# Keyword headlines first
keyword_headlines = [h for h in all_headlines if h["keyword_match"]]
non_keyword_headlines = [h for h in all_headlines if not h["keyword_match"]]

# Combine, keyword headlines first, remove duplicates
unique_titles = set()
final_headlines = []

for h in keyword_headlines + non_keyword_headlines:
    if h["title"] not in unique_titles:
        final_headlines.append({
            "title": h["title"],
            "link": h["link"],
            "source": h["source"],
            "topic": h["topic"]
        })
        unique_titles.add(h["title"])
    if len(final_headlines) >= MIN_HEADLINES:
        break

# ------------------------ Ensure Minimum Headlines ------------------------
if len(final_headlines) < MIN_HEADLINES:
    # Fill from all feeds randomly
    remaining = MIN_HEADLINES - len(final_headlines)
    candidates = [h for h in all_headlines if h["title"] not in unique_titles]
    random.shuffle(candidates)
    for h in candidates[:remaining]:
        final_headlines.append({
            "title": h["title"],
            "link": h["link"],
            "source": h["source"],
            "topic": h["topic"]
        })

# ------------------------ Save to File ------------------------
with open(filepath, "w", encoding="utf-8") as f:
    for item in final_headlines:
        json.dump(item, f, ensure_ascii=False)
        f.write("\n")

print(f"[{datetime.now()}] ✅ Saved {len(final_headlines)} headlines to {filename}")
