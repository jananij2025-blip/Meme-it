
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()


def main():
    print("Testing Meme-it Supabase connection...")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing Supabase credentials in .env")
        return

    try:
        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

        response = (
            supabase.table("meme_users")
            .select("id")
            .limit(1)
            .execute()
        )

        print("SUCCESS: Connected to Supabase!")
        print("SUCCESS: meme_users table is accessible!")
        print("Rows returned:", len(response.data or []))

    except Exception as error:
        print("ERROR: Supabase connection failed.")
        print("Error type:", type(error).__name__)
        print("Details:", str(error))


if __name__ == "__main__":
    main()
