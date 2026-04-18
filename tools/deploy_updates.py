#!/usr/bin/env python3
"""
deploy_updates.py - Đồng bộ mã nguồn và cấu hình sang cho các Agent (Hỗ trợ đa thư mục cho Votranh).
"""

import subprocess
import os
import sys
from pathlib import Path

# Đảm bảo import được delegate.py
current_dir = Path(__file__).parent
WORKSPACE_ROOT = current_dir.parent
sys.path.append(str(WORKSPACE_ROOT / "CenterServer" / "tools"))

try:
    from delegate import AGENTS, ping_agent
except ImportError:
    print("[!] Không tìm thấy delegate.py.")
    sys.exit(1)

FILES_TO_SYNC = [
    "llm_client.py",
    "search_tool.py",
    "agent_core.py",
    "delegate.py",
    "llm_config.json",
    "storage.py",
    "starter.ps1"
]

def deploy():
    print("--- Bắt đầu triển khai cập nhật hệ thống MAS P2P (Multi-Folder Mode) ---")
    
    online_count = 0
    for agent_name, cfg in AGENTS.items():
        if agent_name == "tuyetpt": continue 
        
        # Bỏ qua các định danh agent ảo trong danh sách gốc
        if agent_name in ["votranh_1", "votranh_2", "votranh_3", "votranh_4"]:
            continue
            
        print(f"[*] Đang kiểm tra {agent_name} ({cfg['ssh_host']})...")
        if ping_agent(agent_name):
            online_count += 1
            
            # XÁC ĐỊNH DANH SÁCH THƯ MỤC ĐÍCH
            target_folders = []
            if agent_name == "votranh":
                # Triển khai ra 4 thư mục độc lập
                for i in range(1, 5):
                    target_folders.append((f"votranh_{i}", f"D:\\HAN\\Antigravity\\MAS\\Agent_Votranh_{i}"))
            else:
                # Các máy khác truyền thống
                paths_map = {
                    "hannh": r"C:\Antigravity\MAS\Agent_Hannh",
                    "subin": r"C:\han\mas\Agent_Subin"
                }
                target_folders.append((agent_name, paths_map.get(agent_name)))

            for sub_name, remote_base in target_folders:
                if not remote_base: continue
                print(f"  → Đang triển khai cho {sub_name} tại {remote_base}...")
                
                # Tạo thư mục tools nếu chưa có
                subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"{cfg['ssh_user']}@{cfg['ssh_host']}", f"powershell -Command \"New-Item -ItemType Directory -Force -Path '{remote_base}\\tools'\""], capture_output=True)

                # 1. Sync file chung (trong thu muc tools)
                # O cau truc moi (Flat), tat ca nam trong WORKSPACE_ROOT / tools
                SOURCE_DIR = WORKSPACE_ROOT / "tools"
                for f_name in FILES_TO_SYNC:
                    if f_name == "starter.ps1": continue # Se xử lý riêng o bước sau
                    
                    local_f = SOURCE_DIR / f_name
                    remote_f = f"{remote_base}\\tools\\{f_name}"
                    
                    if local_f.exists():
                        try:
                            subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_f), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_f}"], check=True, capture_output=True)
                        except Exception as e:
                            print(f"    [✗] Lỗi khi copy {f_name}: {e}")

                # 1b. Sync starter.ps1 vao THƯ MỤC GỐC của Agent (De launch_votranh tim thay)
                local_starter = WORKSPACE_ROOT / "starter.ps1"
                remote_starter = f"{remote_base}\\starter.ps1"
                if local_starter.exists():
                    try:
                        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_starter), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_starter}"], check=True, capture_output=True)
                    except Exception as e:
                        print(f"    [✗] Lỗi khi copy starter.ps1: {e}")

                # 2. Sync file config (agent_config.json)
                real_id = "votranh" if "votranh" in sub_name else sub_name
                local_config = WORKSPACE_ROOT / f"tools/agent_config_{real_id}.json"
                if not local_config.exists():
                    local_config = WORKSPACE_ROOT / f"tools/agent_config_{real_id}_fixed.json"
                
                if local_config.exists():
                    try:
                        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_config), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_base}\\tools\\agent_config.json"], check=True, capture_output=True)
                    except Exception: pass
                
                # 3. Sync llm_config.json
                local_llm = WORKSPACE_ROOT / "tools/llm_config.json"
                if local_llm.exists():
                    try:
                        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_llm), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_base}\\tools\\llm_config.json"], check=True, capture_output=True)
                    except Exception: pass

            print(f"  [✓] Đã hoàn thành cập nhật đa thư mục cho {agent_name}")
        else:
            print(f"  [!] {agent_name} đang OFFLINE. Bỏ qua.")
            
    print(f"\n--- Triển khai hoàn tất cho {online_count} máy online. ---")

if __name__ == "__main__":
    deploy()
