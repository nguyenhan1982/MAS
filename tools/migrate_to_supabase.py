import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load môi trường
load_dotenv(Path(__file__).parent.parent / ".env")

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
BOARD_PATH = WORKSPACE_ROOT / "CenterServer" / "task_board.json"

def migrate():
    from supabase import create_client, Client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("[!] Error: No SUPABASE_URL or SUPABASE_KEY in .env")
        return
        
    print(f"Connecting to Supabase: {url}")
    supabase = create_client(url, key)
    
    if not BOARD_PATH.exists():
        print(f"[!] File not found {BOARD_PATH} to migrate.")
        return
        
    print(f"Reading data from: {BOARD_PATH} ...")
    with open(BOARD_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("Pushing data to Supabase table 'mas_storage' (id=1) ...")
    try:
        response = supabase.table("mas_storage").upsert({"id": 1, "data": data}).execute()
        print("[v] Success migrating to Supabase!")
        print("Now change STORAGE_MODE=supabase in .env to test.")
    except Exception as e:
        print(f"[!] Error pushing to Supabase: {e}")

if __name__ == "__main__":
    migrate()
