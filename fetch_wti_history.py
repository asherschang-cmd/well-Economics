"""
fetch_wti_history.py  —  pull 10 years of WTI crude prices, save to CSV + Supabase

This is a step up from eia_test.py. Instead of just printing 10 weeks to prove
the connection works, this pulls a full 10-year weekly price history and does
two things with it:
  1. Saves it to a CSV file (wti_prices.csv) you can open in Excel or load in a notebook
  2. Writes it into a Supabase table (wti_prices) so your dashboard can read it

This is the real price feed your economics model will run on.

BEFORE YOU RUN THIS, make sure:
  1. Your .env has BOTH:
        EIA_API_KEY=your-eia-key
        SUPABASE_URL=your-project-url
        SUPABASE_KEY=your-anon-key
  2. You created a table called "wti_prices" in Supabase with columns:
        week   (text)     <- the date of the price
        price  (float8)   <- the WTI price in dollars
     (Turn OFF Row Level Security on it, like you did for the test table.)
  3. Your terminal shows (.venv).

THEN run it with:
     python fetch_wti_history.py
"""

import os
from datetime import date, timedelta

import requests
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# --- Step 1: load all our keys from .env -----------------------------------
load_dotenv()
eia_key = os.environ.get("EIA_API_KEY")
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not eia_key:
    raise SystemExit("ERROR: EIA_API_KEY missing from .env")
if not supabase_url or not supabase_key:
    raise SystemExit("ERROR: SUPABASE_URL or SUPABASE_KEY missing from .env")

# --- Step 2: work out the date 10 years ago --------------------------------
# We ask EIA only for data on or after this date.
ten_years_ago = (date.today() - timedelta(days=365 * 10)).isoformat()
print(f"Pulling WTI weekly prices since {ten_years_ago}...")

# --- Step 3: ask EIA for the data ------------------------------------------
url = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
params = {
    "api_key": eia_key,
    "frequency": "weekly",
    "data[0]": "value",
    "facets[series][]": "RWTC",     # WTI crude, Cushing OK
    "start": ten_years_ago,         # only data from the last 10 years
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",   # newest first
    "length": 5000,                 # plenty to cover 10 years of weeks (~520)
}

response = requests.get(url, params=params)
if response.status_code != 200:
    raise SystemExit(
        f"ERROR: EIA returned status {response.status_code}.\n"
        f"{response.text[:300]}"
    )

rows = response.json()["response"]["data"]
if not rows:
    raise SystemExit("Connected to EIA but got no rows back. Check the series id.")

print(f"Got {len(rows)} weeks of price data from EIA.")

# --- Step 4: clean it into a tidy table ------------------------------------
df = pd.DataFrame(rows)
df = df[["period", "value"]].rename(columns={"period": "week", "value": "price"})

# EIA sometimes returns the price as text; make sure it's a real number,
# and drop any weeks where the price is missing.
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df = df.dropna(subset=["price"])

print("\nMost recent few weeks:")
print(df.head().to_string(index=False))
print(f"\nOldest week in the pull: {df['week'].min()}")
print(f"Newest week in the pull: {df['week'].max()}")

# --- Step 5: save to a CSV file --------------------------------------------
df.to_csv("wti_prices.csv", index=False)
print(f"\nSaved {len(df)} rows to wti_prices.csv")

# --- Step 6: write to Supabase ---------------------------------------------
# We turn the table into a list of {"week": ..., "price": ...} dictionaries,
# which is the shape Supabase wants for an insert.
supabase = create_client(supabase_url, supabase_key)
records = df.to_dict(orient="records")

# upsert = insert, but if a week already exists, update it instead of
# creating a duplicate. This means you can safely re-run this script.
supabase.table("wti_prices").upsert(records, on_conflict="week").execute()
print(f"Wrote {len(records)} rows to the 'wti_prices' table in Supabase.")

print("\nDone. Your 10-year WTI price history now lives in two places:")
print("  - wti_prices.csv (for notebooks / Excel)")
print("  - the wti_prices table in Supabase (for your dashboard)")
