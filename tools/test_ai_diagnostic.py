import sys
import json
from pathlib import Path

# Thêm đường dẫn để import
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))

try:
    from agent_core import load_config, call_ai
except ImportError:
    print("[ERROR] Không thể import agent_core. Vui lòng kiểm tra đường dẫn.")
    sys.exit(1)

def test():
    try:
        cfg = load_config()
        agent_name = cfg.get('agent_name', 'Unknown')
        ai_cfg = cfg.get('ai_config', {})
        provider = ai_cfg.get('provider', 'N/A')
        model = ai_cfg.get('model', 'N/A')
        
        print(f"--- DIAGNOSTIC: Agent [{agent_name}] ---")
        print(f"[*] AI Provider: {provider}")
        print(f"[*] AI Model: {model}")
        
        prompt = "Trả lời siêu ngắn gọn: 1+1=?"
        print("[*] Đang gọi AI...")
        result = call_ai(cfg, prompt)
        
        print(f"[✓] Kết quả AI: {result.strip()}")
        return True
    except Exception as e:
        print(f"[✗] LỖI DIAGNOSTIC: {e}")
        return False

if __name__ == "__main__":
    test()
