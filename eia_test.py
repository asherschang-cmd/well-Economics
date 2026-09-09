"""
eia_test.py  —  "prove the data pipe" script

Goal: confirm that Python can pull real oil price data from the EIA
(U.S. Energy Information Administration) API into a pandas table.
If this runs and prints recent WTI crude prices, your data source works.

This is the same idea as supabase_test.py, but instead of proving you can
talk to your database, it proves you can pull the real-world data your
model will run on.

BEFORE YOU RUN THIS, make sure:
  1. Your .env file has a line:  EIA_API_KEY=your-key-here
     (get a free key at https://www.eia.gov/opendata/register.php)
  2. Your terminal shows (.venv) at the start of the line.

THEN run it with:
     python eia_test.py
"""

import os                          # read environment variables
import requests                    # make the web request to EIA
import pandas as pd                # put the data into a table
from dotenv import load_dotenv     # read your .env file

# --- Step 1: load your EIA API key from .env -------------------------------
load_dotenv()
api_key = os.environ.get("EIA_API_KEY")

if not api_key:
    raise SystemExit(
        "ERROR: EIA_API_KEY is missing. Add a line to your .env file:\n"
        "    EIA_API_KEY=your-key-here\n"
        "Get a free key at https://www.eia.gov/opendata/register.php"
    )

# --- Step 2: describe what data we want ------------------------------------
# EIA organizes data into "routes". Crude oil spot prices live at:
#     petroleum/pri/spt
# Within that, WTI crude at Cushing, OK is the series "RWTC".
# We ask for weekly data so we get a clean, manageable history.
url = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

params = {
    "api_key": api_key,
    "frequency": "weekly",
    "data[0]": "value",            # we want the price column
    "facets[series][]": "RWTC",    # RWTC = WTI crude, Cushing OK
    "sort[0][column]": "period",   # sort by date...
    "sort[0][direction]": "desc",  # ...newest first
    "length": 10,                  # just the 10 most recent weeks
}

# --- Step 3: make the request ----------------------------------------------
print("Requesting WTI crude prices from EIA...")
response = requests.get(url, params=params)

# If the key is wrong or the request is malformed, say so clearly:
if response.status_code != 200:
    raise SystemExit(
        f"ERROR: EIA returned status {response.status_code}.\n"
        f"Response: {response.text[:300]}\n"
        "Most common cause: the API key is wrong or not yet active."
    )

# --- Step 4: dig the actual data out of the response -----------------------
# The EIA response is JSON shaped like: {"response": {"data": [ ...rows... ]}}
payload = response.json()
rows = payload["response"]["data"]

if not rows:
    raise SystemExit(
        "Connected to EIA, but no rows came back. "
        "Double-check the series id 'RWTC' and the route."
    )

# --- Step 5: load it into a pandas table and show it -----------------------
df = pd.DataFrame(rows)

# Keep just the two columns we care about, and give them friendly names:
df = df[["period", "value"]].rename(
    columns={"period": "week", "value": "wti_price_usd"}
)

print("\nSuccess! Most recent WTI crude spot prices ($/barrel):\n")
print(df.to_string(index=False))

print(
    "\nThis is real market data pulled live from the EIA. "
    "This is the price feed your economics model will use."
)
