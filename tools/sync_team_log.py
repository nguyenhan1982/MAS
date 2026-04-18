"""
sync_team_log.py
Thu thap task_log.jsonl tu cac may nhan vien ve file chung tren may Truong phong.

Cach dung:
  python sync_team_log.py

Output: D:\HAN\Multi_Agent_AI_Agent_Sercurity\.tmp\team_log.jsonl
"""

import json
import subprocess
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AGENTS = {
    "tuyetpt": {
        "ssh_host": "100.114.29.24",
        "ssh_user": "admin",
        "log_path": r"C:\Users\Admin\.openclaw\workspace\task_log.jsonl",
    },
    "subin": {
        "ssh_host": "100.114.133.6",
        "ssh_user": "nguye",
        "log_path": r"C:\Users\nguye\.openclaw\workspace\task_log.jsonl",
    },
}

OUTPUT_FILE = Path(__file__).parent.parent / ".tmp" / "team_log.jsonl"


def fetch_log(agent_name: str, agent: dict) -> list:
    """Lay noi dung task_log.jsonl tu may nhan vien qua SSH."""
    cmd = f'type "{agent["log_path"]}" 2>nul'
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             f"{agent['ssh_user']}@{agent['ssh_host']}", cmd],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            return []
        try:
            text = result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            text = result.stdout.decode("cp1252", errors="replace")
        entries = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry["_agent_source"] = agent_name
                entries.append(entry)
            except json.JSONDecodeError:
                pass
        return entries
    except Exception as e:
        print(f"  [{agent_name}] Loi ket noi: {e}")
        return []


def main():
    OUTPUT_FILE.parent.mkdir(exist_ok=True)

    # Doc team_log hien tai de tranh trung lap
    existing_keys = set()
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    key = f"{entry.get('_agent_source')}:{entry.get('ts')}:{entry.get('task')}"
                    existing_keys.add(key)
                except Exception:
                    pass

    new_entries = []
    print(f"Dong bo log tu {len(AGENTS)} may nhan vien...")

    for name, agent in AGENTS.items():
        print(f"  [{name}] Dang lay log...")
        entries = fetch_log(name, agent)
        count = 0
        for entry in entries:
            key = f"{entry.get('_agent_source')}:{entry.get('ts')}:{entry.get('task')}"
            if key not in existing_keys:
                new_entries.append(entry)
                existing_keys.add(key)
                count += 1
        print(f"  [{name}] {count} entry moi")

    if new_entries:
        # Sort theo timestamp
        new_entries.sort(key=lambda x: x.get("ts", ""))
        with OUTPUT_FILE.open("a", encoding="utf-8") as f:
            for entry in new_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"\nDa them {len(new_entries)} entry vao {OUTPUT_FILE}")
    else:
        print("\nKhong co entry moi.")

    # Hien thi 5 entry cuoi
    print("\n--- 5 hoat dong gan nhat ---")
    all_entries = []
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    all_entries.append(json.loads(line.strip()))
                except Exception:
                    pass
    for entry in all_entries[-5:]:
        ts = entry.get("ts", "")[:19]
        agent = entry.get("agent", entry.get("_agent_source", "?"))
        task = entry.get("task", "?")[:40]
        status = entry.get("status", "?")
        print(f"  {ts} [{agent}] {task} → {status}")


if __name__ == "__main__":
    main()
