"""
Helper for Google Sheets API Error Handling
Handles 429 Rate Limit errors gracefully with retry logic
"""
import streamlit as st
import time
from functools import wraps

def handle_sheets_errors(func):
    """
    Decorator để bắt lỗi 429 và các lỗi Google Sheets khác.
    Hiển thị thông báo thân thiện cho user.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a 429 error
                if "'code': 429" in error_str or "RATE_LIMIT_EXCEEDED" in error_str or "Quota exceeded" in error_str:
                    wait_time = (attempt + 1) * 20  # 20s, 40s, 60s
                    
                    if attempt < max_retries - 1:
                        st.warning(f"⏱️ Hệ thống đang tải dữ liệu... Vui lòng đợi {wait_time}s (Lần thử {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        st.error(f"🔴 **Hệ thống quá tải!** Google Sheets giới hạn 60 lần đọc/phút.\n\n"
                                f"👉 Vui lòng **chờ 1-2 phút** rồi **Refresh lại trang** (F5).\n\n"
                                f"💡 Gợi ý: Tránh mở nhiều trang/tab cùng lúc để giảm tải hệ thống.")
                        return None  # Return None hoặc empty data tùy function
                else:
                    # Lỗi khác không phải 429
                    raise e
        
        return None
    return wrapper
