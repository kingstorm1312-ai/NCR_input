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
    get_contract_group_ranking
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
            get_contract_group_ranking
        ]
        
        # 2. Configure Model with Tools
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=tools_list,
            system_instruction="""
            Bạn là Trợ lý Phân tích Dữ liệu (AI Data Analyst) của nhà máy sản xuất bao bì.
            Nhiệm vụ: Trả lời câu hỏi của Giám đốc về dữ liệu chất lượng (NCR) dựa trên các công cụ (Tools) được cung cấp.
            
            ⚠️ ĐỊNH NGHĨA QUAN TRỌNG (DOMAIN KNOWLEDGE):
            1. **Hợp đồng (Contract)**: Thường là các mã bắt đầu bằng chữ cái như **ADI, ABE, PO, T01, T02**... (Ví dụ: ADI-123, ABE-456).
            2. **Bộ phận / Khâu (Department)**: Là các công đoạn sản xuất, bao gồm: **FI, PE, IN (In ấn), GHÉP, CẮT, TRÁNG, CUỘN (Chia cuộn), SEAL, LÀM TÚI (May),...**
               -> LƯU Ý: **"FI" là tên bộ phận**, KHÔNG PHẢI là hợp đồng.
            3. **Lỗi (Defect)**: Là các vấn đề chất lượng như: Bong keo, Lem màu, Hở seal, Sai kích thước...

            QUY TẮC TRẢ LỜI:
            1. **Phân biệt rõ đối tượng**: Nếu User hỏi "Hợp đồng nào lỗi nhiều nhất?", hãy lọc theo Contract. Nếu hỏi "Khâu nào lỗi nhiều nhất?", hãy lọc theo Department.
            2. **Luôn dùng Tool**: Luôn ưu tiên dùng Tool `filter_data` hoăc `get_department_ranking` để lấy số liệu thực tế. KHÔNG được bịa số liệu.
            3. **Xử lý mơ hồ**: Nếu câu hỏi mơ hồ (VD: "Tình hình sao rồi?"), hãy mặc định lấy dữ liệu THÁNG HIỆN TẠI và báo cáo 3 chỉ số: Tổng lỗi, Bộ phận nhiều lỗi nhất, Top lỗi.
            4. **Drill-down**: Nếu User hỏi về một Phiếu cụ thể (VD: "phiếu lỗi nặng nhất", "phiếu FI-01"), hãy dùng Tool `get_ncr_details`.
            5. **Biểu đồ (Chart)**: Nếu User yêu cầu vẽ biểu đồ hoặc dữ liệu thích hợp để vẽ (VD: so sánh, xu hướng, ranking), hãy thêm block JSON sau vào cuối câu trả lời:
               
               [[CHART:
               {
                 "type": "bar" | "line" | "pie",
                 "title": "Tên biểu đồ",
                 "labels": ["Nhãn 1", "Nhãn 2", ...],
                 "values": [10, 20, ...]
               }
               ]]
               
               LƯU Ý: Chỉ output block này khi cần thiết. Dữ liệu trong block phải khớp với text.

            6. **Văn phong**: Trả lời ngắn gọn, súc tích, chuyên nghiệp bằng Tiếng Việt.
            """
        )
        
        # 3. Create Chat Session with History
        # Transform streamlits chat history to gemini format if needed, 
        # but for simplicity we can just start a chat and send the message history + new msg.
        # Actually proper way is initializing chat with history.
        
        chat = model.start_chat(history=chat_history, enable_automatic_function_calling=True)
        
        # 4. Send Message (Auto-handles tool calls loop)
        response = chat.send_message(user_input)
        
        return response.text
            
    except Exception as e:
        return f"❌ Lỗi Agent: {str(e)}"
