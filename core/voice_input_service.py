import google.generativeai as genai
import streamlit as st
import json
import re

def configure_genai():
    """Đảm bảo GenAI được cấu hình"""
    try:
        # Try multiple paths for API Key
        api_key = st.secrets.get("GEMINI_API_KEY") 
        if not api_key:
            api_key = st.secrets.get("gemini", {}).get("api_key")
            
        if api_key:
            genai.configure(api_key=api_key)
        else:
            print("⚠️ start_voice_service: API Key not found in secrets.")
    except Exception as e:
        print(f"Error configuring GenAI: {e}")

def extract_json(text):
    """Trích xuất JSON từ markdown text"""
    try:
        # Tìm block json trong ```json ... ``` hoặc [...]
        match = re.search(r'```json\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # Thử tìm mảng JSON trực tiếp
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
            
        return []
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return []

def process_audio_defect(audio_bytes: bytes, list_loi: list, list_vi_tri: list) -> list[dict]:
    """
    Gửi audio trực tiếp lên Gemini Flash để trích xuất list lỗi.
    Input:
        - audio_bytes: Raw bytes từ recorder
        - list_loi: Danh sách tên lỗi chuẩn để matching
        - list_vi_tri: Danh sách vị trí chuẩn
    Output:
        - List of dict: [{"ten_loi": "...", "vi_tri": "...", "sl_loi": 1, "muc_do": "..."}]
    """
    if not audio_bytes:
        return []

    configure_genai()
    
    # Sử dụng model Flash cho tốc độ và native audio support
    # Updated to 2.5-flash based on available models
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Chuẩn bị prompt context
    str_list_loi = ", ".join(list_loi) if list_loi else "Không có danh sách chuẩn"
    str_list_vi_tri = ", ".join(list_vi_tri) if list_vi_tri else "Không có danh sách vị trí"
    
    prompt = f"""
    Bạn là một trợ lý QC (Quality Control) chuyên nghiệp.
    Nhiệm vụ: Nghe đoạn ghi âm và trích xuất file JSON chứa **DANH SÁCH TẤT CẢ** các lỗi được nhắc đến.
    
    Hãy chú ý phân tách các lỗi khi người nói dùng các từ nối như: "và", "thêm", "với", "tiếp theo là", "còn có"...
    Ví dụ: "Rách 2 cái và Bẩn 1 cái" -> Phải ra 2 items.

    Dưới đây là danh sách tham chiếu chuẩn (Reference Data):
    - Tên lỗi chuẩn (Standard Defects): {str_list_loi}
    - Các vị trí lỗi thường gặp: {str_list_vi_tri}
    - Mức độ lỗi (Severity): "Nhẹ", "Nặng", "Nghiêm trọng". Mặc định là "Nhẹ".

    QUY TẮC XỬ LÝ QUAN TRỌNG:
    1. **Matching (So khớp)**:
       - Nếu nghe được tên lỗi, hãy tìm tên tương ứng gần đúng nhất trong "Tên lỗi chuẩn".
       - Nếu khớp được (kể cả từ đồng nghĩa hoặc phát âm gần giống), hãy dùng tên chuẩn đó.
       - Nếu nghe rõ ràng là một lỗi nhưng KHÔNG có trong danh sách chuẩn, và cũng không giống lỗi nào -> Hãy gán tên lỗi là "UNKNOWN_DEFECT" và ghi lại nội dung gốc vào field "raw_input".
       - Nếu lời nói không liên quan đến báo cáo lỗi -> Bỏ qua.

    2. **Default Values (Giá trị mặc định)**:
       - Số lượng: Nếu không nói rõ số lượng, mặc định là 1.
       - Mức độ: Nếu không nói rõ, mặc định là "Nhẹ".
       - Vị trí: Nếu không nghe thấy, để chuỗi rỗng "".

    3. **Output Format**:
       - Bắt buộc trả về một JSON Array.
       - Mỗi phần tử có cấu trúc:
         {{
           "ten_loi": "Tên chuẩn hoặc UNKNOWN_DEFECT",
           "raw_input": "Từ user nói (chỉ khi UNKNOWN)",
           "vi_tri": "Vị trí nghe được",
           "sl_loi": số_lượng_int,
           "muc_do": "Nhẹ/Nặng/Nghiêm trọng"
         }}

    Hãy xử lý âm thanh cung cấp và trả về JSON kết quả.
    """
    
    try:
        # Gọi API với audio bytes trực tiếp
        # Gemini Python SDK hỗ trợ dictionary cho các parts multimodality: {'mime_type': '...', 'data': ...}
        response = model.generate_content([
            prompt, 
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        
        return extract_json(response.text)
        
    except Exception as e:
        # Log error
        print(f"Gemini API Error: {e}")
        return []
