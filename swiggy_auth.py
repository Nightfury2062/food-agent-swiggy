import os
from dotenv import load_dotenv

load_dotenv()


def get_swiggy_access_token() -> str:
    token = os.getenv("SWIGGY_ACCESS_TOKEN")
    if not token:
        raise SystemExit("No SWIGGY_ACCESS_TOKEN in .env. Run: python get_token.py")
    return token