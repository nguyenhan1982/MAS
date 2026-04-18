"""
send_task.py
Gửi task tới agent qua SSH + OpenClaw CLI.

Cách dùng:
  python tools/send_task.py --agent votranh --message "Xin chào!"
  python tools/send_task.py --agent votranh --task-file task.txt
  python tools/send_task.py --all --message "[TASK] Báo cáo trạng thái"

Lệnh thực thi bên dưới:
  ssh <user>@<ip> node <openclaw_path> agent --agent main -m "<message>"

Yêu cầu: SSH key đã được cấu hình (không cần password)
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Fix UTF-8 output trên Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WORKSPACE_ROOT = Path(__file__).parent.parent
AGENTS_FILE = WORKSPACE_ROOT / "AGENTS_NETWORK.md"
LOG_FILE = WORKSPACE_ROOT / ".tmp" / "task_log.jsonl"

# Đường dẫn OpenClaw trên máy openclaw-hannh
OPENCLAW_PATH = os.environ.get("OPENCLAW_PATH", r"C:\oc\openclaw.mjs")


def parse_agents_network() -> dict:
    """Đọc AGENTS_NETWORK.md và trả về dict cấu hình agent."""
    if not AGENTS_FILE.exists():
        print(f"Không tìm thấy {AGENTS_FILE}")
        sys.exit(1)

    content = AGENTS_FILE.read_text(encoding="utf-8")
    agents = {}

    # Parse bảng Agent Registry (IP trực tiếp)
    table_pattern = re.compile(
        r"\|\s*(\w+)\s*\|\s*([\d\.<>a-zA-Z\s]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE
    )
    for match in table_pattern.finditer(content):
        name, ip, port = match.groups()
        name = name.strip().lower()
        ip = ip.strip()
        port = int(port.strip())
        if name not in ("tên", "---") and not ip.startswith("<"):
            agents[name] = {"ip": ip, "port": port}

    # Parse bootstrap tokens
    token_pattern = re.compile(r"^(\w+)_GATEWAY_TOKEN=(.+)$", re.MULTILINE)
    for match in token_pattern.finditer(content):
        agent_prefix, token = match.groups()
        name = agent_prefix.lower()
        token = token.strip()
        if name in agents and not token.startswith("<"):
            agents[name]["token"] = token

    # Parse WebSocket URLs (override)
    url_pattern = re.compile(r"^(\w+)_GATEWAY_URL=(ws://.+)$", re.MULTILINE)
    for match in url_pattern.finditer(content):
        agent_prefix, url = match.groups()
        name = agent_prefix.lower()
        url = url.strip()
        if name in agents and not url.startswith("<") and "<IP" not in url:
            agents[name]["gateway_url"] = url

    return agents


def get_gateway_url(config: dict) -> str:
    """Trả về WebSocket URL của gateway agent."""
    if "gateway_url" in config:
        return config["gateway_url"]
    ip = config.get("ip", "")
    port = config.get("port", 18789)
    return f"ws://{ip}:{port}"


def log_task(entry: dict):
    """Ghi log vào .tmp/task_log.jsonl."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_task(name: str, config: dict, message: str) -> dict:
    """
    Gửi task tới agent qua SSH sử dụng file-based approach.
    Tránh lỗi escape khi message chứa ký tự đặc biệt hoặc tiếng Việt.

    Workflow:
    1. Ghi message ra file tạm local
    2. SCP file sang remote
    3. PowerShell đọc file và truyền vào node
    4. Xóa file tạm
    """
    ip = config.get("ip", "")
    ssh_user = config.get("ssh_user", "anhng")
    openclaw_path = config.get("openclaw_path", r"C:\openclaw-anhng\openclaw.mjs")

    if not ip or ip.startswith("<"):
        return {
            "success": False,
            "error": "TailScale IP chưa được điền trong AGENTS_NETWORK.md",
        }

    # Tạo file tạm chứa message
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False)
    tmp.write(message)
    tmp.close()

    # Đường dẫn file tạm trên remote
    remote_tmp = f"C:\\Users\\{ssh_user}\\AppData\\Local\\Temp\\openclaw_task.txt"

    print(f"  Gửi task qua file-based approach...")
    print(f"  Message: {message[:80]}{'...' if len(message) > 80 else ''}")

    try:
        # Bước 1: SCP file sang remote
        scp = subprocess.run(
            ["scp", "-q", tmp.name, f"{ssh_user}@{ip}:{remote_tmp}"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if scp.returncode != 0:
            return {"success": False, "error": f"SCP thất bại: {scp.stderr}"}

        # Bước 2: PowerShell đọc file và truyền vào node
        ps_cmd = (
            f'powershell -Command "'
            f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
            f"$msg = (Get-Content -Path '{remote_tmp}' -Raw -Encoding UTF8).Trim(); "
            f"& node '{openclaw_path}' agent --agent main -m $msg"
            f'"'
        )

        result = subprocess.run(
            ["ssh", f"{ssh_user}@{ip}", ps_cmd],
            capture_output=True,
            timeout=120
        )

        # Decode output
        try:
            output = result.stdout.decode("utf-8").strip()
        except UnicodeDecodeError:
            output = result.stdout.decode("cp1252", errors="replace").strip()

        if result.returncode == 0:
            return {"success": True, "output": output}
        else:
            try:
                err = result.stderr.decode("utf-8")
            except UnicodeDecodeError:
                err = result.stderr.decode("cp1252", errors="replace")
            if not output:
                output = f"Exit {result.returncode}: {err[:300]}"
            return {"success": False, "error": output}

    except FileNotFoundError:
        return {"success": False, "error": "Không tìm thấy lệnh ssh/scp"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout sau 120 giây"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Xóa file tạm local
        os.unlink(tmp.name)
        # Xóa file tạm trên remote
        subprocess.run(
            ["ssh", f"{ssh_user}@{ip}", f'del "{remote_tmp}"'],
            capture_output=True,
            timeout=10
        )


def main():
    parser = argparse.ArgumentParser(
        description="Gửi task tới remote agent qua OpenClaw + TailScale"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--agent", help="Tên agent: votranh / tuyetpt / subin")
    group.add_argument("--all", action="store_true", help="Gửi tới tất cả agent đã cấu hình")

    msg_group = parser.add_mutually_exclusive_group(required=True)
    msg_group.add_argument("--message", "-m", help="Nội dung task")
    msg_group.add_argument("--task-file", help="Đọc task từ file text")

    args = parser.parse_args()

    # Đọc message
    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.exists():
            print(f"Không tìm thấy file: {args.task_file}")
            sys.exit(1)
        message = task_path.read_text(encoding="utf-8").strip()
    else:
        message = args.message

    agents = parse_agents_network()
    if not agents:
        print("Không đọc được thông tin agent từ AGENTS_NETWORK.md")
        sys.exit(1)

    # Xác định target
    if args.all:
        targets = agents
    else:
        name = args.agent.lower()
        if name not in agents:
            print(f"Không tìm thấy agent '{name}'. Các agent có: {list(agents.keys())}")
            sys.exit(1)
        targets = {name: agents[name]}

    print(f"\nGửi task tới {len(targets)} agent...")
    print(f"Message: {message[:120]}{'...' if len(message) > 120 else ''}\n")

    results = {}
    for name, config in targets.items():
        gw = get_gateway_url(config)
        print(f"  → {name} ({gw})...")
        result = send_task(name, config, message)
        results[name] = result

        # Ghi log
        log_task({
            "timestamp": datetime.now().isoformat(),
            "agent": name,
            "gateway_url": gw,
            "message": message,
            "success": result["success"],
            "error": result.get("error"),
            "output": result.get("output", "")[:500],
        })

        if result["success"]:
            print(f"  ✓ OK")
            if result.get("output"):
                print(f"  Phản hồi: {result['output'][:300]}")
        else:
            print(f"  ✗ LỖI: {result['error']}")
        print()

    success_count = sum(1 for r in results.values() if r["success"])
    print(f"{'='*55}")
    print(f"Kết quả: {success_count}/{len(targets)} thành công")
    print(f"Log: {LOG_FILE}\n")

    sys.exit(0 if success_count == len(targets) else 1)


if __name__ == "__main__":
    main()
