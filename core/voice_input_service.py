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
        - Tuple: (List of dict results, dict usage_info)
    """
    if not audio_bytes:
        return []

    configure_genai()
    
    # Sử dụng model Gemini 2.0 Flash (Reverted from 2.5 due to freeze/timeout issues)
    # Available in list: models/gemini-2.0-flash
    model = genai.GenerativeModel('gemini-2.0-flash')
    
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
    - Mức độ lỗi (Severity): "Nhẹ", "Nặng". Mặc định là "Nặng".

    QUY TẮC XỬ LÝ QUAN TRỌNG:
    1. **Matching (So khớp)**:
       - Nếu nghe được tên lỗi, hãy tìm tên tương ứng gần đúng nhất trong "Tên lỗi chuẩn".
       - Nếu người dùng nói "lỗi dệt", hãy tìm tên lỗi chứa từ "dệt" phù hợp nhất trong danh sách.
       - Chỉ trả về "UNKNOWN_DEFECT" nếu thực sự không thể map được với bất kỳ lỗi nào.

    2. **Default Values (Giá trị mặc định)**:
       - Số lượng: Nếu không nói rõ số lượng, mặc định là 1.
       - Mức độ: Nếu không nói rõ, mặc định là "Nhẹ".
       - Vị trí: Nếu không nghe thấy, để chuỗi rỗng "".

    3. **Output Format**:
       - Bắt buộc trả về một JSON Array thuần túy, không markdown.
       - Mỗi phần tử có cấu trúc:
         {{
           "ten_loi": "Tên chuẩn hoặc UNKNOWN_DEFECT",
           "raw_input": "Từ user nói (chỉ khi UNKNOWN)",
           "vi_tri": "Vị trí nghe được",
           "sl_loi": <số nguyên>,
           "muc_do": "Nhẹ/Nặng"
         }}
       
       Example output:
       [
          {{ "ten_loi": "Rách", "vi_tri": "Thân sau", "sl_loi": 2, "muc_do": "Nhẹ" }}
       ]

    Hãy xử lý âm thanh cung cấp và trả về JSON kết quả.
    """
    
    try:
        # Gọi API với audio bytes trực tiếp
        # Gemini Python SDK hỗ trợ dictionary cho các parts multimodality: {'mime_type': '...', 'data': ...}
        response = model.generate_content([
            prompt, 
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        
        # --- COST CALCULATION (Estimate) ---
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count
        comp_tokens = usage.candidates_token_count
        total_tokens = usage.total_token_count
        
        # Pricing Gemini 2.5 Flash (Updated 2026-01-30)
        # Input (Text/Image/Video): $0.10 / 1M
        # Input (Audio): $1.00 / 1M (Per user provided table)
        # Output: $0.40 / 1M
        
        # Note: Since this is Voice Input, prompt is dominated by Audio tokens.
        # We use the Audio rate ($1.00/1M) for the entire prompt to be safe.
        price_input = 1.00
        price_output = 0.40
        
        cost_usd = (prompt_tokens / 1_000_000 * price_input) + (comp_tokens / 1_000_000 * price_output)
        cost_vnd = cost_usd * 25400
        
        usage_info = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": comp_tokens,
            "total_tokens": total_tokens,
            "cost_vnd": cost_vnd
        }

        results = extract_json(response.text)
        return results, usage_info
        
    except Exception as e:
        # Log error
        print(f"Gemini API Error: {e}")
        return [], None
