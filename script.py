import os

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
SNOWFLAKE_TABLE = os.getenv("SNOWFLAKE_TABLE", "STOCK_TICKERS")

LIMIT = 100

url = (
    "https://api.massive.com/v3/reference/tickers"
    f"?market=stocks&active=true&order=asc&limit={LIMIT}&sort=ticker"
    f"&apiKey={POLYGON_API_KEY}"
)

response = requests.get(url)
tickers = []

data = response.json()
for ticker in data["results"]:
    tickers.append(ticker)

while "next_url" in data:
    print("Fetching next page", data["next_url"])
    response = requests.get(data["next_url"] + f"&apiKey={POLYGON_API_KEY}")
    data = response.json()
    for ticker in data["results"]:
        tickers.append(ticker)

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
            LAST_UPDATED_UTC TIMESTAMP_TZ
        )
        """
    )
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
