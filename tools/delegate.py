"""
delegate.py
Công cụ điều phối P2P - Đã loại bỏ hoàn toàn OpenClaw.
Dùng để kiểm tra trạng thái, xem task board và kích hoạt agent qua SSH.
"""

import io
import json
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import os

# Đường dẫn SSH Key tường minh - Quan trọng khi chạy từ tiến trình nền (Flask)
SSH_KEY_PATH = os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Admin'), '.ssh', 'id_ed25519')
SSH_COMMON_OPTS = [
    "-o", "ConnectTimeout=10",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "IdentitiesOnly=yes",
    "-i", SSH_KEY_PATH,
]

# Fix UTF-8 output cho Windows - TAM THOI TAT DE DEBUG
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
# sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def get_local_ips() -> set:
    ips = set()
    try:
        hostname = socket.gethostname()
        ips.add(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if not ip.startswith('::'): ips.add(ip)
    except: pass
    ips.add('127.0.0.1')
    ips.add('localhost')
    return ips

# Đăng ký AGENT
AGENTS = {
    "hannh": {
        "ssh_host": "100.127.128.6",
        "ssh_user": "Admin",
    },
    "votranh": {
        "ssh_host": "100.64.87.73",
        "ssh_user": "anhng",
    },
    "tuyetpt": {
        "ssh_host": "100.114.29.24",
        "ssh_user": "admin",
    },
    "subin": {
        "ssh_host": "100.114.133.6",
        "ssh_user": "nguye",
    },
    # AGENT ẢO (Chạy trên máy votranh)
    "votranh_1": { "ssh_host": "100.64.87.73", "ssh_user": "anhng", "remote_path": "D:\\HAN\\Antigravity\\MAS\\Agent_Votranh" },
    "votranh_2": { "ssh_host": "100.64.87.73", "ssh_user": "anhng", "remote_path": "D:\\HAN\\Antigravity\\MAS\\Agent_Votranh" },
    "votranh_3": { "ssh_host": "100.64.87.73", "ssh_user": "anhng", "remote_path": "D:\\HAN\\Antigravity\\MAS\\Agent_Votranh" },
    "votranh_4": { "ssh_host": "100.64.87.73", "ssh_user": "anhng", "remote_path": "D:\\HAN\\Antigravity\\MAS\\Agent_Votranh" },
}

def get_my_identity() -> str:
    """Xác định danh tính của máy hiện tại dựa trên biến môi trường hoặc IP."""
    # Ưu tiên 1: Nhận diện từ biến môi trường (Nhanh và chính xác nhất cho Agent ảo)
    env_name = os.environ.get("AGENT_NAME")
    if env_name:
        return env_name

    # Ưu tiên 2: Nhận diện từ IP (Dùng cho CenterServer hoặc Agent truyền thống)
    local_ips = get_local_ips()
    for name, info in AGENTS.items():
        if info["ssh_host"] in local_ips:
            return name
    return "unknown"

WHO_AM_I = get_my_identity()

# Cấu hình Shared Board
HOST_MACHINE = {
    "ssh_host": "100.64.87.73",
    "ssh_user": "anhng",
    "shared_dir": r"D:\HAN\Antigravity\MAS",
}

# Cấu hình Hub API (Sẵn sàng cho Cloud)
HUB_API_URL = os.environ.get("HUB_API_URL", "http://100.114.29.24:5000")

# Đăng ký Đường dẫn Script cố định cho từng Agent
PATHS_MAP = {
    "hannh": r"C:\Antigravity\MAS\Agent_Hannh",
    "votranh": r"D:\HAN\Antigravity\MAS\Agent_Votranh",
    "subin": r"C:\han\mas\Agent_Subin",
    "tuyetpt": r"D:\Han\Mas\Agent_Tuyetpt"
}

# Tự động nhận diện thư mục làm việc hiện tại
def get_shared_dir() -> Path:
    # Ưu tiên thư mục cha của tools (CenterServer root)
    current_script_parent = Path(__file__).parent.parent
    if (current_script_parent / "task_board.json").exists():
        return current_script_parent
        
    # Fallback 1. Thử nhận diện bằng Identity
    if WHO_AM_I in PATHS_MAP:
        p = Path(PATHS_MAP[WHO_AM_I])
        if p.exists(): return p
    
    # Fallback 2. Thử duyệt các đường dẫn phổ biến
    for p_str in PATHS_MAP.values():
        p = Path(p_str)
        if p.exists(): return p
        
    return current_script_parent # Default là thư mục hiện tại

SHARED_DIR = get_shared_dir()
TASK_BOARD_PATH = SHARED_DIR / "task_board.json"

def ping_agent(agent_name: str) -> bool:
    """Kiểm tra Agent online bằng ICMP Ping (nhanh, đơn giản, không phụ thuộc SSH auth)."""
    agent = AGENTS.get(agent_name.lower())
    if not agent: return False
    
    host = agent["ssh_host"]
    try:
        # ICMP Ping: 1 gói, timeout 3 giây - đủ nhanh và tin cậy
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "3000", host],
            capture_output=True, timeout=5, stdin=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[DEBUG] Ping {agent_name} ({host}) exception: {str(e)}")
        return False

def trigger_agent(agent_name: str) -> str:
    """Kích hoạt agent_core.py - tự động nhận dạng local vs remote."""
    agent = AGENTS.get(agent_name.lower())
    if not agent: return f"[ERROR] Agent không tồn tại: {agent_name}"
    
    host = agent["ssh_host"]
    user = agent["ssh_user"]
    
    # Đường dẫn script: Ưu tiên remote_path trong AGENTS, sau đó mới tới PATHS_MAP
    base_dir = agent.get("remote_path") or PATHS_MAP.get(agent_name.lower())
    
    if not base_dir:
        return f"[ERROR] Không tìm thấy đường dẫn cho agent: {agent_name}"
        
    remote_path = os.path.join(base_dir, "tools", "agent_core.py")
    
    # Kiểm tra xem agent có đang chạy trên máy hiện tại không
    is_local = (agent_name.lower() == WHO_AM_I.lower())
    
    try:
        if is_local:
            # Chạy trực tiếp trên máy local (không cần SSH vào chính mình)
            # Redirect stdout/stderr vào log file để tránh lỗi [Errno 22] khi pipe bị đứt
            log_dir = Path(remote_path).parent.parent / "scratch"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"agent_{agent_name}_log.txt"
            with open(log_file, "a", encoding="utf-8") as lf:
                subprocess.Popen(
                    ["python", remote_path],
                    stdout=lf, stderr=lf,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
                )
            return f"[SUCCESS] Đã kích hoạt {agent_name} trực tiếp (Local, log: {log_file.name})"
        else:
            # Chạy nền qua SSH với các flag resilient + explicit key
            cmd = ["ssh"] + SSH_COMMON_OPTS + [
                f"{user}@{host}", "python", remote_path
            ]
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"[SUCCESS] Đã gửi tín hiệu kích hoạt tới {agent_name} qua SSH"
    except Exception as e:
        return f"[ERROR] Không thể kích hoạt agent: {e}"





def read_task_board() -> dict:
    """Đọc task_board.json (Local backup trên Hannh)."""
    if TASK_BOARD_PATH.exists():
        with open(TASK_BOARD_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": "", "tasks": []}

def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python delegate.py <check|board|ping|my-tasks>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        print("Kiểm tra trạng thái Agents (P2P SSH):")
        for name in AGENTS:
            status = "ONLINE  ✓" if ping_agent(name) else "OFFLINE ✗"
            print(f"  {name:<12} {status}")
            
    elif cmd == "board":
        board = read_task_board()
        print(f"Task Board (Bản backup tại {WHO_AM_I} - {board.get('updated_at')})")
        print("-" * 65)
        missions = board.get("missions", [])
        if not missions:
            # Fallback cho tasks cũ nếu có
            missions = [{"goal": "Legacy Tasks", "tasks": board.get("tasks", [])}]
            
        for m in missions:
            print(f"\nMission: {m.get('goal', 'Unknown')[:60]}...")
            for task in m.get("tasks", []):
                icon = {"pending": "⏳", "in_progress": "🔄", "done": "✅"}.get(task["status"], "?")
                print(f"  {icon} [{task['id']}] {task['title']} -> {task['assigned_to']}")
            
    elif cmd == "ping" and len(sys.argv) >= 3:
        target = sys.argv[2]
        print(f"→ Đang kích hoạt Agent {target}...")
        print(trigger_agent(target))

if __name__ == "__main__":
    main()
