import os
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv(Path(__file__).resolve().parent / ".env")

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")


SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
SNOWFLAKE_TABLE = os.getenv("SNOWFLAKE_TABLE", "STOCK_TICKERS")

LIMIT = 100


def with_api_key(url, api_key):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["apiKey"] = [api_key]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def fetch_tickers_page(url, api_key, retries=8):
    page_url = with_api_key(url, api_key)
    for attempt in range(1, retries + 1):
        response = requests.get(page_url, timeout=60)
        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 12 * attempt))
            print(f"Rate limited, waiting {wait}s (attempt {attempt}/{retries})")
            time.sleep(wait)
            continue

        response.raise_for_status()
        data = response.json()
        if "results" in data:
            return data

        error = data.get("error") or data.get("message") or data
        error_text = str(error).lower()
        if "exceeded" in error_text or "too many" in error_text or "rate" in error_text:
            wait = 12 * attempt
            print(f"API rate limit in body, waiting {wait}s (attempt {attempt}/{retries})")
            time.sleep(wait)
            continue

        raise RuntimeError(f"Ticker API response missing results: {error}")

    raise RuntimeError("Ticker API failed after retries")


url = (
    "https://api.massive.com/v3/reference/tickers"
    f"?market=stocks&active=true&order=asc&limit={LIMIT}&sort=ticker"
)

tickers = []
data = fetch_tickers_page(url, POLYGON_API_KEY)
tickers.extend(data.get("results", []))

while data.get("next_url"):
    print("Fetching next page", data["next_url"])
    data = fetch_tickers_page(data["next_url"], POLYGON_API_KEY)
    tickers.extend(data.get("results", []))
    time.sleep(12)

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
df = pd.DataFrame(tickers)
df = df.reindex(columns=fieldnames)
df["ds"] = date.today()
df.columns = [col.upper() for col in df.columns]

conn = snowflake.connector.connect(
    account=SNOWFLAKE_ACCOUNT,
    user=SNOWFLAKE_USER,
    password=SNOWFLAKE_PASSWORD,
    warehouse=SNOWFLAKE_WAREHOUSE,
)

with conn.cursor() as cur:
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {SNOWFLAKE_DATABASE}")
    cur.execute(f"USE DATABASE {SNOWFLAKE_DATABASE}")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SNOWFLAKE_SCHEMA}")
    cur.execute(f"USE SCHEMA {SNOWFLAKE_SCHEMA}")
    cur.execute(f"USE WAREHOUSE {SNOWFLAKE_WAREHOUSE}")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SNOWFLAKE_TABLE} (
            TICKER VARCHAR,
            NAME VARCHAR,
            MARKET VARCHAR,
            LOCALE VARCHAR,
            PRIMARY_EXCHANGE VARCHAR,
            TYPE VARCHAR,
            ACTIVE BOOLEAN,
            CURRENCY_NAME VARCHAR,
            COMPOSITE_FIGI VARCHAR,
            SHARE_CLASS_FIGI VARCHAR,
            LAST_UPDATED_UTC TIMESTAMP_TZ,
            DS DATE
        )
        """
    )
    cur.execute(f"ALTER TABLE {SNOWFLAKE_TABLE} ADD COLUMN IF NOT EXISTS DS DATE")
    cur.execute(f"TRUNCATE TABLE {SNOWFLAKE_TABLE}")

success, nchunks, nrows, _ = write_pandas(
    conn,
    df,
    SNOWFLAKE_TABLE,
    database=SNOWFLAKE_DATABASE,
    schema=SNOWFLAKE_SCHEMA,
    quote_identifiers=False,
)
conn.close()

print(len(tickers))
print(f"Loaded {nrows} rows into {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}")
