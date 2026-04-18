import re
import os
from pathlib import Path
import sys

# Đảm bảo console hỗ trợ tiếng Việt
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def main():
    home = Path.home()
    identity_file = home / ".openclaw" / "workspace" / "IDENTITY.md"
    
    if not identity_file.exists():
        print(f"Không tìm thấy file: {identity_file}")
        return
        
    content = identity_file.read_text(encoding='utf-8')
    
    # Tìm phần nội dung trước quy tắc P2P (tìm header có chữ QUY TẮC hoặc Quy tac)
    import re
    pattern = r'\n+---\s*\n+## (QUY TẮC|Quy tac).*'
    parts = re.split(pattern, content, flags=re.IGNORECASE | re.DOTALL)
    base_content = parts[0].strip()
    
    new_rules = r"""
---
## QUY TẮC MẠNG NGANG HÀNG (P2P FULL-MESH) BẮT BUỘC
1. KHÔNG CÓ TRƯỞNG PHÒNG TRONG HỆ THỐNG: Mọi máy đều bình đẳng. Khi bạn nhận được bất kỳ task nào trực tiếp từ người dùng, BẠN chính là người chịu trách nhiệm điều phối mạng lưới.
2. PHẢI CÓ TÀI LIỆU HƯỚNG DẪN: Đừng bao giờ bịa ra tên script hay gọi tool Python mù quáng. HÃY luôn luôn đọc file `D:\HAN\Multi_Agent_AI_Agent_Sercurity\tools\HUONG_DAN_NGANG_HANG.md` (đọc cục bộ nếu bạn là votranh) hoặc qua SSH `ssh anhng@100.64.87.73 "type \"D:\HAN\Multi_Agent_AI_Agent_Sercurity\tools\HUONG_DAN_NGANG_HANG.md\""` (nếu bạn là hannh, tuyetpt, subin).
3. ỦY QUYỀN VÀ GHI BOARD: Coppy chuẩn dòng lệnh SSH trong file Hướng Dẫn trên để kiểm soát Task Board và List AI Online.
"""
    
    with open(identity_file, 'w', encoding='utf-8') as f:
        f.write(base_content + "\n" + new_rules)
        
    print(f"Cập nhật hành vi Ngang Hàng P2P thành công cho: {identity_file}")

if __name__ == "__main__":
    main()
