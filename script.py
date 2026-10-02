import csv
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

print(POLYGON_API_KEY)

# Massive Basic/trial: 5 REST requests per minute.
LIMIT = 100
MAX_PAGES = 5
REQUEST_INTERVAL_SECONDS = 60 / MAX_PAGES

url = (
    "https://api.massive.com/v3/reference/tickers"
    f"?market=stocks&active=true&order=asc&limit={LIMIT}&sort=ticker"
    f"&apiKey={POLYGON_API_KEY}"
)

tickers = []
pages_fetched = 0

response = requests.get(url)
data = response.json()
pages_fetched += 1

if "results" in data:
    tickers.extend(data["results"])

while "next_url" in data and pages_fetched < MAX_PAGES:
    time.sleep(REQUEST_INTERVAL_SECONDS)
    print("Fetching next page", data["next_url"])
    response = requests.get(data["next_url"] + f"&apiKey={POLYGON_API_KEY}")
    data = response.json()
    pages_fetched += 1
    print(data)
    if "results" in data:
        tickers.extend(data["results"])

example_ticker = {
    "ticker": "GLWG",
    "name": "Leverage Shares 2X Long GLW Daily ETF",
    "market": "stocks",
    "locale": "us",
    "primary_exchange": "XNAS",
    "type": "ETF",
    "active": True,
    "currency_name": "usd",
    "composite_figi": "BBG020TYT571",
    "share_class_figi": "BBG020TYT679",
    "last_updated_utc": "2026-10-02T06:11:31.447023594Z",
}

fieldnames = list(example_ticker.keys())
output_path = "tickers.csv"

with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(
        csvfile,
        fieldnames=fieldnames,
        extrasaction="ignore",
        restval="",
    )
    writer.writeheader()
    writer.writerows(tickers)

print(len(tickers))
print(f"Wrote {len(tickers)} rows to {output_path}")
