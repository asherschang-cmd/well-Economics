"""
pull_forecast.py  —  pull EIA STEO forward price forecasts

The Short-Term Energy Outlook (STEO) is EIA's official forward price deck —
where they think oil and gas prices are headed over the next ~1-2 years.
This gives Asher's model a defensible forward price for scenario analysis
instead of him guessing future prices.

Fills:
    price_forecast : product ('oil'|'gas'), month, forecast price, source='EIA STEO'

Route is 'steo'; the facet is 'seriesId' (STEO uses a different facet name than
the spot-price routes). Oil = WTIPUUS ($/bbl), Gas = NGHHUUS ($/MMBtu).

Run:  python -m data_pipeline.pull_forecast
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv
from data_pipeline.supabase_client import upsert_dataframe

load_dotenv()
EIA_KEY = os.environ.get("EIA_API_KEY")

# STEO series: WTI crude and Henry Hub gas forecasts
FORECAST_SERIES = [
    ("oil", "WTIPUUS"),   # WTI spot price forecast, $/bbl
    ("gas", "NGHHUUS"),   # Henry Hub spot price forecast, $/MMBtu
]


def fetch_steo(series_id):
    url = "https://api.eia.gov/v2/steo/data/"
    params = {
        "api_key": EIA_KEY,
        "frequency": "monthly",
        "data[0]": "value",
        "facets[seriesId][]": series_id,     # NOTE: seriesId, not series
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 5000,
    }
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        raise SystemExit(f"ERROR: STEO {series_id} returned {resp.status_code}\n"
                         f"{resp.text[:300]}")
    rows = resp.json()["response"]["data"]
    df = pd.DataFrame(rows)[["period", "value"]]
    df = df.rename(columns={"period": "month", "value": "forecast_price"})
    df["forecast_price"] = pd.to_numeric(df["forecast_price"], errors="coerce")
    df = df.dropna(subset=["forecast_price"])
    return df


def run():
    if not EIA_KEY:
        raise SystemExit("ERROR: EIA_API_KEY missing from .env")

    all_rows = []
    for product, series in FORECAST_SERIES:
        print(f"Pulling STEO forecast for {product} ({series})...")
        df = fetch_steo(series)
        df["product"] = product
        df["source"] = "EIA STEO"
        # keep only forecast months (STEO includes recent history + forward)
        all_rows.append(df)
        print(f"  got {len(df)} monthly points "
              f"({df['month'].min()} -> {df['month'].max()})")

    combined = pd.concat(all_rows, ignore_index=True)
    # unique key for upsert = product + month
    combined["id"] = combined["product"] + "_" + combined["month"]
    combined = combined[["id", "product", "month", "forecast_price", "source"]]
    combined.to_csv("price_forecast.csv", index=False)
    print(f"\nSaved {len(combined)} forecast rows to price_forecast.csv")

    try:
        n = upsert_dataframe("price_forecast", combined, conflict_column="id")
        print(f"Wrote {n} rows to Supabase table 'price_forecast'")
    except Exception as e:
        print(f"(Supabase write skipped: {e})")
        print("-> create table 'price_forecast' with columns id (text, UNIQUE), "
              "product (text), month (text), forecast_price (float8), source (text), "
              "RLS off, then re-run.")


if __name__ == "__main__":
    run()
