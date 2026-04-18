import sys
import json
import requests
import re
import subprocess
import time
import os
from pathlib import Path
from datetime import datetime

# Import storage engine
sys.path.append(str(Path(__file__).parent))
import storage

# Thiết lập vai trò Server để llm_client.py biết và bỏ qua Ollama
os.environ["MAS_ROLE"] = "server"

# Fix UTF-8 output cho Windows 
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Cấu hình đường dẫn
WORKSPACE_ROOT = Path(__file__).parent.parent

PROMPT_TEMPLATE = """
Bạn là một AI chuyên gia điều phối hệ thống Multi-Agent. 
Nhiệm vụ của bạn là phân rã một "Nhiệm vụ chiến lược" thành các "Nhiệm vụ cụ thể" cho các Agent đang ONLINE.

Danh sách các Agent đang ONLINE hiện tại:
{agents_list}

SỐ LƯỢNG NHIỆM VỤ TỐI ĐA (LIMIT): {tasks_limit}
(Quan trọng: Bạn CHỈ ĐƯỢC PHÉP tạo ra tối đa {tasks_limit} nhiệm vụ cụ thể, tương ứng với số lượng Agent đang online).

Hãy phân rã nhiệm vụ sau đây:
"{goal}"

Yêu cầu định dạng đầu ra phải là một JSON array duy nhất, mỗi phần tử có cấu trúc:
{{
  "id": "Mã định danh duy nhất (VD: SEC_001)",
  "title": "Tiêu đề ngắn gọn",
  "assigned_to": "Tên một trong các agent online ở trên",
  "description": "Mô tả chi tiết công việc phải làm",
  "priority": "High/Normal/Low",
  "status": "pending"
}}

CHỈ TRẢ VỀ JSON ARRAY, KHÔNG CÓ GIẢI THÍCH GÌ THÊM.
"""

def get_online_agents():
    """Lấy danh sách agent online. Trên Cloud, ta sẽ mặc định lấy từ config vì không check được SSH."""
    sys.path.append(str(WORKSPACE_ROOT / "tools"))
    from delegate import AGENTS
    
    # Nếu đang chạy trên Cloud (Supabase mode), ta không thể ping SSH tới máy local
    # Ở chế độ Supabase chuẩn hóa, ta giả định các Agent trong cấu hình đang sẵn sàng
    return list(AGENTS.keys())
    
    # Nếu chạy local, vẫn dùng ping SSH như cũ
    print("--- Đang kiểm tra trạng thái các Agent (Local SSH) ---")
    try:
        from delegate import ping_agent
        online_agents = []
        for name in AGENTS:
            if ping_agent(name):
                online_agents.append(name)
        return online_agents if online_agents else ["hannh"]
    except Exception as e:
        print(f"Lỗi kiểm tra trạng thái: {e}")
        return ["hannh"]

def decompose_task(goal, online_agents):
    tasks_limit = len(online_agents)
    print(f"--- Đang phân rã nhiệm vụ cho {tasks_limit} Agent: {', '.join(online_agents)} ---")
    
    prompt = PROMPT_TEMPLATE.format(
        goal=goal, 
        agents_list=", ".join(online_agents),
        tasks_limit=tasks_limit
    )
    
    try:
        # Sử dụng llm_client với cơ chế fallback
        from llm_client import call_llm_with_fallback
        
        content = call_llm_with_fallback(prompt, system_instruction="Bạn là một AI phân rã nhiệm vụ chuyên nghiệp. Chỉ trả về JSON array.")
        
        if "[ERROR]" in content:
            print(content)
            return None

        match = re.search(r'\[\s*.*?\s*\]', content, re.DOTALL)
        if not match:
            print("Lỗi: Không tìm thấy định dạng JSON trong phản hồi của AI.")
            return None
            
        json_str = match.group()
        tasks = json.loads(json_str)
        return tasks
    except Exception as e:
        print(f"Lỗi khi thực hiện phân rã: {e}")
        return None

def trigger_agents_if_local(tasks):
    """Kích hoạt Agent. Chỉ hoạt động nếu đang chạy ở môi trường Local có quyền SSH."""
    # Agent máy local sẽ tự động 'Pull' nhiệm vụ từ Cloud
    return

    assigned_agents = list(set(t["assigned_to"] for t in tasks))
    from delegate import trigger_agent
    
    for agent_name in assigned_agents:
        print(f"→ Gửi tín hiệu kích hoạt tới Agent: {agent_name} (via SSH)")
        msg = trigger_agent(agent_name)
        print(f"  Kết quả: {msg}")

def update_task_board(goal, new_tasks):
    if not new_tasks:
        return False
        
    print("[*] Đang tải board dữ liệu...")
    board = storage.get_board()
            
    if "missions" not in board: board["missions"] = []
    
    # Tạo Mission mới
    mission_id = f"M_{datetime.now().strftime('%m%d_%H%M')}"
    new_mission = {
        "id": mission_id,
        "goal": goal,
        "status": "in_progress",
        "created_at": datetime.now().isoformat(),
        "tasks": [],
        "report": ""
    }
    
    for t in new_tasks:
        t["created_at"] = datetime.now().isoformat()
        new_mission["tasks"].append(t)
        
    board["missions"].insert(0, new_mission)
    board["updated_at"] = datetime.now().isoformat()
    
    print("[*] Saving new mission to Supabase...")
    if storage.save_board(board):
        print("✓ Mission saved successfully.")
        return True
    else:
        print("[!] Failed to save mission.")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python decompose_task.py \"Nhiệm vụ chiến lược\"")
        sys.exit(1)
        
    strategic_goal = sys.argv[1]
    raw_online_list = get_online_agents()
    
    # BỘ LỌC CHUYÊN BIỆT: Chỉ sử dụng 4 Agent ảo trên máy votranh
    VOTRANH_VIRTUAL_AGENTS = ["votranh_1", "votranh_2", "votranh_3", "votranh_4"]
    online_list = [a for a in raw_online_list if a in VOTRANH_VIRTUAL_AGENTS]
    
    if not online_list:
        print("\n[!] CANH BAO: Khong co Agent ảo (votranh_1..4) nao dang online.")
        print("Vui long chay launch_votranh_hidden.ps1 tren may votranh truoc.")
        print("\n--- [FAILED] ---")
        sys.exit(0)
    
    print(f"[*] He thong dang su dung {len(online_list)} Agent chuyen biet: {', '.join(online_list)}")
        
    tasks = decompose_task(strategic_goal, online_list)
    if tasks:
        if update_task_board(strategic_goal, tasks):
            print("\n--- [SUCCESS] ---")
        else:
            print("\n--- [FAILED] ---")
    else:
        print("\n[!] Lỗi: Không thể phân rã nhiệm vụ hoặc định dạng phản hồi không hợp lệ.")
        print("--- [FAILED] ---")
