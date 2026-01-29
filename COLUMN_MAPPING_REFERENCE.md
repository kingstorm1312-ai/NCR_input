# CRITICAL COLUMN MAPPING REFERENCE

# This file documents the mapping between Google Sheet column names and internal code column names

# ALWAYS use the "Internal Name" when writing code that accesses DataFrame columns

## Mapping Table (Internal Name -> Google Sheet Name)

| Internal Name (Use in Code) | Google Sheet Name | Description |
|----------------------------|-------------------|-------------|
| `so_phieu`                 | `so_phieu_ncr`    | NCR Ticket Number |
| `sl_loi`                   | `so_luong_loi`    | Defect Quantity |
| `sl_kiem`                  | `so_luong_kiem`   | Inspected Quantity |
| `md_loi`                   | `muc_do`          | Severity Level |
| `sl_lo_hang`               | `so_luong_lo_hang`| Batch Quantity |

## Same in Both (No Mapping Needed)

- `ngay_lap`
- `hop_dong`
- `ma_vat_tu`
- `ten_sp`
- `ten_loi`
- `vi_tri_loi`
- `nguon_goc`
- `phan_loai`
- `mo_ta_loi`
- `nguoi_lap_phieu`
- `noi_gay_loi`
- `trang_thai`
- `thoi_gian_cap_nhat`
- `nguoi_duyet_1` -> `duyet_truong_ca` (actually mapped, but target different)
- `nguoi_duyet_2` -> `duyet_truong_bp`
- `nguoi_duyet_3` -> `duyet_qc_manager`
- `nguoi_duyet_4` -> `duyet_giam_doc`
- `nguoi_duyet_5` -> `duyet_bgd_tan_phu`
- `bien_phap_truong_bp`
- `huong_giai_quyet` -> `y_kien_qc`
- `huong_xu_ly_gd` -> `huong_xu_ly_giam_doc`
- `ly_do_tu_choi`
- `hinh_anh`
- `don_vi_tinh`
- `kp_status`
- `kp_assigned_by`
- `kp_assigned_to`
- `kp_message`
- `kp_deadline`
- `kp_response`
- `so_lan`
- `so_po`
- `khach_hang`
- `don_vi_kiem`
- `bo_phan`
- `bo_phan_full`
- `year`
- `month`
- `week`
- `date_obj`

## CRITICAL RULES FOR AI TOOLS DEVELOPMENT

1. ALWAYS use internal names (`sl_loi`, `sl_kiem`, `md_loi`) in ai_tools.py
2. System Prompt should reference internal names to avoid confusion
3. When documenting for users, can mention both names for clarity
