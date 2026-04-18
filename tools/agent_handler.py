import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Fix UTF-8 output cho Windows (Tránh lỗi closed file)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Đường dẫn local trên máy agent
BOARD_PATH = Path(r"C:\Antigravity\MAS\task_board.json")
# Trên máy votranh thì board ở D:\...
if not BOARD_PATH.exists():
    BOARD_PATH = Path(r"D:\HAN\Antigravity\MAS\task_board.json")

def process_my_tasks(agent_name):
    print(f"--- Agent {agent_name} đang kiểm tra Task Board ---")
    
    if not BOARD_PATH.exists():
        print(f"Lỗi: Không tìm thấy Task Board tại {BOARD_PATH}")
        return
        
    try:
        with open(BOARD_PATH, "r", encoding="utf-8") as f:
            board = json.load(f)
    except Exception as e:
        print(f"Lỗi đọc board: {e}")
        return
        
    my_tasks = [t for t in board["tasks"] if t["assigned_to"] == agent_name and t["status"] == "pending"]
    
    if not my_tasks:
        print("Không có nhiệm vụ mới.")
        return
        
    for task in my_tasks:
        print(f"Đang thực hiện: [{task['id']}] {task['title']}")
        
        # Đánh dấu in_progress
        task["status"] = "in_progress"
        save_board(board)
        
        # Giả lập thực hiện công việc (Trong thực tế sẽ gọi SOP/Script tương ứng)
        # result = execute_sop(task)
        result = f"Đã hoàn thành: {task['title']}"
        
        # Đánh dấu done
        task["status"] = "done"
        task["result"] = result
        task["completed_at"] = datetime.now().isoformat()
        save_board(board)
        print(f"✓ Hoàn thành nhiệm vụ {task['id']}")

def save_board(board):
    board["updated_at"] = datetime.now().isoformat()
    with open(BOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python agent_handler.py <agent_name>")
        sys.exit(1)
        
    agent_name = sys.argv[1]
    process_my_tasks(agent_name)
