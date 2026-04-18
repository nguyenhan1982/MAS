import os
import sys
import json
import time
import random
import socket
from pathlib import Path
import requests

# BẢN VÁ MẠNG THÉP: Ép hệ thống dùng IPv4 để tránh treo DNS getaddrinfo trên Windows
orig_getaddrinfo = socket.getaddrinfo
def dashed_getaddrinfo(*args, **kwargs):
    res = orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET]
socket.getaddrinfo = dashed_getaddrinfo

# Thêm tools vào path để import delegate và llm_client
tools_dir = str(Path(__file__).parent)
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)
import delegate
import storage

# ƯU TIÊN DANH TÍNH TỪ BIẾN MÔI TRƯỜNG
MY_NAME = os.environ.get("AGENT_NAME", "").strip()
if not MY_NAME or MY_NAME == "unknown":
    MY_NAME = delegate.WHO_AM_I.strip()

# Fix UTF-8 cho Windows (Quietly)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

# Thư mục log riêng cho từng Agent
LOG_DIR = Path(__file__).parent.parent / "scratch"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"agent_{MY_NAME}_log.txt"

def log(msg):
    """Hàm ghi nhật ký tối giản, không gây đệ quy."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [{MY_NAME}] {msg}"
    # In trực tiếp ra màn hình
    try:
        print(full_msg, flush=True)
    except: pass
    # Ghi vào tệp tin
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except: pass

def call_ai(cfg, prompt):
    try:
        from llm_client import call_llm_with_fallback
        return call_llm_with_fallback(
            prompt,
            system_instruction=f"Bạn là Agent {MY_NAME}. Hãy trả lời chuyên nghiệp."
        )
    except Exception as e:
        return f"[ERROR] Lỗi gọi AI: {e}"

def fetch_tasks_supabase(agent_name):
    """Truy vấn thẳng bảng mas_tasks - chỉ lấy đúng task của Agent mình, không kéo toàn bộ JSON."""
    try:
        client = storage.get_supabase_client()
        if client is None:
            return {"tasks": []}

        # Chỉ lấy các task của agent này đang pending
        res = client.table("mas_tasks") \
            .select("*") \
            .eq("assigned_to", agent_name) \
            .in_("status", ["pending", "in_progress"]) \
            .execute()

        tasks = res.data if res.data else []
        log(f"[DB] Agent: {agent_name} | Tasks pending: {len(tasks)}")
        return {"tasks": tasks}
    except Exception as e:
        log(f"Loi doc Supabase (Normalized): {e}")
        return {"tasks": []}

def update_task_status_supabase(mission_id, task_id, status, result=None):
    try:
        # Tương tác Database chuẩn hóa: Ghi thẳng vào Row của Task mà không cần kéo cả cục JSON xuống
        updates = {"status": status}
        if result:
            updates["result"] = result
            
        success = storage.update_task_atomic(task_id, updates)
        return success
    except Exception as e:
        log(f"Lỗi cập nhật Supabase (Atomic): {e}")
        return False

def main_loop():
    log(f"--- AGENT {MY_NAME} KHOI DONG (Cloud Mode) ---")
    
    # KHỞI ĐỘNG SO LE (STAGGERING): Tránh việc 4 Agent cùng ập vào Ollama một lúc
    try:
        agent_id = "".join(filter(str.isdigit, MY_NAME))
        rank = int(agent_id) if agent_id else 0
        wait_time = rank * 2 # Agent 1 đợi 2s, Agent 2 đợi 4s...
        if wait_time > 0:
            log(f"Staggering: Doi {wait_time}s de tranh xung dot khoi dong...")
            time.sleep(wait_time)
    except: pass

    # Check AI status (Non-fatal & Non-blocking)
    log("Dang thu ket noi AI (Ollama)...")
    for attempt in range(3):
        try:
            # Neu AI treo, van tiep tuc vao vong lap sau 10s
            test_res = call_ai({}, "OK?") 
            log(f"Trạng thái AI: {test_res[:30]}...")
            break
        except Exception as e:
            log(f"AI chưa sẵn sàng (Lần {attempt+1}): {e}")
            time.sleep(3)

    while True:
        try:
            log(f"--- {MY_NAME} dang kiem tra nhiem vu moi... ---")
            data = fetch_tasks_supabase(MY_NAME)
            tasks = data.get("tasks", [])
            
            if not tasks:
                # JITTERING: Nghỉ ngẫu nhiên 10-15s để không bị trùng nhịp với Agent khác
                sleep_time = 10 + random.uniform(0, 5)
                time.sleep(sleep_time)
                continue
                
            for task in tasks:
                log(f"==> NHAN NHIEM VU: {task['title']}")
                update_task_status_supabase(task["mission_id"], task["id"], "in_progress")
                
                log(f"Dang xu ly: {task['description'][:50]}...")
                prompt = f"Nhiệm vụ: {task['title']}\nMô tả: {task['description']}"
                response = call_ai({}, prompt)
                
                log(f"✓ Hoan thanh: {task['id']}")
                update_task_status_supabase(task["mission_id"], task["id"], "done", response)
                
        except Exception as e:
            log(f"Lỗi vòng lặp chính: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
