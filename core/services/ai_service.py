import google.generativeai as genai
import streamlit as st
import pandas as pd

def analyze_ncr_data(summary_text, api_key):
    """
    Sends summary data to Gemini 1.5 Flash for analysis.
    
    Args:
        summary_text (str): Pre-formatted summary of the data.
        api_key (str): Google AI Studio API Key.
        
    Returns:
        str: AI generated insight or error message.
    """
    if not api_key:
        return "⚠️ Chưa cấu hình API Key. Vui lòng thêm `GEMINI_API_KEY` vào `.streamlit/secrets.toml`."

    try:
        genai.configure(api_key=api_key)
        # Gemini 1.5 Flash is cost-effective and fast for this task
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = f"""
        Bạn là Trợ lý phân tích chất lượng (QC Analyst) chuyên nghiệp của nhà máy sản xuất bao bì.
        Hãy phân tích dữ liệu tóm tắt NCR (Non-Conformance Report) dưới đây và đưa ra báo cáo ngắn gọn cho Giám đốc.

        DỮ LIỆU ĐẦU VÀO:
        {summary_text}

        YÊU CẦU OUTPUT:
        Hãy viết một báo cáo ngắn gọn (dưới 10 dòng) gồm các mục sau:
        1. **Tổng quan**: Nhận xét nhanh về tình hình lỗi (Tăng/Giảm/Bất thường).
        2. **Vấn đề trọng yếu**: Chỉ ra bộ phận hoặc loại lỗi cần quan tâm nhất (chiếm tỷ trọng cao).
        3. **Khuyến nghị**: Đề xuất 1 hành động cụ thể để khắc phục ngay.
        
        Phong cách: Chuyên nghiệp, súc tích, khách quan. Dùng tiếng Việt.
        """

        with st.spinner("🤖 AI đang đọc dữ liệu và viết báo cáo..."):
            response = model.generate_content(prompt)
            return response.text
            
    except Exception as e:
        return f"❌ Lỗi khi gọi AI: {str(e)}"
