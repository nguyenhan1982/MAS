#!/usr/bin/env python3
"""
sync_backups.py - Đồng bộ task_board.json từ máy Master (votranh) sang các Agent online.
"""

import json
import subprocess
import os
import sys
from pathlib import Path

# Đảm bảo import được delegate.py
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))
from delegate import AGENTS, ping_agent, HOST_MACHINE, trigger_agent

def sync_all():
    master_host = HOST_MACHINE["ssh_host"]
    master_user = HOST_MACHINE["ssh_user"]
    master_path = f"{HOST_MACHINE['shared_dir']}\\task_board.json"
    
    # Sử dụng SHARED_DIR từ delegate
    from delegate import SHARED_DIR, WHO_AM_I, PATHS_MAP, SSH_COMMON_OPTS
    local_temp_board = SHARED_DIR / "task_board.json"
    
    print(f"--- Bắt đầu đồng bộ bản backup (Coordinated by {WHO_AM_I}) ---")
    
    # Bước 1: SCP từ Master về Local (Nếu mình không phải Master)
    if WHO_AM_I != "votranh":
        try:
            print(f"[*] Đang tải board từ Master ({master_host}) về local...")
            cmd_pull = ["scp"] + SSH_COMMON_OPTS + [f"{master_user}@{master_host}:{master_path}", str(local_temp_board)]
            subprocess.run(cmd_pull, check=True, capture_output=True)
        except Exception as e:
            print(f"[ERROR] Không thể tải board từ Master: {e}")
            return False
    else:
        print("[*] Đang chạy trên Master, bỏ qua bước pull board.")

    # Bước 2: Duyệt danh sách Agent, nếu online thì SCP từ local board sang Agent đó
    online_agents = []
    for agent_name, cfg in AGENTS.items():
        # Kiểm tra xem có phải máy hiện tại không
        is_local = (agent_name == WHO_AM_I)
        
        print(f"[*] Kiểm tra {agent_name}...")
        is_online = ping_agent(agent_name)
        
        # Kiểm tra xem có phải máy hiện tại không
        is_local = (agent_name == WHO_AM_I)
        
        if is_online or is_local:
            online_agents.append(agent_name)
            # Sử dụng PATHS_MAP từ delegate
            remote_base = PATHS_MAP.get(agent_name, r"C:\Antigravity\MAS")
            remote_target = f"{remote_base}\\task_board.json"
            
            try:
                if not is_local:
                    print(f"  → Đang backup sang {agent_name} ({cfg['ssh_host']})...")
                    cmd_push = ["scp"] + SSH_COMMON_OPTS + [str(local_temp_board), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_target}"]
                    subprocess.run(cmd_push, check=True, capture_output=True)
                    print(f"  [✓] Hoàn thành backup cho {agent_name}")
                else:
                    print(f"  → {agent_name} là máy hiện tại, bỏ qua SCP.")
                
                # Kích hoạt Agent
                print(f"  [*] Gửi tín hiệu kích hoạt (Ping) tới {agent_name}...")
                trigger_res = trigger_agent(agent_name)
                print(f"  {trigger_res}")
                
            except Exception as e:
                print(f"  [✗] Lỗi backup cho {agent_name}: {e}")
    
    print(f"--- Đồng bộ hoàn tất. Đã backup cho {len(online_agents)} agent online. ---")
    return True

if __name__ == "__main__":
    sync_all()
