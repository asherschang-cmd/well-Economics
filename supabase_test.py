"""
supabase_test.py  —  "prove the pipe" script

Goal: confirm that Python can talk to your Supabase database.
If this runs and prints a row, the data half of your project works.

BEFORE YOU RUN THIS, make sure:
  1. Your .env file exists and has SUPABASE_URL and SUPABASE_KEY filled in.
  2. You created a table called "test" in Supabase with columns:
         id    (int8, this is the default primary key)
         name  (text)
  3. Your terminal shows (.venv) at the start of the line.

THEN run it with:
     python supabase_test.py
"""

import os                              # lets us read environment variables
from dotenv import load_dotenv         # reads your .env file
from supabase import create_client     # the Supabase connector

# --- Step 1: load the secrets from your .env file --------------------------
load_dotenv()                          # finds .env and loads it into memory

url = os.environ.get("SUPABASE_URL")   # pulls the value you pasted in .env
key = os.environ.get("SUPABASE_KEY")

# A quick safety check so the error is obvious if .env isn't set up right:
if not url or not key:
    raise SystemExit(
        "ERROR: SUPABASE_URL or SUPABASE_KEY is missing. "
        "Check that your .env file exists and both values are filled in."
    )

# --- Step 2: connect to Supabase -------------------------------------------
supabase = create_client(url, key)
print("Connected to Supabase.")

# --- Step 3: INSERT one row into the 'test' table --------------------------
# This writes a new row with name = "hello from python"
insert_result = supabase.table("test").insert({"name": "hello from python"}).execute()
print("Inserted a row:", insert_result.data)

# --- Step 4: READ the rows back out of the 'test' table --------------------
# This selects everything currently in the table and prints it
read_result = supabase.table("test").select("*").execute()
print("Rows currently in the table:")
for row in read_result.data:
    print("   ", row)

print("\nDone. Now go check the 'test' table in your Supabase dashboard —")
print("you should see the row you just inserted.")
