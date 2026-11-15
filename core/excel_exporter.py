import os
from datetime import datetime, date
from typing import Optional, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from core.database import Database
from core.config import EXPORTS_DIR

class ExcelExporter:
    """Xuất báo cáo dữ liệu và lịch sử tăng trưởng kênh TikTok ra file Excel chuyên nghiệp"""

    def __init__(self, db: Database):
        self.db = db

    def export_growth_report(self, category_filter: Optional[str] = None, country_filter: Optional[str] = None, phone_code_filter: Optional[str] = None, filename: Optional[str] = None) -> str:
        if not filename:
            today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            cat_suffix = f"_{category_filter}" if category_filter else ""
            ctry_suffix = f"_{country_filter}" if country_filter else ""
            filename = f"TikTok_Growth_Report_{today_str}{cat_suffix}{ctry_suffix}.xlsx"

        filepath = os.path.join(EXPORTS_DIR, filename)

        wb = openpyxl.Workbook()
        ws_today = wb.active
        ws_today.title = "Báo Cáo Hôm Nay"

        channels = self.db.get_all_channels(
            category_filter=category_filter,
            country_filter=country_filter,
            phone_code_filter=phone_code_filter
        )
        self._build_today_summary_sheet(ws_today, channels)

        ws_history = wb.create_sheet(title="Lịch Sử Tăng Trưởng Chi Tiết")
        self._build_full_history_sheet(ws_history, channels)

        wb.save(filepath)
        return filepath

    def _build_today_summary_sheet(self, ws, channels: List[dict]):
        ws.views.sheetView[0].showGridLines = True

        title_font = Font(name="Calibri", size=16, bold=True, color="1E293B")
        ws.merge_cells("A1:Q1")
        title_cell = ws["A1"]
        title_cell.value = f"BÁO CÁO TĂNG TRƯỞNG KÊNH TIKTOK - NGÀY {date.today().strftime('%d/%m/%Y')}"
        title_cell.font = title_font
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 40

        ws.merge_cells("A2:Q2")
        sub_cell = ws["A2"]
        sub_cell.value = f"Thời gian xuất: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')} | Tổng số kênh: {len(channels)}"
        sub_cell.font = Font(name="Calibri", size=11, italic=True, color="64748B")
        sub_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        headers = [
            "STT", "Tên Kênh", "TikTok ID", "Quốc gia", "Mã ĐT", "Nhóm / Tag", "Trạng thái",
            "Followers", "Tăng Follow (+/-)", 
            "Tổng Tym", "Tăng Tym (+/-)", 
            "Tổng Video", "Tăng Video (+/-)",
            "V1 (Mới nhất)", "V2", "V3", "V4", "V5", "View TB (5 video)", "RPM", "Dash ($)", "Ghi chú"
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.row_dimensions[4].height = 30
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        pos_font = Font(name="Calibri", size=11, color="16A34A", bold=True)
        neg_font = Font(name="Calibri", size=11, color="DC2626", bold=True)
        normal_font = Font(name="Calibri", size=11, color="0F172A")
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        yellow_fill = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
        yellow_font = Font(name="Calibri", size=11, bold=True, color="854D0E")

        row_start = 5
        for idx, ch in enumerate(channels, 1):
            curr_row = row_start + idx - 1
            ws.row_dimensions[curr_row].height = 22

            d_flw = ch.get("delta_followers") or 0
            d_hrt = ch.get("delta_hearts") or 0
            d_vid = ch.get("delta_videos") or 0

            d_flw_display = f"+{d_flw:,}" if d_flw > 0 else (f"{d_flw:,}" if d_flw < 0 else "0")
            d_hrt_display = f"+{d_hrt:,}" if d_hrt > 0 else (f"{d_hrt:,}" if d_hrt < 0 else "0")
            d_vid_display = f"+{d_vid:,}" if d_vid > 0 else (f"{d_vid:,}" if d_vid < 0 else "0")

            values = [
                idx,
                ch.get("nickname") or ch.get("username"),
                f"@{ch.get('username')}",
                ch.get("country", "") or "--",
                str(ch.get("phone_code", "") or "--"),
                ch.get("category", "Mặc định"),
                ch.get("status", "Hoạt động"),
                ch.get("followers") or 0,
                d_flw_display,
                ch.get("hearts") or 0,
                d_hrt_display,
                ch.get("video_count") or 0,
                d_vid_display,
                ch.get("v1_view") or 0,
                ch.get("v2_view") or 0,
                ch.get("v3_view") or 0,
                ch.get("v4_view") or 0,
                ch.get("v5_view") or 0,
                round(ch.get("avg_views") or 0.0, 1),
                float(ch.get("rpm") or 0.0),
                float(ch.get("dash") or 0.0),
                ch.get("note", "") or ""
            ]

            is_zebra = (idx % 2 == 0)

            for col_idx, val in enumerate(values, 1):
                cell = ws.cell(row=curr_row, column=col_idx, value=val)
                cell.border = thin_border
                cell.font = normal_font

                if is_zebra:
                    cell.fill = zebra_fill

                if col_idx in [1, 4, 5, 6, 7]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in [8, 10, 12, 14, 15, 16, 17, 18, 19]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, (int, float)):
                        cell.number_format = '#,##0' if col_idx != 19 else '#,##0.0'
                        # Tô màu vàng cho các video V1-V5 có views >= 10,000
                        if col_idx in [14, 15, 16, 17, 18] and val >= 10000:
                            cell.fill = yellow_fill
                            cell.font = yellow_font
                elif col_idx in [9, 11, 13]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if "+" in str(val):
                        cell.font = pos_font
                    elif "-" in str(val):
                        cell.font = neg_font

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    def _build_full_history_sheet(self, ws, channels: List[dict]):
        ws.views.sheetView[0].showGridLines = True

        headers = [
            "Ngày Quét", "TikTok ID", "Tên Kênh", "Quốc gia", "Mã ĐT", "Nhóm / Tag",
            "Followers", "Tăng Follow", 
            "Tổng Tym", "Tăng Tym", 
            "Tổng Video", "Tăng Video",
            "V1 View", "V2 View", "V3 View", "V4 View", "V5 View", "View TB (5 video)", "RPM", "Dash ($)", "Ghi chú"
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.row_dimensions[1].height = 28
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        pos_font = Font(name="Calibri", size=11, color="16A34A", bold=True)
        neg_font = Font(name="Calibri", size=11, color="DC2626", bold=True)
        normal_font = Font(name="Calibri", size=11, color="0F172A")
        yellow_fill = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
        yellow_font = Font(name="Calibri", size=11, bold=True, color="854D0E")

        curr_row = 2
        for ch in channels:
            history = self.db.get_channel_history(ch['id'])
            for snap in history:
                ws.row_dimensions[curr_row].height = 20
                d_flw = snap.get("delta_followers") or 0
                d_hrt = snap.get("delta_hearts") or 0
                d_vid = snap.get("delta_videos") or 0

                d_flw_display = f"+{d_flw:,}" if d_flw > 0 else (f"{d_flw:,}" if d_flw < 0 else "0")
                d_hrt_display = f"+{d_hrt:,}" if d_hrt > 0 else (f"{d_hrt:,}" if d_hrt < 0 else "0")
                d_vid_display = f"+{d_vid:,}" if d_vid > 0 else (f"{d_vid:,}" if d_vid < 0 else "0")

                values = [
                    snap.get("scan_date"),
                    f"@{ch.get('username')}",
                    ch.get("nickname") or ch.get("username"),
                    ch.get("country", "") or "--",
                    str(ch.get("phone_code", "") or "--"),
                    ch.get("category", "Mặc định"),
                    snap.get("follower_count") or 0,
                    d_flw_display,
                    snap.get("heart_count") or 0,
                    d_hrt_display,
                    snap.get("video_count") or 0,
                    d_vid_display,
                    snap.get("v1_view") or 0,
                    snap.get("v2_view") or 0,
                    snap.get("v3_view") or 0,
                    snap.get("v4_view") or 0,
                    snap.get("v5_view") or 0,
                    round(snap.get("avg_views") or 0.0, 1),
                    float(snap.get("rpm") or 0.0),
                    float(snap.get("dash") or 0.0),
                    ch.get("note", "") or ""
                ]

                for col_idx, val in enumerate(values, 1):
                    cell = ws.cell(row=curr_row, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.font = normal_font

                    if col_idx in [1, 4, 5, 6]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif col_idx in [7, 9, 11, 13, 14, 15, 16, 17, 18]:
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if isinstance(val, (int, float)):
                            cell.number_format = '#,##0' if col_idx != 18 else '#,##0.0'
                            # Tô màu vàng cho các video V1-V5 có views >= 10,000
                            if col_idx in [13, 14, 15, 16, 17] and val >= 10000:
                                cell.fill = yellow_fill
                                cell.font = yellow_font
                    elif col_idx in [8, 10, 12]:
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if "+" in str(val):
                            cell.font = pos_font
                        elif "-" in str(val):
                            cell.font = neg_font

                curr_row += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
