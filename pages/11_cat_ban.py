from core.form_engine import run_inspection_page
from depts.registry import get_dept

run_inspection_page(get_dept('cat_ban'))
