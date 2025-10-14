import os
import random
import time
import requests
import tweepy
from datetime import datetime

# Environment variables
PERPLEXITY_API = os.getenv("PERPLEXITY_API")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")

# X (Twitter) client setup
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Prompts with probability (total 12)
PROMPTS = [
    ("भारत में आज की एक सकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 4),
    ("बीजेपी से जुड़ी एक सकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
    ("कांग्रेस से जुड़ी एक सकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
    ("कांग्रेस से जुड़ी एक नकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
    ("बीजेपी से जुड़ी एक नकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
    ("दुनिया की एक सकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 2),
    ("दुनिया की एक नकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
    ("भारत की एक नकारात्मक खबर, 250 अक्षरों से कम में हिंदी में बताइए।", 1),
]

def choose_prompt():
    total = sum(weight for _, weight in PROMPTS)
    r = random.uniform(0, total)
    upto = 0
    for prompt, weight in PROMPTS:
        if upto + weight >= r:
            return prompt
        upto += weight

def query_perplexity(prompt):
    """Query Perplexity with sonar model."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond only with one clear Hindi news item under 250 characters."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    return text.strip()

def clean_text(text):
    """Remove duplication and non-relevant second news."""
    # If there are multiple news separated by '।' or newline, take first one
    if "।" in text:
        first = text.split("।")[0] + "।"
    elif "\n" in text:
        first = text.split("\n")[0]
    else:
        first = text
    # Remove repetition like "घटना घटना" or "हुआ हुआ"
    words = first.split()
    cleaned_words = []
    for i, w in enumerate(words):
        if i == 0 or w != words[i-1]:
            cleaned_words.append(w)
    cleaned = " ".join(cleaned_words)
    # Light human touch
    cleaned = cleaned.replace("है है", "है").replace("हुआ हुआ", "हुआ")
    cleaned = cleaned.strip()
    return cleaned[:250]

def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Posted: {text}")
    except Exception as e:
        print(f"❌ Tweet failed: {e}")

def main():
    prompt = choose_prompt()
    print(f"🎯 Prompt: {prompt}")
    text = query_perplexity(prompt)
    final_text = clean_text(text)
    post_tweet(final_text)

if __name__ == "__main__":
    main()
