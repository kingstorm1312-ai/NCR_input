import os
import streamlit as st
import pandas as pd
from datetime import datetime
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import tempfile
import requests
import shutil

def get_temp_file_path(filename):
    return os.path.join(tempfile.gettempdir(), filename)

def format_date_vn(date_str):
    if not date_str:
        return ""
    try:
        # Hỗ trợ nhiều định dạng
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
            try:
                dt = datetime.strptime(str(date_str), fmt)
                return dt.strftime("%d/%m/%Y")
            except:
                continue
        return str(date_str)
    except:
        return str(date_str)

def download_image(url):
    """Tải ảnh từ URL về file tạm để chèn vào Word"""
    try:
        if not url: return None
        res = requests.get(url, stream=True)
        if res.status_code == 200:
            tmp_name = f"img_{int(datetime.now().timestamp())}_{os.urandom(4).hex()}.jpg"
            tmp_path = get_temp_file_path(tmp_name)
            with open(tmp_path, 'wb') as f:
                shutil.copyfileobj(res.raw, f)
            return tmp_path
        return None
    except Exception as e:
        print(f"Lỗi tải ảnh: {e}")
        return None

def generate_ncr_pdf(template_path, ticket_data, df_errors, output_filename_prefix):
    """
    Điền dữ liệu vào template Word và xuất ra PDF.
    
    Args:
        template_path (str): Đường dẫn đến file mẫu .docx
        ticket_data (dict/Series): Thông tin chung của phiếu (1 dòng)
        df_errors (DataFrame): Bảng chi tiết các lỗi của phiếu này
        output_filename_prefix (str): Prefix cho tên file output (vd: NCR_FI-01-001)
        
    Returns:
        str: Đường dẫn file PDF kết quả (hoặc None nếu lỗi)
        str: Đường dẫn file Docx kết quả
    """
    try:
        doc = DocxTemplate(template_path)
        
        # 1. CHUẨN BỊ DỮ LIỆU MAPPING (Bridge)
        # Dictionary này đóng vai trò cầu nối giữa Header Sheet và PlaceHolder Word
        
        # FIX: Khởi tạo context bằng dữ liệu gốc (ticket_data) trước
        # Để đảm bảo mọi key trong ticket_data đều có mặt trong template (vd: ten_sp, so_luong_lo_hang...)
        context = ticket_data.copy() if isinstance(ticket_data, dict) else ticket_data.to_dict()
        
        # Sau đó Override/Bổ sung các key chuẩn hóa nếu cần
        context.update({
            # --- HEADER INFO ---
            'so_phieu': ticket_data.get('so_phieu', ''),
            'ngay_lap': format_date_vn(ticket_data.get('ngay_lap', '')),
            'bo_phan': ticket_data.get('bo_phan', ''),
            'nguoi_lap': ticket_data.get('nguoi_lap_phieu', ''),
            
            # --- PRODUCT INFO ---
            'ten_tui': ticket_data.get('ten_sp', ''),      # Map ten_sp -> ten_tui
            'ma_vat_tu': ticket_data.get('ma_vat_tu', ''),
            'hop_dong': ticket_data.get('hop_dong', ''),
            'sl_lo_hang': ticket_data.get('sl_lo_hang', ''),
            'sl_kiem': ticket_data.get('sl_kiem', ''),
            
            # --- UNIT / SOURCE ---
            # Ưu tiên lấy nguon_goc, nếu không có thì lấy noi_gay_loi hoặc bo_phan
            'noi_may': ticket_data.get('nguon_goc') or ticket_data.get('noi_gay_loi') or ticket_data.get('bo_phan', ''),
            'nguon_goc': ticket_data.get('nguon_goc', ''),
            
            # --- SUMMARY ---
            'tong_loi': ticket_data.get('sl_loi', 0),
            'cac_loi': ticket_data.get('ten_loi', ''),
            
            # --- PHÊ DUYỆT / GIẢI PHÁP ---
            'nguyen_nhan': ticket_data.get('mo_ta_loi', ''), # Tạm map mô tả lỗi vào nguyên nhân
            'bien_phap_khac_phuc': ticket_data.get('bien_phap_truong_bp', ''),
            'y_kien_qc': ticket_data.get('huong_giai_quyet', ''),
            'y_kien_gd': ticket_data.get('huong_xu_ly_gd', ''),
            
            # Kết luận: Nếu trạng thái là Hoàn thành -> Đạt ? (Logic này tùy biến)
            'ket_luan': "ĐẠT" if str(ticket_data.get('trang_thai', '')).lower() == 'hoan_thanh' else "CHƯA KẾT LUẬN"
        })
        
        # 2. CHUẨN BỊ BẢNG TABLE (Dynamic Rows)
        # Cần check xem trong template dùng tên biến gì cho vòng lặp
        # Giả sử trong template dùng: {%tr for item in list_errors %} ...
        
        list_errors = []
        if not df_errors.empty:
            for idx, row in df_errors.reset_index(drop=True).iterrows():
                err_item = {
                    'stt': idx + 1,
                    'ten_loi': row.get('ten_loi', ''),
                    'vi_tri': row.get('vi_tri_loi', ''),
                    'sl': row.get('sl_loi', 0),
                    'dvt': row.get('don_vi_tinh', ''),
                    'muc_do': row.get('muc_do', ''),
                    'ghi_chu': '' # Thêm nếu cần
                }
                list_errors.append(err_item)
        
        context['danh_sach_loi'] = list_errors # Key này phải khớp với vòng lặp trong Word
        
        # --- RENDER TABLE LỖI ---
        # Tự động tính toán Field Summary nếu chưa có
        if list_errors:
            context['tong_loi_chi_tiet'] = sum([float(e['sl']) for e in list_errors if str(e['sl']).replace('.','',1).isdigit()])
        
        # 3. FILL TEMPLATE
        doc.render(context)
        
        # 4. SAVE TEMP DOCX
        tmp_dir = tempfile.gettempdir()
        docx_filename = f"{output_filename_prefix}_{int(datetime.now().timestamp())}.docx"
        docx_path = os.path.join(tmp_dir, docx_filename)
        doc.save(docx_path)
        
        # 5. CONVERT TO PDF
        pdf_filename = f"{output_filename_prefix}_{int(datetime.now().timestamp())}.pdf"
        pdf_path = os.path.join(tmp_dir, pdf_filename)
        
        try:
            # Lưu ý: Hàm này yêu cầu MS Word cài trên máy
            from docx2pdf import convert
            convert(docx_path, pdf_path)
            return pdf_path, docx_path
        except Exception as e:
            # Nếu lỗi convert (vd server Linux), trả về None cho PDF nhưng vẫn trả DOCX
            print(f"Không thể convert sang PDF: {e}")
            return None, docx_path
            
    except Exception as e:
        print(f"Lỗi tạo file báo cáo: {e}")
        return None, None
