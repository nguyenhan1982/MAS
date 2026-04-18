#!/usr/bin/env python3
"""
export_pdf.py - Phiên bản Cloud-Master (v2: Tự động tải Font)
Đọc dữ liệu từ Supabase và đảm bảo có Font hỗ trợ Tiếng Việt.
"""

import sys
import os
import re
import requests
from pathlib import Path
from fpdf import FPDF
import markdown

# Thiết lập đường dẫn và import module storage
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))

try:
    import storage
except ImportError:
    print("[ERROR] Không tìm thấy module storage.py")
    sys.exit(1)

# Cấu hình Font
FONT_DIR = Path(__file__).parent / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)
ROBOTO_PATH = FONT_DIR / "Roboto-Regular.ttf"
ROBOTO_URL = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"

OUTPUT_FILE = WORKSPACE_ROOT / "final_report.pdf"

class ULTRA_PDF(FPDF):
    def header(self):
        # Sử dụng font "Vietnamese" đã đăng ký
        try:
            self.set_font("Vietnamese", "I", 8)
        except:
            self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, "AntiGravity Multi-Agent System | Chiến lược AI Security", align="R")
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        try:
            self.set_font("Vietnamese", "I", 8)
        except:
            self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Báo cáo chiến lược - Trang {self.page_no()}/{{nb}}", align="C")

def clean_non_bmp(text):
    return "".join(c for c in text if ord(c) <= 0xFFFF)

# Danh sách các nguồn tải Font hỗ trợ Tiếng Việt (Dự phòng nhiều lớp)
ROBOTO_URLS = [
    "https://github.com/python-visualization/folium/raw/main/folium/templates/fonts/Roboto-Regular.ttf",
    "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf",
    "https://raw.githubusercontent.com/googlefonts/roboto/master/src/hinted/Roboto-Regular.ttf"
]

def ensure_font():
    """Tải Font Roboto từ danh sách dự phòng nếu không có sẵn."""
    if ROBOTO_PATH.exists():
        return True
        
    print("[*] Đang tìm nguồn tải Font hỗ trợ Tiếng Việt...")
    for url in ROBOTO_URLS:
        try:
            print(f"    -> Thử tải từ: {url}")
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                with open(ROBOTO_PATH, "wb") as f:
                    f.write(resp.content)
                print(f"    ✓ Tải font thành công!")
                return True
        except Exception as e:
            print(f"    [!] Nguồn lỗi: {e}")
            continue
            
    print("[ERROR] Tất cả các nguồn tải font đều thất bại.")
    return False

def register_fonts(pdf):
    """Đăng ký font TrueType."""
    if ensure_font() and ROBOTO_PATH.exists():
        try:
            pdf.add_font("Vietnamese", style="", fname=str(ROBOTO_PATH))
            # Alias cho code cũ nếu cần
            pdf.add_font("Arial", style="", fname=str(ROBOTO_PATH))
            return True
        except Exception as e:
            print(f"[!] Lỗi khi đăng ký font: {e}")
    return False

def generate_pdf(report_text, title="Báo cáo"):
    html_content = markdown.markdown(report_text, extensions=['tables', 'fenced_code'])
    html_content = clean_non_bmp(html_content)
    
    # Preprocess HTML: Fix table border
    html_content = html_content.replace("<table>", '<table width="100%" border="1">')
    
    pdf = ULTRA_PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=20, top=20, right=20)
    
    has_font = register_fonts(pdf)
    pdf.add_page()
    
    # Chọn font: Ưu tiên font đã đăng ký
    font_family = "Vietnamese" if has_font else "Helvetica"
    pdf.set_font(font_family, size=11)
    
    styled_html = f'<div style="line-height: 1.4; text-align: justify;">{html_content}</div>'
    
    try:
        pdf.write_html(styled_html)
        pdf.output(str(OUTPUT_FILE))
    except Exception as e:
        print(f"[ERROR] In lỗi HTML: {e}")
        # Chế độ Fallback cuối cùng: Multi-cell text thô
        pdf.add_page()
        pdf.multi_cell(0, 6, clean_non_bmp(report_text))
        pdf.output(str(OUTPUT_FILE))

if __name__ == "__main__":
    mission_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    print(f"[*] Đang lấy dữ liệu từ Cloud...")
    try:
        board = storage.get_board()
        missions = board.get("missions", [])
        
        target_mission = None
        if mission_id:
            target_mission = next((m for m in missions if m["id"] == mission_id), None)
        elif missions:
            target_mission = missions[0]
            
        if not target_mission or not target_mission.get("report"):
            print(f"[ERROR] Không tìm thấy dữ liệu báo cáo.")
            sys.exit(1)
            
        generate_pdf(target_mission["report"], target_mission["goal"])
        print(f"[SUCCESS] PDF generated at: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"[ERROR] Lỗi hệ thống: {e}")
        sys.exit(1)
