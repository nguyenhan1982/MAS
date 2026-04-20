"""
llm_client.py - Module điều phối AI với cơ chế Fallback.
Thử nghiệm các mô hình theo thứ tự ưu tiên: Gemini -> Cerebras -> Sambanova -> Groq.
"""

import json
import requests
import sys
import io
import os
from datetime import datetime
from dotenv import load_dotenv

try:
    from search_tool import web_search
except ImportError:
    web_search = None

# --- PATHS ---
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Nạp .env từ thư mục gốc của thành phần (CenterServer hoặc Agent_Tuyetpt)
load_dotenv(os.path.join(WORKSPACE_ROOT, ".env"))

CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "tools", "llm_config.json")

def load_local_config():
    """Nạp cấu hình từ file nội bộ của dự án."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Lỗi khi đọc file config: {e}")
    return {}

LOCAL_CONFIG = load_local_config()

def get_current_agent_name():
    """Lấy tên Agent từ delegate.WHO_AM_I."""
    try:
        import delegate
        return delegate.WHO_AM_I
    except ImportError:
        return "center_server"

# --- CONFIGURATION (Tự động nạp Key) ---
def get_providers():
    agent_name = get_current_agent_name()
    role = os.environ.get("MAS_ROLE", "agent") # "agent" hoặc "server"
    all_providers = []
    
    # 1. Nạp tất cả providers từ config
    config_data = LOCAL_CONFIG
    config_providers = config_data.get("providers", [])
    
    # Chuẩn hóa format
    for p in config_providers:
        all_providers.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "type": p.get("type", "openai"),
            "url": p.get("url", ""),
            "key": p.get("key") if p.get("type") != "google" else None, # Google dùng url có key
            "model": p.get("model", "")
        })

    # 2. Xử lý ưu tiên
    final_providers = []
    
    # CHO PHÉP tất cả các Agent trên máy votranh (bao gồm các Agent ảo) được phép gọi Ollama
    if "votranh" in agent_name.lower() and role != "server":
        final_providers.append({
            "id": "ollama",
            "name": "Ollama (Local)",
            "type": "ollama",
            "url": "http://127.0.0.1:11434/api/generate",
            "model": "gemma4:e4b"
        })
        # Đối với votranh, giữ nguyên thứ tự mặc định của providers
        final_providers.extend(all_providers)
    else:
        # Đối với các máy khác (tuyetpt, subin, server...), dùng non_votranh_priority
        priority_ids = config_data.get("non_votranh_priority", [])
        if priority_ids:
            # Sắp xếp theo ID trong list priority
            provider_map = {p["id"]: p for p in all_providers}
            for pid in priority_ids:
                if pid in provider_map:
                    final_providers.append(provider_map[pid])
            # Thêm nốt những cái còn lại (nếu có)
            for p in all_providers:
                if p["id"] not in priority_ids:
                    final_providers.append(p)
        else:
            final_providers.extend(all_providers)
            
    # 3. Dynamic override from Environment Variables (.env)
    env_keys = {
        "gemini": "GOOGLE_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "sambanova": "SAMBANOVA_API_KEY",
        "groq": "GROQ_API_KEY"
    }
    
    for p in all_providers:
        pid = p["id"].lower()
        env_var = None
        
        # Tìm kiếm env_var tương ứng dựa trên tiền tố hoặc từ khóa
        # Ví dụ: "gemini-3-flash" sẽ khớp với key "gemini"
        for key, var_name in env_keys.items():
            if key in pid:
                env_var = var_name
                break
        
        # CHỈ gọi os.environ.get nếu env_var không phải là None để tránh lỗi "str expected, not NoneType"
        if env_var:
            val = os.environ.get(env_var)
            if val:
                if "gemini" in pid and "key=" in p["url"]:
                    import re
                    # Cập nhật key trong URL cho Gemini
                    p["url"] = re.sub(r'key=[^&]+', f'key={val}', p["url"])
                else:
                    # Cập nhật key trong header cho các provider khác
                    p["key"] = val

    # DEBUG
    print(f"[*] AI System loaded {len(final_providers)} providers: {[p['name'] for p in final_providers]}")
    return final_providers

LLM_PROVIDERS = get_providers()

def call_google(provider, prompt, system_instruction=""):
    full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }
    
    resp = requests.post(provider["url"], json=payload, timeout=1200)
    if resp.status_code != 200:
        print(f"DEBUG Google Error: {resp.status_code} - {resp.text}")
    resp.raise_for_status()
    data = resp.json()
    # Lưu ý: Gemini trả về kết quả kèm citations nếu có
    return data['candidates'][0]['content']['parts'][0]['text']

def call_openai_style(provider, prompt, system_instruction=""):
    headers = {
        "Authorization": f"Bearer {provider['key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    resp = requests.post(provider["url"], headers=headers, json=payload, timeout=1200)
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']

def call_ollama(provider, prompt, system_instruction=""):
    full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
    payload = {
        "model": provider["model"],
        "prompt": full_prompt,
        "stream": False
    }
    
    try:
        resp = requests.post(provider["url"], json=payload, timeout=1200)
        resp.raise_for_status()
        data = resp.json()
        return data['response']
    except Exception as e:
        raise Exception(f"Ollama không phản hồi tại {provider['url']}. Lỗi: {str(e)}")

def call_llm_with_fallback(prompt, system_instruction=""):
    """Thử gọi các LLM theo thứ tự cho đến khi thành công."""
    last_error = ""
    
    # Lấy thông tin vai trò để quyết định logic tiêm ngữ cảnh
    role = os.environ.get("MAS_ROLE", "agent")
    
    # TIÊM NGỮ CẢNH THỜI GIAN THỰC
    now = datetime.now()
    real_time_str = now.strftime('%d/%m/%Y %H:%M:%S')
    
    # CHỈ cưỡng chế ngày tháng đối với Agent (không áp dụng cho Server để tránh hỏng định dạng JSON khi phân rã/tổng hợp)
    if role != "server":
        time_instruction = f"\n[QUY ĐỊNH HỆ THỐNG: Ngày hiện tại là {real_time_str}. Khi viết báo cáo, BẮT BUỘC phải ghi đúng ngày thực hiện là {now.strftime('%d/%m/%Y')}. TUYỆT ĐỐI không dùng ngày cũ trong dữ liệu tập huấn.]\n"
        enhanced_system_instruction = (system_instruction + time_instruction) if system_instruction else time_instruction
    else:
        # Đối với Server, chỉ cung cấp thông tin ngày tháng, không ra lệnh cưỡng chế viết vào kết quả
        time_info = f"\n[Thông tin hệ thống: Hiện tại là {real_time_str}]\n"
        enhanced_system_instruction = (system_instruction + time_info) if system_instruction else time_info
    
    for provider in LLM_PROVIDERS:
        try:
            print(f"[*] Calling AI: {provider['name']}...")
            
            # Xử lý đặc biệt cho Google (Đã có Search Grounding tích hợp)
            if provider["type"] == "google":
                return call_google(provider, prompt, enhanced_system_instruction)
            
            # Xử lý cho các mô hình khác (Sử dụng Search Tool bên ngoài nếu cần)
            current_prompt = prompt
            if web_search and any(key in prompt.lower() for key in ["thời tiết", "tin tức", "giá vàng", "tỷ giá", "mới nhất", "hiện nay"]):
                search_results = web_search(prompt)
                current_prompt = f"DỮ LIỆU TRA CỨU WEB THỜI GIAN THỰC:\n{search_results}\n\nCÂU HỎI NGƯỜI DÙNG: {prompt}"
            
            full_prompt = enhanced_system_instruction + "\n" + current_prompt

            if provider["type"] == "ollama":
                return call_ollama(provider, full_prompt, "")
            else:
                return call_openai_style(provider, current_prompt, enhanced_system_instruction)
                
        except Exception as e:
            last_error = str(e)
            print(f"[!] Error calling {provider['name']}: {last_error}")
            continue
    
    import re
    # Che giấu API Key trong thông báo lỗi (đặc biệt là Google Key trong URL)
    masked_error = re.sub(r'key=[^& \n"]+', 'key=***MASKED***', last_error)
            
    return f"[ERROR] Tất cả các mô hình AI đều thất bại. Lỗi: {masked_error}"

if __name__ == "__main__":
    # Test nhanh
    print(call_llm_with_fallback("Hãy chào bằng tiếng Việt."))
