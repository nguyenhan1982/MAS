import requests
import json
import sys

# Fix UTF-8 cho Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("[*] Đang kiểm tra Ollama trên localhost:11434...")
url = "http://localhost:11434/api/generate"
payload = {
    "model": "gemma4:e4b",
    "prompt": "Bạn là ai? Hãy trả lời bằng một câu tiếng Việt ngắn gọn.",
    "stream": False
}

try:
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()
    print(f"[THÀNH CÔNG] Phản hồi từ mô hình: {result.get('response')}")
except Exception as e:
    print(f"[THẤT BẠI] Lỗi: {e}")
