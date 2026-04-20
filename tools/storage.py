import os
import time
import random
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Tự động xác định thư mục gốc của CenterServer
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

_supabase_client = None
STORAGE_MODE = "Supabase" # Mac dinh dung Cloud cho moi truong Votranh Hybrid

def get_supabase_client():
    global _supabase_client
    if _supabase_client is None:
        # Cơ chế Retry cho việc khởi tạo Client
        for attempt in range(3):
            try:
                url: str = os.environ.get("SUPABASE_URL", "").strip()
                key: str = os.environ.get("SUPABASE_KEY", "").strip()
                if not url or not key:
                    print("[!] Error: Missing SUPABASE_URL or SUPABASE_KEY in configuration.")
                    return None
                _supabase_client = create_client(url, key)
                if _supabase_client: break
            except Exception as e:
                print(f"[!] Supabase Init Error (Attempt {attempt+1}): {e}")
                time.sleep(2)
    return _supabase_client

def get_board() -> dict:
    """Trả về JSON định dạng chuẩn để tương thích với giao diện UI hiện có."""
    for attempt in range(3):
        client = get_supabase_client()
        if client is None:
            time.sleep(2)
            continue
        
        try:
            # Truy vấn song song dữ liệu từ 2 bảng của CSDL
            missions_res = client.table("mas_missions").select("*").execute()
            tasks_res = client.table("mas_tasks").select("*").execute()
            
            m_data = missions_res.data if missions_res.data else []
            t_data = tasks_res.data if tasks_res.data else []
            
            board = {"updated_at": "", "missions": []}
            
            # Nối (Join) các Task vào đúng Mission cha của nó để Web hiểu được
            for m in m_data:
                m_dict = {
                    "id": m["id"],
                    "goal": m["goal"],
                    "report": m.get("report", ""),
                    "tasks": []
                }
                # Lọc tasks con
                for t in t_data:
                    if t.get("mission_id") == m["id"]:
                        m_dict["tasks"].append(t)
                board["missions"].append(m_dict)
                
            return board
        except Exception as e:
            print(f"[Supabase] Retry reading Database (Attempt {attempt+1}): {e}")
            time.sleep(2)
            
    return {"updated_at": "", "missions": [], "tasks": []}

def save_board(board_data: dict) -> bool:
    """Được giao diện UI sử dụng khi phân chia việc. Dùng Upsert SQL"""
    client = get_supabase_client()
    if client is None:
        return False
        
    try:
        missions = board_data.get("missions", [])
        for m in missions:
            # 1. Upsert mission
            m_payload = {"id": m["id"], "goal": m["goal"], "report": m.get("report", "")}
            client.table("mas_missions").upsert(m_payload).execute()
            
            # 2. Upsert tasks
            for t in m.get("tasks", []):
                t_payload = {
                    "id": t["id"],
                    "mission_id": m["id"],
                    "title": t.get("title", ""),
                    "description": t.get("description", ""),
                    "assigned_to": t.get("assigned_to", ""),
                    "status": t.get("status", "pending"),
                    "result": t.get("result", "")
                }
                client.table("mas_tasks").upsert(t_payload).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Error saving Database: {e}")
        return False

def update_task_atomic(task_id: str, updates: dict) -> bool:
    """HÀM SIÊU NHÂN: Cho phép Agent gọi chớp nhoáng (Update theo tên trường dữ liệu). Bảo đảm 100% không đụng độ ghi đè."""
    client = get_supabase_client()
    if client is None:
        return False
        
    try:
        from datetime import datetime
        updates["updated_at"] = datetime.now().isoformat()
        
        # Chỉ nhắm mút cập nhật duy nhất Row của task này
        client.table("mas_tasks").update(updates).eq("id", task_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Error Update Task Atomic: {e}")
        return False

def delete_mission(mission_id: str) -> bool:
    """Xóa bỏ hoàn toàn một Mission và các Task liên quan (Cascade xử lý bởi DB)."""
    client = get_supabase_client()
    if client is None: return False
    try:
        client.table("mas_missions").delete().eq("id", mission_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Error deleting Mission: {e}")
        return False

def delete_task(task_id: str) -> bool:
    """Xóa bỏ một Task đơn lẻ."""
    client = get_supabase_client()
    if client is None: return False
    try:
        client.table("mas_tasks").delete().eq("id", task_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Error deleting Task: {e}")
        return False

def reset_board() -> bool:
    """Xóa sạch sành sanh mọi dữ liệu để bắt đầu lại từ đầu."""
    client = get_supabase_client()
    if client is None: return False
    try:
        # Xóa mission sẽ tự động xóa task nhờ CASCADE
        client.table("mas_missions").delete().neq("id", "VOID").execute()
        return True
    except Exception as e:
        print(f"[Supabase] Error Reset Board: {e}")
        return False

def get_board_size_mb() -> float:
    return 0.0

def board_exists() -> bool:
    client = get_supabase_client()
    if client is None: return False
    try:
        res = client.table("mas_missions").select("id").limit(1).execute()
        return len(res.data) > 0
    except:
        return False
