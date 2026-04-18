#!/usr/bin/env python3
"""
write_task_remote.py - Ghi task vào task_board trên máy Host qua SSH

Sử dụng file-based approach để tránh lỗi escape ký tự đặc biệt.

Cách dùng:
    python write_task_remote.py --task-id SEC_002 --title "Quét logs" --assigned-to votranh --description "Mô tả task"
    python write_task_remote.py --task-id SEC_002 --status done

Script này sẽ:
1. Tạo file JSON tạm chứa task data
2. SCP file JSON sang máy Host (votranh)
3. SSH chạy write_task.py --json-file trên Host
4. Xóa file tạm
"""

import argparse
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Fix UTF-8 output trên Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Cấu hình máy Host (nơi chứa task_board.json master)
HOST_CONFIG = {
    "ssh_host": "100.64.87.73", # votranh
    "ssh_user": "anhng",
    "tools_dir": r"D:\HAN\Antigravity\MAS\tools",
    "shared_dir": r"D:\HAN\Antigravity\MAS",
    "temp_dir": r"AppData\Local\Temp", # Tương đối với User Home trên Windows
}


def get_local_ips() -> set:
    """Lấy tất cả IP của máy hiện tại."""
    ips = set()
    try:
        hostname = socket.gethostname()
        ips.add(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if not ip.startswith('::'):
                ips.add(ip)
    except Exception:
        pass
    ips.add('127.0.0.1')
    ips.add('localhost')
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips


def is_host_machine() -> bool:
    """Kiểm tra xem đang chạy trên máy Host hay không."""
    local_ips = get_local_ips()
    return HOST_CONFIG["ssh_host"] in local_ips


def write_task_local(task_data: dict) -> dict:
    """Ghi task trực tiếp khi đang chạy trên máy Host."""
    # Import write_task.py functions
    tools_dir = Path(__file__).parent
    task_board_path = Path(r"C:\Users\anhng\.openclaw\workspace") / "task_board.json"

    # Tạo file JSON tạm
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
    json.dump(task_data, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    try:
        # Gọi write_task.py trực tiếp
        write_task_path = tools_dir / "write_task.py"
        result = subprocess.run(
            ["python", str(write_task_path), "--json-file", tmp.name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr or result.stdout}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        os.unlink(tmp.name)


def write_task_to_host(task_data: dict) -> dict:
    """Ghi task lên Host qua SSH sử dụng file-based approach."""

    # Nếu đang chạy trên Host → gọi trực tiếp
    if is_host_machine():
        return write_task_local(task_data)

    host = HOST_CONFIG["ssh_host"]
    user = HOST_CONFIG["ssh_user"]
    tools_dir = HOST_CONFIG["tools_dir"]
    temp_dir = HOST_CONFIG["temp_dir"]

    # Tạo file JSON tạm local
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
    json.dump(task_data, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    # Đường dẫn file tạm trên remote
    remote_json = f"{temp_dir}\\task_input.json"

    try:
        # Bước 1: SCP file JSON sang Host
        scp_result = subprocess.run(
            ["scp", "-q", tmp.name, f"{user}@{host}:{remote_json}"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if scp_result.returncode != 0:
            return {"success": False, "error": f"SCP thất bại: {scp_result.stderr}"}

        # Bước 2: SSH chạy write_task.py --json-file trên Host
        # Lưu ý: TEMP file trên remote thường ở thư mục Temp của User
        remote_json_full = f"C:\\Users\\{user}\\{temp_dir}\\task_input.json"
        write_task_path = f"{tools_dir}\\write_task.py"
        ssh_cmd = f'python "{write_task_path}" --json-file "{remote_json_full}"'

        result = subprocess.run(
            ["ssh", f"{user}@{host}", ssh_cmd],
            capture_output=True,
            timeout=30
        )

        # Decode output
        try:
            output = result.stdout.decode("utf-8").strip()
        except UnicodeDecodeError:
            output = result.stdout.decode("cp1252", errors="replace").strip()

        if result.returncode == 0 and output:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"success": True, "output": output}
        else:
            try:
                err = result.stderr.decode("utf-8")
            except UnicodeDecodeError:
                err = result.stderr.decode("cp1252", errors="replace")
            return {"success": False, "error": f"Exit {result.returncode}: {err or output}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout sau 30 giây"}
    except FileNotFoundError:
        return {"success": False, "error": "Không tìm thấy lệnh ssh/scp"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Xóa file tạm local
        os.unlink(tmp.name)
        # Xóa file tạm trên remote
        subprocess.run(
            ["ssh", f"{user}@{host}", f'del "{remote_json}"'],
            capture_output=True,
            timeout=10
        )


def main():
    parser = argparse.ArgumentParser(
        description="Ghi task vào task_board trên máy Host qua SSH (file-based)"
    )
    parser.add_argument("--task-id", required=True, help="ID của task")
    parser.add_argument("--title", help="Tiêu đề task (bắt buộc khi thêm mới)")
    parser.add_argument("--assigned-to", help="Agent được giao task (bắt buộc khi thêm mới)")
    parser.add_argument("--description", help="Mô tả chi tiết task (bắt buộc khi thêm mới)")
    parser.add_argument("--created-by", default="agent", help="Agent tạo task")
    parser.add_argument("--status", help="Cập nhật status (pending/in_progress/done/cancelled)")
    parser.add_argument("--result", help="Ghi kết quả khi hoàn thành task")

    args = parser.parse_args()

    # Xây dựng task data
    if args.status or args.result:
        # Cập nhật status hoặc result
        task_data = {
            "task_id": args.task_id,
            "status": args.status,
            "result": args.result
        }
    elif args.title and args.assigned_to and args.description:
        # Thêm task mới
        task_data = {
            "task_id": args.task_id,
            "title": args.title,
            "assigned_to": args.assigned_to,
            "description": args.description,
            "created_by": args.created_by
        }
    else:
        print("Lỗi: Để thêm task mới cần: --title, --assigned-to, --description")
        print("     Để cập nhật status cần: --task-id, --status")
        parser.print_help()
        sys.exit(1)

    if is_host_machine():
        print(f"→ Ghi task {args.task_id} trực tiếp (đang chạy trên Host)...")
    else:
        print(f"→ Ghi task {args.task_id} lên Host ({HOST_CONFIG['ssh_host']}) qua SSH...")
    result = write_task_to_host(task_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
