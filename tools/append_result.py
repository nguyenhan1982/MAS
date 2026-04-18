#!/usr/bin/env python3
"""
append_result.py - Ghi kết quả task vào results_<agent>.jsonl

Sử dụng:
    python append_result.py --agent tuyetpt --task-id task_001 --summary "Tìm được 3 căn" --data '{"items": [...]}'
    python append_result.py --agent tuyetpt --read  # Đọc kết quả của agent
    python append_result.py --read-all  # Đọc tất cả kết quả
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Đảm bảo console hỗ trợ tiếng Việt
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

VALID_AGENTS = ["hannh", "tuyetpt", "subin", "votranh"]


def get_result_file(agent: str) -> str:
    """Lấy đường dẫn file kết quả của agent."""
    return os.path.join(SHARED_DIR, f"results_{agent}.jsonl")


def append_result(agent: str, task_id: str, summary: str, data: dict = None, status: str = "done") -> dict:
    """Ghi 1 dòng kết quả vào file results_<agent>.jsonl."""
    if agent not in VALID_AGENTS:
        return {"error": f"Agent không hợp lệ. Chọn: {VALID_AGENTS}"}

    result_entry = {
        "ts": datetime.now().isoformat(),
        "task_id": task_id,
        "agent": agent,
        "summary": summary,
        "data": data or {},
        "status": status
    }

    result_file = get_result_file(agent)

    with open(result_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_entry, ensure_ascii=False) + "\n")

    return {"success": True, "entry": result_entry}


def read_results(agent: str) -> list:
    """Đọc tất cả kết quả của agent."""
    result_file = get_result_file(agent)
    results = []

    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    return results


def read_all_results() -> dict:
    """Đọc kết quả từ tất cả agents."""
    all_results = {}
    for agent in VALID_AGENTS:
        all_results[agent] = read_results(agent)
    return all_results


def get_results_by_task(task_id: str) -> list:
    """Lấy tất cả kết quả liên quan đến task_id."""
    results = []
    for agent in VALID_AGENTS:
        for entry in read_results(agent):
            if entry.get("task_id") == task_id:
                results.append(entry)
    return results


def main():
    parser = argparse.ArgumentParser(description="Ghi kết quả task")
    parser.add_argument("--agent", help="Tên agent (hannh/tuyetpt/subin/votranh)")
    parser.add_argument("--task-id", help="ID của task")
    parser.add_argument("--summary", help="Tóm tắt kết quả")
    parser.add_argument("--data", help="Dữ liệu JSON (optional)")
    parser.add_argument("--status", default="done", help="Trạng thái (done/error/partial)")
    parser.add_argument("--read", action="store_true", help="Đọc kết quả của agent")
    parser.add_argument("--read-all", action="store_true", help="Đọc tất cả kết quả")
    parser.add_argument("--by-task", help="Lọc kết quả theo task_id")

    args = parser.parse_args()

    if args.read_all:
        result = read_all_results()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.by_task:
        result = get_results_by_task(args.by_task)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.read and args.agent:
        result = read_results(args.agent)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.agent and args.task_id and args.summary:
        data = json.loads(args.data) if args.data else None
        result = append_result(args.agent, args.task_id, args.summary, data, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
