#!/usr/bin/env python3
"""
update_server_location.py - Tự động nhận diện IP Server và cập nhật cho toàn mạng lưới.
Sử dụng khi bạn di chuyển Central Server từ máy này sang máy khác.
"""

import json
import socket
import subprocess
import sys
from pathlib import Path

# Thêm đường dẫn để import delegate
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))
from delegate import AGENTS, ping_agent

def get_tailscale_ip():
    """Lấy IP Tailscale (thường bắt đầu bằng 100.)."""
    try:
        # Cách 1: Thử gọi lệnh tailscale
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    # Cách 2: Duyệt các interface mạng
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith("100."):
                return ip
    except:
        pass
    return "127.0.0.1"

def update_local_config(server_ip):
    config_path = WORKSPACE_ROOT / "tools" / "agent_config.json"
    if not config_path.exists():
        print(f"[ERROR] Không tìm thấy {config_path}")
        return False
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    new_url = f"http://{server_ip}:5000"
    if config.get("central_server") == new_url:
        print(f"[*] Cấu hình local đã chính xác: {new_url}")
    else:
        config["central_server"] = new_url
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[✓] Đã cập nhật local Central Server: {new_url}")
    return True

def sync_config_to_agents(server_ip):
    config_path = WORKSPACE_ROOT / "tools" / "agent_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        base_config = json.load(f)

    online_count = 0
    for agent_name, cfg in AGENTS.items():
        # Không cần push cho chính mình (đã làm ở trên) nhưng nếu test agent local thì vẫn cần
        print(f"[*] Đang kiểm tra Agent: {agent_name}...")
        if ping_agent(agent_name):
            # Tùy biến config cho từng agent (đổi tên agent)
            agent_cfg = base_config.copy()
            agent_cfg["agent_name"] = agent_name
            
            # Tạo file tạm để push
            tmp_file = WORKSPACE_ROOT / f"agent_config_{agent_name}.json"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(agent_cfg, f, ensure_ascii=False, indent=2)
            
            # Xác định đường dẫn máy Agent
            paths_map = {
                "hannh": r"C:\Antigravity\MAS",
                "votranh": r"D:\HAN\Antigravity\MAS",
                "subin": r"C:\han\mas",
                "tuyetpt": r"D:\Han\Mas"
            }
            remote_base = paths_map.get(agent_name, r"C:\Antigravity\MAS")
            remote_target = f"{remote_base}\\tools\\agent_config.json"
            
            try:
                print(f"  → Đang đẩy cấu hình sang {agent_name} ({cfg['ssh_host']})...")
                subprocess.run(
                    ["scp", str(tmp_file), f"{cfg['ssh_user']}@{cfg['ssh_host']}:{remote_target}"],
                    check=True, capture_output=True
                )
                print(f"  [✓] Đã cập nhật xong cho {agent_name}")
                online_count += 1
            except Exception as e:
                print(f"  [✗] Lỗi khi đẩy cấu hình sang {agent_name}: {e}")
            finally:
                if tmp_file.exists(): tmp_file.unlink()
    
    print(f"--- Đã đồng bộ cấu hình cho {online_count} Agent online. ---")

def main():
    print("--- QUY TRÌNH THIẾT LẬP VỊ TRÍ SERVER TỰ ĐỘNG ---")
    server_ip = get_tailscale_ip()
    print(f"[*] Nhận diện IP Server hiện tại: {server_ip}")
    
    if update_local_config(server_ip):
        sync_config_to_agents(server_ip)

if __name__ == "__main__":
    main()
