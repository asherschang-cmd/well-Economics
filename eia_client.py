"""
eia_client.py  —  shared helper for pulling any series from the EIA API

Every EIA price pull needs the same plumbing: read the key, build the request,
check for errors, dig the data rows out of the JSON, return a clean DataFrame.
Rather than copy that into every script, we write it ONCE here and each dataset
script just calls fetch_eia_series(...) with its own route and series id.

This is a good habit worth showing Asher: when you find yourself about to
copy-paste the same 20 lines into a third file, pull them into a shared helper
instead. One place to fix bugs, one place to understand.
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
EIA_KEY = os.environ.get("EIA_API_KEY")


def fetch_eia_series(route, series_id, frequency="weekly",
                     start=None, value_name="price", length=5000):
    """
    Pull one series from the EIA v2 API and return a tidy DataFrame with
    columns ['date', value_name].

      route      : EIA data route, e.g. 'petroleum/pri/spt'
      series_id  : the specific series, e.g. 'RWTC' (WTI) or 'RNGWHHD' (Henry Hub)
      frequency  : 'daily' | 'weekly' | 'monthly'
      start      : optional 'YYYY-MM-DD' lower bound
      value_name : what to call the value column in the output
      length     : max rows to pull
    """
    if not EIA_KEY:
        raise SystemExit(
            "ERROR: EIA_API_KEY missing from .env. "
            "Get a free key at https://www.eia.gov/opendata/register.php"
        )

    url = f"https://api.eia.gov/v2/{route}/data/"
    params = {
        "api_key": EIA_KEY,
        "frequency": frequency,
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": length,
    }
    if start:
        params["start"] = start

    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        raise SystemExit(
            f"ERROR: EIA returned {resp.status_code} for {route}/{series_id}\n"
            f"{resp.text[:300]}\n"
            "Most common cause: wrong series id, or key not active yet."
        )

    rows = resp.json()["response"]["data"]
    if not rows:
        raise SystemExit(
            f"Connected to EIA but no rows for {route}/{series_id}. "
            "Check the series id."
        )

    df = pd.DataFrame(rows)[["period", "value"]]
    df = df.rename(columns={"period": "date", "value": value_name})
    df[value_name] = pd.to_numeric(df[value_name], errors="coerce")
    df = df.dropna(subset=[value_name]).reset_index(drop=True)
    return df
