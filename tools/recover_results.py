import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Fix UTF-8 cho Windows console
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

WORKSPACE_ROOT = Path(__file__).parent.parent
BOARD_PATH = WORKSPACE_ROOT / "task_board.json"
SCRATCH_DIR = WORKSPACE_ROOT / "scratch"

def merge_result(board, result_data):
    mission_id = result_data.get("mission_id")
    task_id = result_data.get("task_id")
    result_text = result_data.get("result")
    
    if not mission_id or not task_id:
        return False
        
    found = False
    for m in board.get("missions", []):
        if m["id"] == mission_id:
            for t in m.get("tasks", []):
                if t["id"] == task_id:
                    t["status"] = "done"
                    t["result"] = result_text
                    t["completed_at"] = datetime.now().isoformat()
                    found = True
                    break
    return found

def main():
    if not BOARD_PATH.exists():
        print("Không tìm thấy task_board.json")
        return

    try:
        with open(BOARD_PATH, "r", encoding="utf-8") as f:
            board = json.load(f)
    except Exception as e:
        print(f"Lỗi đọc board: {e}")
        return

    temp_files = list(SCRATCH_DIR.glob("temp_result_*.json"))
    if not temp_files:
        print("Không tìm thấy file kết quả tạm nào.")
        return

    count = 0
    for tf in temp_files:
        if tf.stat().st_size == 0:
            print(f"Bỏ qua file trống: {tf.name}")
            continue
            
        try:
            with open(tf, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    continue
                data = json.loads(content)
            
            if merge_result(board, data):
                print(f"[✓] Đã gộp kết quả từ {tf.name}")
                count += 1
                # Ghi chú: Không xóa file để user kiểm tra lại nếu cần
        except Exception as e:
            print(f"[!] Lỗi khi xử lý {tf.name}: {str(e)}")

    if count > 0:
        board["updated_at"] = datetime.now().isoformat()
        with open(BOARD_PATH, "w", encoding="utf-8") as f:
            json.dump(board, f, ensure_ascii=False, indent=2)
        print(f"\n--- Hoàn tất. Đã gộp {count} kết quả vào task_board.json ---")
    else:
        print("Không có kết quả nào mới được gộp.")

if __name__ == "__main__":
    main()
