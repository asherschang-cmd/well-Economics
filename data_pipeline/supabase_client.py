"""
supabase_client.py  —  shared helper for writing a DataFrame to Supabase

Same idea as eia_client.py: every dataset needs to push its rows into a
Supabase table, so we write that once here. upsert_dataframe handles the
insert-or-update so re-running a pull never creates duplicates.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("ERROR: SUPABASE_URL or SUPABASE_KEY missing from .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_dataframe(table_name, df, conflict_column):
    """
    Write every row of df into table_name. If a row with the same
    conflict_column value already exists, update it instead of duplicating.
    Requires conflict_column to be marked UNIQUE on the table in Supabase.
    """
    client = get_client()
    records = df.to_dict(orient="records")
    client.table(table_name).upsert(records, on_conflict=conflict_column).execute()
    return len(records)
