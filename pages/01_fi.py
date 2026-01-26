from core.auth import require_login
from core.form_engine import run_inspection_page
from depts.registry import get_dept

# Kiểm tra đăng nhập
require_login()

# Chạy engine với profile FI
run_inspection_page(get_dept("fi"))
