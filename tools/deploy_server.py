import os
import subprocess
import sys
from pathlib import Path

# Cấu hình đích (Votranh)
REMOTE_HOST = "100.64.87.73"
REMOTE_USER = "anhng"
REMOTE_BASE = r"D:\HAN\Antigravity\MAS\CommandCenter"

# Thư mục gốc cục bộ
WORKSPACE_ROOT = Path(__file__).parent.parent

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=10"
]

def run_ssh(cmd_list):
    full_cmd = ["ssh"] + SSH_OPTS + [f"{REMOTE_USER}@{REMOTE_HOST}"] + cmd_list
    return subprocess.run(full_cmd, capture_output=True, text=True)

def deploy():
    print(f"--- DANG TRIEN KHAI CENTER SERVER TOI {REMOTE_HOST} ---")
    
    # 1. Tạo thư mục đích
    print(f"[*] Tao thu muc: {REMOTE_BASE}")
    run_ssh([f"powershell -Command New-Item -ItemType Directory -Force -Path {REMOTE_BASE}"])
    run_ssh([f"powershell -Command New-Item -ItemType Directory -Force -Path {REMOTE_BASE}\\ui"])
    run_ssh([f"powershell -Command New-Item -ItemType Directory -Force -Path {REMOTE_BASE}\\tools"])
    
    # 2. Đồng bộ tệp tin chính
    files_to_sync = ["app.py", ".env"]
    for f in files_to_sync:
        print(f"[*] Syncing: {f}")
        local_f = WORKSPACE_ROOT / f
        if local_f.exists():
            subprocess.run(["scp"] + SSH_OPTS + [str(local_f), f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_BASE}\\{f}"], check=True)

    # 3. Đồng bộ thư mục UI (Recursive)
    print("[*] Syncing UI folder...")
    local_ui = WORKSPACE_ROOT / "ui"
    # Lưu ý: Không để khoảng trắng sau dấu gạch chéo
    subprocess.run(["scp"] + SSH_OPTS + ["-r", str(local_ui), f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_BASE}/"], check=True)

    # 4. Đồng bộ thư mục tools (Recursive)
    print("[*] Syncing tools folder...")
    local_tools = WORKSPACE_ROOT / "tools"
    subprocess.run(["scp"] + SSH_OPTS + ["-r", str(local_tools), f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_BASE}/"], check=True)

    print("\n[SUCCESS] Center Server da duoc dong bo len Votranh tai:")
    print(f" Path: {REMOTE_BASE}")

if __name__ == "__main__":
    deploy()
