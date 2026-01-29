import pandas as pd
import json
from core.services.ai_tools import get_report_data

def investigate_high_rate(source_name="Hồng Toản"): # Search term
    try:
        df = get_report_data()
        
        # Log to file
        with open('debug_high_rate_output.txt', 'w', encoding='utf-8') as f:
            f.write(f"========================================\n")
            f.write(f"DEBUG REPORT FOR SOURCE: {source_name}\n")
            
            if 'nguon_goc' not in df.columns:
                 f.write("ERROR: Column 'nguon_goc' not found in DataFrame.\n")
                 return

            # Filter by source
            df_source = df[df['nguon_goc'].astype(str).str.contains(source_name, case=False, na=False)]
            row_count = len(df_source)
            f.write(f"Total rows found: {row_count}\n")
            
            if row_count == 0:
                f.write("No rows found. Checking available sources:\n")
                unique_sources = df['nguon_goc'].dropna().unique()
                for s in unique_sources:
                    f.write(f"- '{s}'\n")
                return

            unique_tickets = df_source['so_phieu'].unique()
            f.write(f"Unique tickets: {len(unique_tickets)}\n")
            f.flush()
            
            suspicious_tickets = []
            total_qty = 0
            total_insp = 0
            
            for ticket in unique_tickets:
                try:
                    ticket_df = df_source[df_source['so_phieu'] == ticket]
                    
                    # Calculate Defect Qty for this ticket (sum of sl_loi rows)
                    sl_loi = pd.to_numeric(ticket_df['sl_loi'], errors='coerce').fillna(0).sum()
                    
                    # Get Inspection Qty (max or first, assuming consistent per ticket)
                    sl_kiem_vals = pd.to_numeric(ticket_df['sl_kiem'], errors='coerce').fillna(0)
                    sl_kiem = sl_kiem_vals.max() 
                    
                    total_qty += sl_loi
                    total_insp += sl_kiem
                    
                    current_rate = (sl_loi/sl_kiem*100) if sl_kiem > 0 else 0
                    
                    if sl_loi > sl_kiem: # Critical: Defect > Insp
                        suspicious_tickets.append({
                            "ticket": ticket,
                            "sl_loi": int(sl_loi),
                            "sl_kiem": int(sl_kiem),
                            "rate": round(current_rate, 2)
                        })
                except Exception as e_inner:
                     f.write(f"Error processing ticket {ticket}: {str(e_inner)}\n")

            f.write(f"\n--- SUMMARY ---\n")
            f.write(f"Total Defect Qty (sl_loi): {int(total_qty)}\n")
            f.write(f"Total Insp Qty (sl_kiem): {int(total_insp)}\n")
            global_rate = (total_qty/total_insp*100) if total_insp > 0 else 0
            f.write(f"Calculated Rate: {global_rate:.2f}%\n")
            
            f.write(f"\n--- SUSPICIOUS TICKETS (Loi > Kiem) ---\n")
            if not suspicious_tickets:
                f.write("None found. Data seems consistent (sum sl_loi <= sl_kiem).\n")
            else:
                for t in suspicious_tickets:
                    f.write(f"Ticket {t['ticket']}: Lỗi={t['sl_loi']} / Kiểm={t['sl_kiem']} -> Rate={t['rate']}%\n")
            f.flush()
            print("Investigation complete. Check debug_high_rate_output.txt")

    except Exception as e:
        with open('debug_high_rate_output.txt', 'a', encoding='utf-8') as f:
            f.write(f"\nCRITICAL ERROR: {str(e)}\n")
        print(f"CRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    investigate_high_rate()
