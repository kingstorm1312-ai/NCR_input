from core.auth import require_login
from core.form_engine import run_inspection_page
from depts.registry import get_dept

# Kiểm tra đăng nhập
require_login()

# Chạy engine với profile TP Đầu Vào
run_inspection_page(get_dept("tp_dau_vao"))