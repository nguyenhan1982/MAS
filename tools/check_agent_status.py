"""
check_agent_status.py
Kiểm tra trạng thái online/offline của các agent bằng ICMP Ping.
Sử dụng registry từ delegate.py để tránh lỗi File Not Found.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Thêm tools vào path để import delegate
tools_dir = str(Path(__file__).parent)
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

try:
    import delegate
except ImportError:
    print("[ERROR] Không tìm thấy delegate.py")
    sys.exit(1)

# Fix UTF-8 output cho Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def check_agent(name: str) -> dict:
    """Kiểm tra một agent qua Ping."""
    agent_info = delegate.AGENTS.get(name.lower())
    host = agent_info.get("ssh_host", "unknown") if agent_info else "unknown"
    
    result = {
        "agent": name,
        "host": host,
        "status": "unknown",
        "ping": False,
        "latency_ms": None,
        "error": None,
    }

    if not agent_info:
        result["status"] = "offline"
        result["error"] = "Agent không tồn tại trong registry"
        return result

    # Kiểm tra PING (ICMP) - Trạng thái máy sống
    start_time = time.time()
    is_online = delegate.ping_agent(name)
    
    if is_online:
        result["ping"] = True
        result["status"] = "online"
        result["latency_ms"] = round((time.time() - start_time) * 1000)
    else:
        result["ping"] = False
        result["status"] = "offline"

    return result

def print_table(results: list):
    """In kết quả dạng bảng đẹp."""
    print("\n" + "=" * 55)
    print(f"  {'AGENT':<15} {'TRẠNG THÁI':<20} {'LATENCY':<10}")
    print("=" * 55)

    for r in results:
        status_text = "✓ ONLINE" if r["status"] == "online" else "✗ OFFLINE"
        latency = f"{r['latency_ms']}ms" if r["latency_ms"] else "-"
        print(f"  {r['agent']:<15} {status_text:<20} {latency:<10}")

    print("=" * 55)
    online_count = sum(1 for r in results if r["status"] == "online")
    print(f"\n  {online_count}/{len(results)} agent online\n")

def main():
    parser = argparse.ArgumentParser(description="Kiểm tra trạng thái agent qua Ping")
    parser.add_argument("--agent", help="Tên agent cụ thể")
    parser.add_argument("--json", action="store_true", help="Output dạng JSON")
    args = parser.parse_args()

    if args.agent:
        names = [args.agent]
    else:
        names = list(delegate.AGENTS.keys())

    results = []
    for name in names:
        results.append(check_agent(name))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_table(results)

if __name__ == "__main__":
    main()
