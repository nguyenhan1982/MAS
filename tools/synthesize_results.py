#!/usr/bin/env python3
"""
synthesize_results.py - Tổng hợp kết quả từ tất cả các Agent bằng cách sử dụng storage module.
Tương thích cả Local (file) và Cloud (Supabase).
"""

import json
import os
import sys
from pathlib import Path

# Thiết lập vai trò Server để llm_client.py ưu tiên mô hình Cloud
os.environ["MAS_ROLE"] = "server"

# Thêm đường dẫn để import các module local
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))

try:
    from llm_client import call_llm_with_fallback
    import storage
except ImportError:
    print("[ERROR] Không tìm thấy module cần thiết trong thư mục tools/")
    sys.exit(1)

def synthesize(mission_id=None):
    print("[*] Đang tải board dữ liệu...")
    board = storage.get_board()

    missions = board.get("missions", [])
    if not missions:
        return "Chưa có mission nào."

    # Tìm mission cần tổng hợp
    target_mission = None
    if mission_id:
        target_mission = next((m for m in missions if m["id"] == mission_id), None)
    else:
        # Mặc định lấy mission đầu tiên (mới nhất) nếu không chỉ định
        target_mission = missions[0]

    if not target_mission:
        return f"Không tìm thấy mission có ID: {mission_id}"

    done_tasks = [t for t in target_mission.get("tasks", []) if t.get("status") == "done"]

    if not done_tasks:
        return "Chưa có nhiệm vụ nào của mission này hoàn thành để tổng hợp."

    # Xây dựng ngữ cảnh cho AI
    context = f"Dưới đây là kết quả chi tiết cho nhiệm vụ chiến lược: '{target_mission['goal']}'\n\n"
    
    details_section = "\n\n---\n# PHẦN 2: PHỤ LỤC CHI TIẾT TỪ CÁC AGENT\n\n"
    
    for t in done_tasks:
        context += f"### Nhiệm vụ con: {t['title']}\n"
        context += f"**Agent thực hiện:** {t['assigned_to']}\n"
        context += f"**Mô tả:** {t['description']}\n"
        context += f"**Kết quả:**\n{t['result']}\n"
        context += "---\n"
        
        details_section += f"### {t['title']} (Thực hiện bởi: {t['assigned_to']})\n\n"
        details_section += t['result'] + "\n\n---\n"

    # Prompt tổng hợp
    prompt = f"""
Bạn là một Chuyên gia Phân tích Chiến lược AI. 
Dựa trên các báo cáo chi tiết dưới đây từ các Agent chuyên trách, hãy viết một **BÁO CÁO TỔNG TỔNG HỢP CHIẾN LƯỢC** cho mục tiêu: "{target_mission['goal']}".

Yêu cầu báo cáo:
1. Tiêu đề chuyên nghiệp và tóm tắt executive summary.
2. Phân tích sự kết hợp giữa các mảnh ghép từ các Agent.
3. Đưa ra kiến nghị hành động cụ thể.
4. Ngôn ngữ: Tiếng Việt, trình bày Markdown.

DỮ LIỆU ĐẦU VÀO:
{context}
"""

    print(f"[*] Đang tổng hợp cho Mission: {target_mission['id']}...")
    summary = call_llm_with_fallback(prompt, system_instruction="Bạn là AI đầu não thực hiện tổng hợp tri thức.")

    if summary.startswith("[ERROR]"):
        print(f"\n[!] AI Synthesis Failed: {summary}")
        # Không lưu kết quả lỗi vào Database để UI có thể nhận biết là 'chưa có báo cáo'
        return summary

    final_report = f"# BÁO CÁO TỔNG HỢP: {target_mission['goal']}\n\n"
    final_report += summary
    final_report += details_section
    
    # Cập nhật kết quả vào board
    target_mission["report"] = final_report
    print(f"[*] Đang lưu báo cáo (Mode: {storage.STORAGE_MODE})...")
    if storage.save_board(board):
        print(f"✓ Đã cập nhật báo cáo thành công.")
        return final_report
    else:
        print("[!] Lỗi khi lưu báo cáo.")
        return final_report

if __name__ == "__main__":
    mid = sys.argv[1] if len(sys.argv) > 1 else None
    report = synthesize(mid)
    
    # Lưu ra file markdown (optional local backup)
    try:
        report_path = WORKSPACE_ROOT / "final_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
    except: pass
    
    print(f"\n[✓] Hoàn tất tổng hợp.")
