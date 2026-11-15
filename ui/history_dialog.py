import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import Database

class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem tùy chỉnh để sắp xếp theo giá trị số thực tế (Numeric Sorting)"""
    def __init__(self, text: str, num_val: float = 0.0):
        super().__init__(str(text))
        self.num_val = float(num_val) if num_val is not None else 0.0

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.num_val < other.num_val
        try:
            val_self = self.num_val
            txt_other = other.text().replace(',', '').replace('+', '').replace(' ', '').strip()
            return val_self < float(txt_other)
        except Exception:
            return super().__lt__(other)

class HistoryDialog(QDialog):
    """Hộp thoại hiển thị biểu đồ lịch sử tăng trưởng của 1 kênh theo từng ngày"""

    def __init__(self, channel: dict, db: Database, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.db = db
        nick = channel.get("nickname") or channel.get("username")
        self.setWindowTitle(f"📈 Lịch Sử Tăng Trưởng: {nick} (@{channel.get('username')})")
        self.resize(1000, 520)
        self.setModal(True)
        self._init_ui()
        self._load_history()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Info Card
        header_frame = QFrame()
        header_frame.setObjectName("kpiCard")
        h_layout = QHBoxLayout(header_frame)

        v_info = QVBoxLayout()
        nick = self.channel.get("nickname") or self.channel.get("username")
        lbl_name = QLabel(f"🌟 {nick}")
        lbl_name.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFFFFF;")
        v_info.addWidget(lbl_name)

        lbl_user = QLabel(f"ID: @{self.channel.get('username')} | Nhóm: {self.channel.get('category', 'Mặc định')}")
        lbl_user.setStyleSheet("color: #38BDF8; font-size: 12px;")
        v_info.addWidget(lbl_user)

        h_layout.addLayout(v_info, 1)

        # Current Stats
        flw = self.channel.get("followers") or 0
        hrt = self.channel.get("hearts") or 0
        vid = self.channel.get("video_count") or 0

        v_stats = QVBoxLayout()
        lbl_stat = QLabel(f"👥 Followers: {flw:,}   |   ❤️ Tym: {hrt:,}   |   🎬 Videos: {vid:,}")
        lbl_stat.setStyleSheet("font-weight: 700; color: #FBBF24; font-size: 13px;")
        v_stats.addWidget(lbl_stat)
        h_layout.addLayout(v_stats)

        layout.addWidget(header_frame)

        # History Table
        self.table = QTableWidget()
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels([
            "Ngày Quét", "Followers", "Tăng Follow (+/-)", 
            "Tổng Tym", "Tăng Tym (+/-)", 
            "Tổng Video", "Tăng Video",
            "V1 View", "V2 View", "V3 View", "V4 View", "V5 View", "View TB (5 video)", "RPM", "Dash"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)

        # Close button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _load_history(self):
        records = self.db.get_channel_history(self.channel['id'])
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))

        for row_idx, r in enumerate(reversed(records)):
            # Ngày
            self._set_cell(row_idx, 0, r.get("scan_date"), align=Qt.AlignmentFlag.AlignCenter, bold=True)

            # Follower
            flw = r.get("follower_count") or 0
            self._set_cell(row_idx, 1, f"{flw:,}", align=Qt.AlignmentFlag.AlignRight, num_val=flw)

            # Tăng Follow
            d_flw = r.get("delta_followers") or 0
            d_flw_str = f"+{d_flw:,}" if d_flw > 0 else (f"{d_flw:,}" if d_flw < 0 else "0")
            d_flw_col = QColor("#10B981") if d_flw > 0 else (QColor("#EF4444") if d_flw < 0 else None)
            self._set_cell(row_idx, 2, d_flw_str, align=Qt.AlignmentFlag.AlignRight, color=d_flw_col, bold=True, num_val=d_flw)

            # Tym
            hrt = r.get("heart_count") or 0
            self._set_cell(row_idx, 3, f"{hrt:,}", align=Qt.AlignmentFlag.AlignRight, num_val=hrt)

            # Tăng Tym
            d_hrt = r.get("delta_hearts") or 0
            d_hrt_str = f"+{d_hrt:,}" if d_hrt > 0 else (f"{d_hrt:,}" if d_hrt < 0 else "0")
            d_hrt_col = QColor("#10B981") if d_hrt > 0 else (QColor("#EF4444") if d_hrt < 0 else None)
            self._set_cell(row_idx, 4, d_hrt_str, align=Qt.AlignmentFlag.AlignRight, color=d_hrt_col, bold=True, num_val=d_hrt)

            # Video
            vid = r.get("video_count") or 0
            self._set_cell(row_idx, 5, f"{vid:,}", align=Qt.AlignmentFlag.AlignRight, num_val=vid)

            # Tăng Video
            d_vid = r.get("delta_videos") or 0
            d_vid_str = f"+{d_vid:,}" if d_vid > 0 else (f"{d_vid:,}" if d_vid < 0 else "0")
            self._set_cell(row_idx, 6, d_vid_str, align=Qt.AlignmentFlag.AlignRight, num_val=d_vid)

            # V1 - V5 Views (Tô màu vàng nổi bật cho video >= 10,000 views)
            v_views = [
                r.get("v1_view") or 0,
                r.get("v2_view") or 0,
                r.get("v3_view") or 0,
                r.get("v4_view") or 0,
                r.get("v5_view") or 0
            ]
            for col_offset, v_val in enumerate(v_views):
                col_idx = 7 + col_offset
                if v_val >= 10000:
                    self._set_cell(
                        row_idx, col_idx, f"{v_val:,}",
                        align=Qt.AlignmentFlag.AlignRight,
                        color=QColor("#FEF08A"),
                        bg_color=QColor(234, 179, 8, 85),
                        bold=True,
                        num_val=v_val
                    )
                else:
                    self._set_cell(row_idx, col_idx, f"{v_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=v_val)

            # View TB
            avg_v = r.get("avg_views") or 0.0
            self._set_cell(row_idx, 12, f"{avg_v:,.1f}", align=Qt.AlignmentFlag.AlignRight, bold=True, color=QColor("#FBBF24"), num_val=avg_v)

            # RPM theo ngày
            rpm_v = float(r.get("rpm") or 0.0)
            rpm_str = "0" if not rpm_v else (f"{int(rpm_v):,}" if rpm_v == int(rpm_v) else f"{rpm_v:,.2f}".rstrip("0").rstrip("."))
            self._set_cell(
                row_idx, 13, rpm_str,
                align=Qt.AlignmentFlag.AlignRight,
                bold=(rpm_v > 0),
                color=QColor("#34D399") if rpm_v > 0 else QColor("#94A3B8"),
                num_val=rpm_v
            )

            # Dash ($) theo ngày
            dash_v = float(r.get("dash") or 0.0)
            dash_str = "$0" if not dash_v else (f"${int(dash_v):,}" if dash_v == int(dash_v) else f"${dash_v:,.2f}")
            self._set_cell(
                row_idx, 14, dash_str,
                align=Qt.AlignmentFlag.AlignRight,
                bold=(dash_v > 0),
                color=QColor("#38BDF8") if dash_v > 0 else QColor("#94A3B8"),
                num_val=dash_v
            )

        self.table.setSortingEnabled(True)

    def _set_cell(self, row: int, col: int, text: str, align=Qt.AlignmentFlag.AlignLeft, color=None, bold=False, bg_color=None, num_val=None):
        if num_val is not None:
            item = NumericTableWidgetItem(str(text), num_val)
        else:
            item = QTableWidgetItem(str(text))
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(color)
        if bg_color:
            item.setBackground(bg_color)
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        self.table.setItem(row, col, item)
