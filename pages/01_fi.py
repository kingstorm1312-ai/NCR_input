from core.form_engine import run_inspection_page
from depts.registry import get_dept

# Chạy engine với profile FI
run_inspection_page(get_dept("fi"))
