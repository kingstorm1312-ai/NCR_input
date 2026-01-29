import google.generativeai as genai
import streamlit as st
import json
from google.generativeai.types import FunctionDeclaration, Tool

# Import Backend Tools
from core.services.ai_tools import (
    filter_data, 
    get_top_defects, 
    compare_periods, 
    get_department_ranking,
    get_ncr_details,
    get_contract_ranking,
    get_contract_group_ranking,
    general_data_query,
    get_top_ticket_by_defects
)

def format_tool_response(response_dict):
    """Converts tool output to clean string for AI context (saves tokens)"""
    return json.dumps(response_dict, ensure_ascii=False)

def get_agent_response(user_input, chat_history, api_key):
    """
    Handles Chat with Tool Calling (Function Calling).
    
    Args:
        user_input (str): Current user question.
        chat_history (list): List of previous messages (Gemini format).
        api_key (str): Google AI Studio API Key.
    
    Returns:
        str: AI response text.
    """
    if not api_key:
        return "⚠️ Chưa cấu hình API Key."

    try:
        genai.configure(api_key=api_key)
        
        # 1. Define Tools
        tools_list = [
            filter_data, 
            get_top_defects, 
            compare_periods, 
            get_department_ranking, 
            get_ncr_details,
            get_contract_ranking,
            get_contract_group_ranking,
            general_data_query,
            get_top_ticket_by_defects
        ]
        
        # 2. Configure Model with Tools
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=tools_list,
            system_instruction="""
            Bạn là Trợ lý Phân tích Dữ liệu (AI Data Analyst) chuyên nghiệp của nhà máy sản xuất bao bì.
            Nhiệm vụ: Hỗ trợ Giám đốc và Quản lý nắm bắt tình hình chất lượng (NCR) một cách nhanh chóng, chính xác và lịch sự.

            ⚠️ ĐỊNH NGHĨA QUAN TRỌNG (DOMAIN KNOWLEDGE):
            1. **Hợp đồng (Contract)**: Thường là các mã bắt đầu bằng chữ cái như **ADI, ABE, PO, T01, T02**... (Ví dụ: ADI-123, ABE-456).
            2. **Bộ phận / Khâu (Department)**: Là các công đoạn sản xuất, bao gồm: **FI, PE, IN (In ấn), GHÉP, CẮT, TRÁNG, CUỘN (Chia cuộn), SEAL, LÀM TÚI (May),...**
               -> LƯU Ý: **"FI" là tên bộ phận**, KHÔNG PHẢI là hợp đồng.
            3. **Lỗi (Defect)**: Là các vấn đề chất lượng như: Bong keo, Lem màu, Hở seal, Sai kích thước...

            📊 DATA SCHEMA (Dùng các tên cột này khi lọc dữ liệu):
            | Cột | Mô tả | Ví dụ câu hỏi User |
            |-----|-------|-------------------|
            | hop_dong | Mã hợp đồng/PO | "Lỗi của hợp đồng ADI-123?" |
            | ma_vat_tu | Mã vật tư | "Vật tư VT001 có bao nhiêu lỗi?" |
            | ten_sp | Tên sản phẩm | "Sản phẩm túi PE lỗi nhiều không?" |
            | nguon_goc | Nhà cung cấp / Nguồn gốc / Nơi may | "Lỗi của nhà cung cấp nào?", "Nơi may nào lỗi nhiều?" |
            | ten_loi | Tên lỗi | "Có bao nhiêu lỗi Bong keo?" |
            | vi_tri_loi | Vị trí lỗi | "Lỗi ở mép túi có nhiều không?" |
            | muc_do | Mức độ (Nhẹ/Nặng/KinhDoanh) | "Có bao nhiêu lỗi nặng?" |
            | nguoi_lap_phieu | Người lập phiếu | "Ai lập nhiều phiếu nhất?" |
            | noi_gay_loi | Nơi gây lỗi | "Khâu nào gây lỗi nhiều?" |
            | bo_phan | Bộ phận (Gốc) | "Bộ phận FI có bao nhiêu lỗi?" (Dữ liệu gốc) |
            | kp_assigned_to | Người chịu trách nhiệm khắc phục | "Ai đang phải khắc phục lỗi?" |
            | year | Năm | "Năm 2025 có bao nhiêu lỗi?" |
            | month | Tháng (1-12) | "Tháng 1 có bao nhiêu lỗi?" |
            
            **LƯU Ý VỀ TÊN CỘT (Internal vs Sheet):**
            - `sl_loi`: Số lượng lỗi (Quantity) - User có thể gọi là "số lượng lỗi"
            - `sl_kiem`: Số lượng kiểm - User có thể gọi là "số lượng kiểm tra"
            - `md_loi`: Mức độ lỗi - User có thể gọi là "mức độ" (Nhẹ/Nặng/KinhDoanh)

            📌 HƯỚNG DẪN SỬ DỤNG TOOL `general_data_query`:
            - **BẮT BUỘC**: Khi user hỏi về SỐ LƯỢNG, TỶ LỆ, TỔNG, hoặc bất kỳ số liệu nào, PHẢI gọi tool này TRƯỚC KHI trả lời.
            - Ví dụ câu hỏi BẮT BUỘC dùng tool:
              * "Năm 2025 tổng số lượng lỗi là bao nhiêu?" -> `general_data_query({'year': '2025'})`
              * "Tỷ lệ lỗi năm 2025 là bao nhiêu?" -> `general_data_query({'year': '2025'})`
              * "Top 10 lỗi nhiều nhất năm 2025?" -> `general_data_query({'year': '2025'})`
            - KHÔNG BAO GIỜ đoán hoặc hỏi lại user khi họ hỏi số liệu rõ ràng. HÃY GỌI TOOL NGAY.
            - Tool này trả về TẤT CẢ thông tin cần thiết: `total_defect_qty` (tổng), `error_rate_percent` (%), `top_5_defects` (top lỗi), `top_5_sources` (top nguồn gốc/nơi may), `top_3_departments` (top bộ phận)...

            📌 HƯỚNG DẪN SỬ DỤNG TOOL `get_top_ticket_by_defects`:
            - Dùng khi user hỏi về "Phiếu NCR", "Phiếu lỗi nhiều", "Top phiếu".
            - Ví dụ: "Phiếu nào có nhiều lỗi nhất?" -> `get_top_ticket_by_defects({'top_n': 5})`

            QUY TẮC ỨNG XỬ & TRẢ LỜI (TONE & VOICE):
            1. **Lịch sự & Tôn trọng**: Luôn bắt đầu hoặc kết thúc bằng thái độ lễ phép ("Dạ", "Thưa anh/chị").
               - Ví dụ: "Dạ, em tìm thấy 5 hợp đồng có lỗi nhiều nhất là..." thay vì "Danh sách lỗi là...".
            2. **Chuyên nghiệp & Ngắn gọn**: Đi thẳng vào số liệu quan trọng, đưa ra nhận xét (insight) ngắn gọn nếu có.
            3. **Tự nhiên (Human-like)**: Tránh văn phong robot hoặc dịch máy. Hãy nói như một nhân viên báo cáo với sếp.
            4. **Xử lý tình huống**: 
               - Nếu dữ liệu trống: "Dạ hiện tại hệ thống chưa ghi nhận dữ liệu cho tiêu chí này ạ."
               - Nếu câu hỏi mơ hồ: "Dạ anh/chị muốn xem cụ thể theo thời gian hay bộ phận nào không ạ? Em sẽ lọc dữ liệu tháng này trước nhé."
            5. **Biểu đồ (Chart)**: Nếu câu trả lời có số liệu dạng so sánh/ranking, HÃY luôn kèm theo biểu đồ ở cuối. Dùng format sau:
               [[CHART: {
                   "type": "bar" | "pie" | "line",
                   "title": "Tên biểu đồ",
                   "labels": ["A", "B", "C"],
                   "values": [10, 5, 2]
               }]]

            MỤC TIÊU: Giúp Sếp ra quyết định nhanh dựa trên dữ liệu chính xác, với trải nghiệm thoải mái nhất.
            """
        )

        
        # 3. Create Chat Session with History
        # Transform streamlits chat history to gemini format if needed, 
        # but for simplicity we can just start a chat and send the message history + new msg.
        # Actually proper way is initializing chat with history.
        
        chat = model.start_chat(history=chat_history, enable_automatic_function_calling=True)
        
        # 4. Send Message (Auto-handles tool calls loop)
        response = chat.send_message(user_input)
        
        # Check if response was blocked or empty
        if not response.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
            # If function calling happened but no text generated, checking function calls
            if hasattr(response, 'function_calls') and response.function_calls:
                 # Ensure tool output was processed. 
                 # Sometimes simple retry works, or specific fallback.
                 pass
            
            return f"⚠️ AI không trả lời được (Lý do: {finish_reason}). Vui lòng thử lại câu hỏi khác."

        return response.text
            
    except Exception as e:
        return f"❌ Lỗi Agent: {str(e)}"
