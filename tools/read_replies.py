"""
read_replies.py
Đọc phản hồi từ các agent qua OpenClaw Gateway Sessions API.

Cách dùng:
  python tools/read_replies.py                     # Đọc reply từ tất cả agent
  python tools/read_replies.py --agent votranh     # Chỉ đọc từ votranh
  python tools/read_replies.py --since 10m         # Reply trong 10 phút gần đây
  python tools/read_replies.py --wait 60           # Chờ tối đa 60 giây

Yêu cầu:
  pip install requests
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Thiếu thư viện: pip install requests")
    sys.exit(1)

WORKSPACE_ROOT = Path(__file__).parent.parent
AGENTS_FILE = WORKSPACE_ROOT / "AGENTS_NETWORK.md"
LOG_FILE = WORKSPACE_ROOT / ".tmp" / "task_log.jsonl"
REPLIES_FILE = WORKSPACE_ROOT / ".tmp" / "replies.jsonl"


def parse_agents_network() -> dict:
    """Đọc AGENTS_NETWORK.md và trả về dict cấu hình agent."""
    if not AGENTS_FILE.exists():
        print(f"Không tìm thấy {AGENTS_FILE}")
        sys.exit(1)

    content = AGENTS_FILE.read_text(encoding="utf-8")
    agents = {}

    table_pattern = re.compile(
        r"\|\s*(\w+)\s*\|\s*([^\|]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE
    )
    for match in table_pattern.finditer(content):
        name, host, port = match.groups()
        name = name.strip().lower()
        host = host.strip()
        port = int(port.strip())
        if name not in ("tên", "---"):
            agents[name] = {"host": host, "port": port}

    token_pattern = re.compile(r"^(\w+)_GATEWAY_TOKEN=(.+)$", re.MULTILINE)
    for match in token_pattern.finditer(content):
        agent_prefix, token = match.groups()
        name = agent_prefix.lower()
        token = token.strip()
        if name in agents and not token.startswith("<"):
            agents[name]["token"] = token

    host_pattern = re.compile(r"^(\w+)_TAILSCALE_HOST=(.+)$", re.MULTILINE)
    for match in host_pattern.finditer(content):
        agent_prefix, host = match.groups()
        name = agent_prefix.lower()
        host = host.strip()
        if name in agents and not host.startswith("<") and "<TAILNET>" not in host:
            agents[name]["host"] = host

    return agents


def parse_since(since_str: str) -> datetime:
    """Parse chuỗi thời gian như '10m', '1h', '30s' thành datetime."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.match(r"^(\d+)([smhd])$", since_str.lower())
    if not match:
        print(f"Format --since không hợp lệ: '{since_str}'. Dùng: 10m, 1h, 30s")
        sys.exit(1)
    value, unit = match.groups()
    delta = timedelta(seconds=int(value) * units[unit])
    return datetime.now() - delta


def fetch_sessions(host: str, port: int, token: str) -> list:
    """Lấy danh sách sessions từ OpenClaw Gateway."""
    url = f"http://{host}:{port}/api/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "sessions" in data:
                return data["sessions"]
        return []
    except Exception:
        return []


def fetch_session_messages(host: str, port: int, token: str, session_id: str) -> list:
    """Lấy messages của một session cụ thể."""
    url = f"http://{host}:{port}/api/sessions/{session_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else []
        return []
    except Exception:
        return []


def read_replies_from_log(agent_name: str = None, since: datetime = None) -> list:
    """
    Đọc replies từ file log local (.tmp/replies.jsonl).
    Dùng khi agents ghi kết quả về máy chủ qua shared storage.
    """
    if not REPLIES_FILE.exists():
        return []

    replies = []
    with REPLIES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if agent_name and entry.get("agent") != agent_name:
                    continue
                if since:
                    ts = datetime.fromisoformat(entry.get("timestamp", ""))
                    if ts < since:
                        continue
                replies.append(entry)
            except (json.JSONDecodeError, ValueError):
                continue

    return sorted(replies, key=lambda x: x.get("timestamp", ""), reverse=True)


def poll_agent_replies(name: str, config: dict, since: datetime = None) -> list:
    """
    Poll replies từ remote agent qua OpenClaw Sessions API.
    Trả về list các reply messages.
    """
    host = config.get("host", "")
    port = config.get("port", 18789)
    token = config.get("token", "")

    if "<TAILNET>" in host or (host.endswith(".ts.net") and "<" in host):
        return []
    if not token or token.startswith("<"):
        return []

    sessions = fetch_sessions(host, port, token)
    if not sessions:
        return []

    replies = []
    for session in sessions[:10]:  # Chỉ lấy 10 session gần nhất
        session_id = session.get("sessionId") or session.get("id", "")
        if not session_id:
            continue

        messages = fetch_session_messages(host, port, token, session_id)
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            ts_raw = msg.get("timestamp") or msg.get("createdAt", "")

            # Chỉ lấy responses từ assistant
            if role != "assistant":
                continue

            if since and ts_raw:
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    # Convert to naive datetime for comparison
                    ts = ts.replace(tzinfo=None)
                    if ts < since:
                        continue
                except (ValueError, AttributeError):
                    pass

            replies.append({
                "agent": name,
                "session_id": session_id,
                "timestamp": ts_raw,
                "content": content[:1000],
                "source": "sessions_api",
            })

    return replies


def print_replies(all_replies: dict):
    """In replies dạng dễ đọc."""
    total = sum(len(r) for r in all_replies.values())
    print(f"\n{'='*65}")
    print(f"  Tổng cộng {total} reply\n")

    if total == 0:
        print("  Chưa có phản hồi nào.")
        print("  Gợi ý: Dùng --wait 60 để chờ tối đa 60 giây")
        print(f"{'='*65}\n")
        return

    for agent_name, replies in all_replies.items():
        if not replies:
            print(f"  [{agent_name.upper()}] Không có reply\n")
            continue

        print(f"  [{agent_name.upper()}] {len(replies)} reply:")
        for r in replies[:5]:  # Hiển thị tối đa 5 reply gần nhất
            ts = r.get("timestamp", "")
            content = r.get("content", "")
            print(f"  {'─'*60}")
            if ts:
                print(f"  Thời gian: {ts}")
            print(f"  {content[:400]}{'...' if len(content) > 400 else ''}")
        print()

    print(f"{'='*65}")
    print(f"  Log file: {REPLIES_FILE}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Đọc phản hồi từ remote agents qua OpenClaw Sessions API"
    )
    parser.add_argument("--agent", help="Chỉ đọc từ agent này (votranh/tuyetpt/subin)")
    parser.add_argument("--since", default="1h",
                        help="Lọc reply từ X thời gian trước (ví dụ: 10m, 1h, 30s). Mặc định: 1h")
    parser.add_argument("--wait", type=int, default=0,
                        help="Chờ tối đa N giây cho đến khi có reply mới")
    parser.add_argument("--json", action="store_true", help="Output dạng JSON")
    args = parser.parse_args()

    since = parse_since(args.since)
    agents = parse_agents_network()

    if args.agent:
        name = args.agent.lower()
        if name not in agents:
            print(f"Không tìm thấy agent '{name}'. Có: {list(agents.keys())}")
            sys.exit(1)
        targets = {name: agents[name]}
    else:
        targets = agents

    deadline = time.time() + args.wait if args.wait > 0 else 0

    while True:
        all_replies = {}

        for name, config in targets.items():
            # Thử Sessions API
            replies = poll_agent_replies(name, config, since)
            # Fallback: đọc từ log local
            if not replies:
                replies = read_replies_from_log(name, since)
            all_replies[name] = replies

        total = sum(len(r) for r in all_replies.values())

        # Nếu đang chờ và chưa có reply
        if args.wait > 0 and total == 0 and time.time() < deadline:
            remaining = int(deadline - time.time())
            print(f"  Đang chờ reply... ({remaining}s còn lại)", end="\r", flush=True)
            time.sleep(3)
            continue

        break

    if args.json:
        flat = [r for replies in all_replies.values() for r in replies]
        print(json.dumps(flat, ensure_ascii=False, indent=2))
    else:
        print_replies(all_replies)


if __name__ == "__main__":
    main()
