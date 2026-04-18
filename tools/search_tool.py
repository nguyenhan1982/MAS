from duckduckgo_search import DDGS
import json

def web_search(query, max_results=3):
    """Thực hiện tìm kiếm web và trả về kết quả thô."""
    print(f"[*] Đang thực hiện tra cứu Web cho: '{query}'...")
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"Tiêu đề: {r['title']}\nNội dung: {r['body']}\nNguồn: {r['href']}\n")
        
        if not results:
            return "Không tìm thấy kết quả tìm kiếm."
            
        return "\n---\n".join(results)
    except Exception as e:
        return f"Lỗi khi tra cứu web: {str(e)}"

if __name__ == "__main__":
    # Test nhanh
    print(web_search("Thời tiết Hà Nội hôm nay"))
