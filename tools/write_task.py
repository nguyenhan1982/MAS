#!/usr/bin/env python3
"""
write_task.py - Thêm task vào task_board.json

Sử dụng:
    python write_task.py --task-id task_001 --title "Tìm BĐS" --assigned-to tuyetpt --description "Chi tiết task"
    python write_task.py --task-id task_001 --status done  # Cập nhật status
    python write_task.py --list  # Liệt kê tasks
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Đảm bảo console hỗ trợ tiếng Việt
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WORKSPACE_ROOT = Path(__file__).parent.parent
# Ưu tiên thư mục hiện tại (Portable), fallback sang các máy khác
PATHS_TO_CHECK = [
    str(WORKSPACE_ROOT),        # Local (Current machine)
    r"D:\Han\Mas",               # tuyetpt
    r"D:\HAN\Antigravity\MAS",  # votranh
    r"C:\Antigravity\MAS",      # hannh
    r"C:\han\mas",              # subin
]
SHARED_DIR = WORKSPACE_ROOT # Default
for p in PATHS_TO_CHECK:
    if Path(p).exists():
        SHARED_DIR = Path(p)
        break
TASK_BOARD_PATH = SHARED_DIR / "task_board.json"


def load_task_board() -> dict:
    """Load task_board.json, tạo mới nếu chưa có."""
    if os.path.exists(TASK_BOARD_PATH):
        with open(TASK_BOARD_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": "", "tasks": []}


def save_task_board(data: dict) -> None:
    """Ghi task_board.json."""
    data["updated_at"] = datetime.now().isoformat()
    with open(TASK_BOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_task_id(task: dict) -> str:
    """Lấy ID của task, tương thích cả 'id' và 'task_id'."""
    return task.get("id") or task.get("task_id", "")


def add_task(task_id: str, title: str, assigned_to: str, description: str, created_by: str = "agent") -> dict:
    """Thêm task mới vào board."""
    board = load_task_board()

    # Kiểm tra task_id đã tồn tại chưa (tương thích cả id và task_id)
    for task in board["tasks"]:
        if get_task_id(task) == task_id:
            return {"error": f"Task {task_id} đã tồn tại"}

    new_task = {
        "id": task_id,
        "created_at": datetime.now().isoformat(),
        "created_by": created_by,
        "title": title,
        "assigned_to": assigned_to,
        "description": description,
        "status": "pending"
    }

    board["tasks"].append(new_task)
    save_task_board(board)

    return {"success": True, "task": new_task}


def update_task(task_id: str, status: str = None, result: str = None) -> dict:
    """Cập nhật status và/hoặc kết quả của task."""
    valid_statuses = ["pending", "in_progress", "done", "cancelled"]

    if status and status not in valid_statuses:
        return {"error": f"Status không hợp lệ. Chọn: {valid_statuses}"}

    board = load_task_board()

    for task in board["tasks"]:
        if get_task_id(task) == task_id:
            if status:
                task["status"] = status
            if result:
                task["result"] = result
                task["completed_at"] = datetime.now().isoformat()
            task["updated_at"] = datetime.now().isoformat()
            save_task_board(board)
            return {"success": True, "task": task}

    return {"error": f"Không tìm thấy task {task_id}"}


def update_task_status(task_id: str, status: str) -> dict:
    """Cập nhật status của task (wrapper cho backward compatibility)."""
    return update_task(task_id, status=status)


def list_tasks(assigned_to: str = None) -> dict:
    """Liệt kê tasks, có thể lọc theo agent."""
    board = load_task_board()
    tasks = board["tasks"]

    if assigned_to:
        tasks = [t for t in tasks if t["assigned_to"] == assigned_to]

    return {"tasks": tasks, "count": len(tasks)}


def get_pending_tasks(agent: str) -> list:
    """Lấy tasks pending của agent."""
    board = load_task_board()
    return [t for t in board["tasks"] if t["assigned_to"] == agent and t["status"] == "pending"]


def parse_json_input(data: dict) -> dict:
    """Parse JSON input và gọi add_task hoặc update_task.

    Dùng khi gọi qua SSH để tránh lỗi escape ký tự đặc biệt.
    """
    # Nếu có task_id và (status hoặc result) → cập nhật task
    if "task_id" in data and ("status" in data or "result" in data):
        return update_task(data["task_id"], status=data.get("status"), result=data.get("result"))
    # Nếu có đầy đủ fields → thêm task mới
    elif all(k in data for k in ["task_id", "title", "assigned_to", "description"]):
        return add_task(
            data["task_id"],
            data["title"],
            data["assigned_to"],
            data["description"],
            data.get("created_by", "agent")
        )
    else:
        return {"error": "JSON thiếu fields bắt buộc: task_id, title, assigned_to, description"}


def main():
    parser = argparse.ArgumentParser(description="Quản lý task board")
    parser.add_argument("--task-id", help="ID của task")
    parser.add_argument("--title", help="Tiêu đề task")
    parser.add_argument("--assigned-to", help="Agent được giao task")
    parser.add_argument("--description", help="Mô tả chi tiết task")
    parser.add_argument("--created-by", default="agent", help="Agent tạo task")
    parser.add_argument("--status", help="Cập nhật status (pending/in_progress/done/cancelled)")
    parser.add_argument("--result", help="Ghi kết quả khi hoàn thành task")
    parser.add_argument("--list", action="store_true", help="Liệt kê tất cả tasks")
    parser.add_argument("--filter", help="Lọc theo agent khi --list")
    parser.add_argument("--json-file", help="Đọc task từ file JSON (tránh lỗi escape qua SSH)")

    args = parser.parse_args()

    # Ưu tiên --json-file để tránh escape issues qua SSH
    if args.json_file:
        try:
            with open(args.json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            result = parse_json_input(data)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except FileNotFoundError:
            print(json.dumps({"error": f"Không tìm thấy file: {args.json_file}"}, ensure_ascii=False))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON không hợp lệ: {e}"}, ensure_ascii=False))
    elif args.list:
        res = list_tasks(args.filter)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.task_id and (args.status or args.result):
        res = update_task(args.task_id, status=args.status, result=args.result)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.task_id and args.title and args.assigned_to and args.description:
        result = add_task(args.task_id, args.title, args.assigned_to, args.description, args.created_by)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
