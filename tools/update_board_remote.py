import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

def update_task(task_id, mission_id=None, status=None, result=None):
    # Đảm bảo đường dẫn tuyệt đối lấy từ thư mục chứa công cụ
    WORKSPACE_ROOT = Path(__file__).parent.parent
    board_path = WORKSPACE_ROOT / "task_board.json"
    
    if not board_path.exists():
        print(f"Error: {board_path} not found.")
        return False

    # Cơ chế Lock an toàn hơn với Timeout
    lock_path = board_path.with_suffix(".lock")
    start_time = datetime.now().timestamp()
    timeout = 10 # Giây
    
    lock_acquired = False
    while (datetime.now().timestamp() - start_time) < timeout:
        try:
            # Tạo file lock kiểu nguyên tử (atomic)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            lock_acquired = True
            break
        except FileExistsError:
            import time
            time.sleep(0.5)
            continue
    
    if not lock_acquired:
        print(f"Error: Timeout waiting for lock on {board_path}")
        return False
    
    try:
        
        with open(board_path, "r", encoding="utf-8") as f:
            board = json.load(f)

        updated = False
        for mission in board.get("missions", []):
            # Nếu có mission_id, chỉ kiểm tra trong mission đó
            if mission_id and mission.get("id") != mission_id:
                continue
                
            for task in mission.get("tasks", []):
                if task["id"] == task_id:
                    if status:
                        task["status"] = status
                    if result:
                        task["result"] = result
                    
                    if status == "done":
                        task["completed_at"] = datetime.now().isoformat()
                    
                    task["updated_at"] = datetime.now().isoformat()
                    updated = True
                    break
            if updated: break

        if updated:
            with open(board_path, "w", encoding="utf-8") as f:
                json.dump(board, f, ensure_ascii=False, indent=2)
            msg = f"Successfully updated task {task_id}"
            if mission_id: msg += f" in mission {mission_id}"
            print(msg)
        else:
            print(f"Task {task_id} not found" + (f" in mission {mission_id}" if mission_id else "") + ".")

    finally:
        if lock_path.exists():
            lock_path.unlink()
    
    return updated

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--mission", help="Mission ID to narrow down the search")
    parser.add_argument("--status")
    parser.add_argument("--result")
    parser.add_argument("--file")
    args = parser.parse_args()
    
    result_content = args.result
    if args.file and os.path.exists(args.file):
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                result_content = f.read()
        except Exception as e:
            print(f"Error reading file {args.file}: {e}")
    
    update_task(args.id, args.mission, args.status, result_content)
