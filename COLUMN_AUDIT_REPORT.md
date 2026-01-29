# COLUMN NAME AUDIT REPORT

## Summary

Đã kiểm tra TẤT CẢ các tham chiếu column trong AI Tools để đảm bảo sử dụng đúng **Internal Column Names** (sau khi COLUMN_MAPPING áp dụng).

## Files Audited

1. `core/services/ai_tools.py` - 313 lines
2. `core/services/ai_service.py` - 121 lines

## Critical Mapping (Internal -> Sheet)

| Internal Name | Google Sheet Name |
|---------------|-------------------|
| `sl_loi`      | `so_luong_loi`    |
| `sl_kiem`     | `so_luong_kiem`   |
| `md_loi`      | `muc_do`          |
| `so_phieu`    | `so_phieu_ncr`    |
| `sl_lo_hang`  | `so_luong_lo_hang`|

## Issues Found & Fixed

### 1. ❌ `ai_tools.py` - Line 155 (FIXED)

**Function:** `get_ncr_details`
**Issue:** Sử dụng `'muc_do'` (sheet name) thay vì `'md_loi'` (internal name)

```python
# Before:
errors = ticket[['ten_loi', 'sl_loi', 'muc_do', 'vi_tri_loi']].to_dict('records')

# After:
errors = ticket[['ten_loi', 'sl_loi', 'md_loi', 'vi_tri_loi']].to_dict('records')
```

### 2. ❌ `ai_tools.py` - Line 275-287 (FIXED EARLIER)

**Function:** `general_data_query`
**Issue:** Sử dụng `'so_luong_loi'` và `'so_luong_kiem'` (sheet names)

```python
# Fixed to:
if 'sl_loi' in df.columns:
    total_defect_qty = pd.to_numeric(df['sl_loi'], errors='coerce').fillna(0).sum()

if 'sl_kiem' in df.columns:
    total_inspected_qty = pd.to_numeric(df['sl_kiem'], errors='coerce').fillna(0).sum()
```

### 3. ✅ `ai_service.py` - System Prompt (UPDATED)

**Issue:** System Prompt không rõ ràng về internal vs sheet column names
**Fix:** Thêm section chú thích rõ ràng về các cột có mapping khác nhau.

## All Column References Verified ✓

### Correct Internal Names (After Audit)

- ✅ `so_phieu` (mapped from `so_phieu_ncr`)
- ✅ `sl_loi` (mapped from `so_luong_loi`)
- ✅ `sl_kiem` (mapped from `so_luong_kiem`)
- ✅ `md_loi` (mapped from `muc_do`)
- ✅ `hop_dong` (same in both)
- ✅ `ten_loi` (same in both)
- ✅ `vi_tri_loi` (same in both)
- ✅ `nguon_goc` (same in both)
- ✅ `bo_phan` / `bo_phan_full` (same in both)
- ✅ `year` / `month` / `week` (derived columns)
- ✅ `ngay_lap` (same in both)
- ✅ `nguoi_lap_phieu` (same in both)
- ✅ `kp_assigned_to` (same in both)

## Status: ✅ ALL CLEAR

Tất cả các column references trong AI Tools đã được audit và sử dụng đúng Internal Names.

## Documentation Created

- `COLUMN_MAPPING_REFERENCE.md` - Tài liệu tham khảo cho developers

## Recommendations

1. ✅ Luôn tham khảo `COLUMN_MAPPING_REFERENCE.md` khi thêm logic mới
2. ✅ Khi debug, nhớ rằng DataFrame columns sử dụng **Internal Names**, không phải Sheet Names
3. ✅ System Prompt đã được cập nhật để AI hiểu rõ về mapping này
