import os
import sys
import webbrowser
import subprocess
from datetime import datetime, date
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
    QProgressBar, QMessageBox, QMenu, QInputDialog, QFrame, QCheckBox,
    QSpinBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.database import Database
from core.scanner import ScanWorker
from core.excel_exporter import ExcelExporter
from core.config import load_config, save_config, EXPORTS_DIR
from core.scheduler import register_windows_task, remove_windows_task, is_windows_task_registered
from ui.add_channel_dialog import AddChannelDialog
from ui.history_dialog import HistoryDialog
from ui.settings_dialog import SettingsDialog
from ui.update_dialog import UpdateDialog
from core.updater import get_local_version_info
from ui.styles import DARK_THEME_QSS

COUNTRY_OPTIONS = ["--", "Mỹ", "Anh", "Pháp", "Đức", "Nhật", "Hàn", "Mexico"]
PHONE_OPTIONS = ["--"] + [str(i) for i in range(1, 101)]
CATEGORY_OPTIONS = ["BKT", "TKT NT", "TKT BM", "NUÔI", "OUT", "Mặc định"]

CATEGORY_STYLES = {
    "BKT": "background-color: #065F46; color: #FFFFFF; font-weight: 800; border: 1px solid #10B981;",
    "TKT NT": "background-color: #BAE6FD; color: #0369A1; font-weight: 800; border: 1px solid #38BDF8;",
    "TKT BM": "background-color: #FFE4E6; color: #BE123C; font-weight: 800; border: 1px solid #F43F5E;",
    "NUÔI": "background-color: #E2E8F0; color: #1E293B; font-weight: 800; border: 1px solid #94A3B8;",
    "OUT": "background-color: #F3E8FF; color: #6B21A8; font-weight: 800; border: 1px solid #A855F7;",
    "Mặc định": "background-color: #1E293B; color: #94A3B8; border: 1px solid #334155;"
}

class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem tùy chỉnh để sắp xếp theo giá trị số thực tế (Numeric Sorting chuẩn xác)"""
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

class MainWindow(QMainWindow):
    """Cửa sổ chính Quản Lý & Theo Dõi Tăng Trưởng Kênh TikTok"""

    def __init__(self):
        super().__init__()
        self.app_version = get_local_version_info().get("version", "2.2")
        self.setWindowTitle(f"TikTok Channel Growth Tracker v{self.app_version} - Quản Lý & Theo Dõi Tăng Trưởng Kênh")
        self.resize(1420, 850)
        self.setMinimumSize(1100, 680)

        self.db = Database()
        self.exporter = ExcelExporter(self.db)
        self.scan_worker: Optional[ScanWorker] = None
        self.current_channels: List[Dict] = []
        self.is_auto_running: bool = False

        self.auto_timer = QTimer(self)
        self.auto_timer.setInterval(1000)
        self.auto_timer.timeout.connect(self._on_auto_timer_tick)
        self.seconds_remaining: int = 30 * 60

        self._init_ui()
        self.setStyleSheet(DARK_THEME_QSS)

        # Nạp trạng thái tự động quét từ cấu hình
        cfg = load_config()
        saved_mins = cfg.get("auto_scan_interval_minutes", 30)
        self.spin_auto_minutes.setValue(saved_mins)
        self.seconds_remaining = saved_mins * 60
        if cfg.get("auto_scan_enabled", False):
            self.chk_auto_scan.setChecked(True)

        self._refresh_all()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header KPI Cards
        main_layout.addLayout(self._create_header_kpi_layout())

        # 2. Main Action Toolbar (Thêm kênh, Chạy đã chọn, Chạy tất cả, Xóa đã chọn, Xuất Excel)
        main_layout.addLayout(self._create_main_action_toolbar())

        # 3. Selection & Filter Toolbar (Chọn tất cả, Bỏ chọn, Chọn chưa quét, Lọc tag, Tìm kiếm)
        main_layout.addLayout(self._create_selection_filter_toolbar())

        # 4. Main Data Table
        self.table = QTableWidget()
        self.table.setColumnCount(22)
        self.table.setHorizontalHeaderLabels([
            "☑️", "STT", "Tên Kênh", "TikTok ID", 
            "Quốc gia", "Mã ĐT", "Nhóm / Tag", 
            "Followers", "Tăng Follow (+/-)", 
            "Tổng Tym", "Tăng Tym (+/-)", 
            "Tổng Video", "V1 (Mới nhất)", "V2", "V3", "V4", "V5", 
            "View TB (5 video)", "RPM", "Dash", "Ghi chú", "Trạng thái & Giờ quét"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.table.setMouseTracking(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        self.table.cellEntered.connect(self._on_table_cell_entered)
        self.table.doubleClicked.connect(self._on_table_double_click)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.setSortingEnabled(True)

        main_layout.addWidget(self.table, 1)

        # 5. Progress Bar & Status Footer
        main_layout.addLayout(self._create_statusbar_layout())

    def _create_header_kpi_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.card_total = self._create_kpi_card("📊 TỔNG SỐ KÊNH", "0 kênh", "Đang quản lý trong hệ thống")
        layout.addWidget(self.card_total)

        self.card_followers = self._create_kpi_card("👥 TỔNG FOLLOWERS", "0", "+0 hôm nay", is_growth=True)
        layout.addWidget(self.card_followers)

        self.card_hearts = self._create_kpi_card("❤️ TỔNG LƯỢT TYM", "0", "+0 hôm nay", is_growth=True)
        layout.addWidget(self.card_hearts)

        self.card_dash = self._create_kpi_card("💵 TỔNG DASH ($)", "$0", "0 kênh có doanh thu | RPM TB: 0", is_growth=True)
        layout.addWidget(self.card_dash)

        self.card_status = self._create_kpi_card("⚡ TIẾN ĐỘ HÔM NAY", "0 / 0 kênh", f"Ngày {date.today().strftime('%d/%m/%Y')}")
        layout.addWidget(self.card_status)

        return layout

    def _create_kpi_card(self, title: str, main_val: str, sub_val: str, is_growth: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("kpiTitle")
        card_layout.addWidget(lbl_title)

        lbl_val = QLabel(main_val)
        lbl_val.setObjectName("kpiValue")
        card_layout.addWidget(lbl_val)

        lbl_sub = QLabel(sub_val)
        if is_growth:
            lbl_sub.setObjectName("kpiGrowthPos")
        else:
            lbl_sub.setObjectName("kpiTitle")
        card_layout.addWidget(lbl_sub)

        card.lbl_val = lbl_val
        card.lbl_sub = lbl_sub
        return card

    def _create_main_action_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # Nút Thêm Kênh (Mỗi ID 1 dòng)
        btn_add = QPushButton("➕ Nhập danh sách ID")
        btn_add.setObjectName("btnPrimary")
        btn_add.setToolTip("Mở bảng dán danh sách ID (mỗi ID một dòng)")
        btn_add.clicked.connect(self._open_add_channel_dialog)
        layout.addWidget(btn_add)

        layout.addSpacing(8)

        # Nút Chạy các kênh đã chọn hôm nay (Big Green)
        self.btn_scan_selected = QPushButton("⚡ Chạy hôm nay (Các kênh đã chọn)")
        self.btn_scan_selected.setObjectName("btnSuccess")
        self.btn_scan_selected.setToolTip("Chỉ quét cập nhật các kênh bạn vừa tick chọn")
        self.btn_scan_selected.clicked.connect(self._start_scan_selected)
        layout.addWidget(self.btn_scan_selected)

        # Nút Chạy toàn bộ
        self.btn_scan_all = QPushButton("🚀 Cập nhật toàn bộ")
        self.btn_scan_all.setToolTip("Quét cập nhật tất cả kênh trong hệ thống")
        self.btn_scan_all.clicked.connect(self._start_scan_all)
        layout.addWidget(self.btn_scan_all)

        # Nút Dừng quét (khi đang chạy)
        self.btn_stop_scan = QPushButton("⏹️ Dừng quét")
        self.btn_stop_scan.setObjectName("btnDanger")
        self.btn_stop_scan.setVisible(False)
        self.btn_stop_scan.clicked.connect(self._stop_scan)
        layout.addWidget(self.btn_stop_scan)

        # Nút Xóa các kênh đã chọn
        btn_del = QPushButton("🗑️ Xóa kênh đã chọn")
        btn_del.setObjectName("btnDanger")
        btn_del.setToolTip("Xóa toàn bộ các kênh đang được tick chọn")
        btn_del.clicked.connect(self._delete_selected_channels)
        layout.addWidget(btn_del)

        layout.addSpacing(6)

        # Cụm điều khiển Tự động quét hiển thị trực tiếp ngoài giao diện
        frame_auto = QFrame()
        frame_auto.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border: 1px solid #38BDF8;
                border-radius: 6px;
            }
        """)
        h_auto = QHBoxLayout(frame_auto)
        h_auto.setContentsMargins(8, 2, 8, 2)
        h_auto.setSpacing(6)

        self.chk_auto_scan = QCheckBox("⏰ Tự động:")
        self.chk_auto_scan.setStyleSheet("font-weight: 700; color: #38BDF8;")
        self.chk_auto_scan.setToolTip("Bật/Tắt chế độ tự động quét định kỳ theo số phút bên cạnh (Đồng bộ cả Windows Task Scheduler).")
        self.chk_auto_scan.toggled.connect(self._on_auto_scan_toggled)
        h_auto.addWidget(self.chk_auto_scan)

        self.spin_auto_minutes = QSpinBox()
        self.spin_auto_minutes.setRange(5, 1440)
        self.spin_auto_minutes.setValue(30)
        self.spin_auto_minutes.setSuffix(" phút")
        self.spin_auto_minutes.setFixedWidth(85)
        self.spin_auto_minutes.setToolTip("Khoảng thời gian tự động quét lặp lại (Ví dụ: 15, 30, 60 phút...)")
        self.spin_auto_minutes.valueChanged.connect(self._on_auto_interval_changed)
        h_auto.addWidget(self.spin_auto_minutes)

        self.lbl_auto_countdown = QLabel("Đang tắt")
        self.lbl_auto_countdown.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 11px;")
        h_auto.addWidget(self.lbl_auto_countdown)

        layout.addWidget(frame_auto)

        layout.addStretch()

        # Nút Xuất Excel
        btn_export = QPushButton("📊 Xuất file Excel (.xlsx)")
        btn_export.setToolTip("Xuất toàn bộ bảng dữ liệu và lịch sử ra file Excel đẹp mắt")
        btn_export.clicked.connect(self._export_excel)
        layout.addWidget(btn_export)

        # Nút Xem lịch sử
        btn_history = QPushButton("📈 Xem lịch sử kênh")
        btn_history.clicked.connect(self._open_selected_history)
        layout.addWidget(btn_history)

        # Nút Cài đặt
        btn_settings = QPushButton("⚙️ Cài đặt")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        # Nút Cập nhật phiên bản mới từ GitHub
        btn_update = QPushButton(f"🔄 Cập nhật (v{self.app_version})")
        btn_update.setToolTip("Cập nhật phiên bản mới từ GitHub (Giữ nguyên 100% kênh, Cookie, Proxy trên máy)")
        btn_update.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: #FFFFFF; font-weight: 700;
                border: 1px solid #38BDF8; border-radius: 6px; padding: 6px 12px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        btn_update.clicked.connect(self._open_update_dialog)
        layout.addWidget(btn_update)

        return layout

    def _create_selection_filter_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Quick Selection Buttons
        btn_select_all = QPushButton("☑️ Chọn tất cả")
        btn_select_all.setFixedHeight(32)
        btn_select_all.clicked.connect(self._select_all_rows)
        layout.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("⬜ Bỏ chọn")
        btn_deselect_all.setFixedHeight(32)
        btn_deselect_all.clicked.connect(self._deselect_all_rows)
        layout.addWidget(btn_deselect_all)

        btn_select_unscanned = QPushButton("⚡ Chọn kênh chưa quét hôm nay")
        btn_select_unscanned.setFixedHeight(32)
        btn_select_unscanned.setToolTip("Tự động tick chọn các kênh chưa có dữ liệu ngày hôm nay")
        btn_select_unscanned.clicked.connect(self._select_unscanned_today)
        layout.addWidget(btn_select_unscanned)

        layout.addSpacing(12)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(32)
        self.txt_search.setPlaceholderText("🔍 Tìm theo ID (@username) hoặc tên kênh...")
        self.txt_search.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.txt_search, 2)

        # Filter by Category/Tag
        lbl_cat = QLabel("Nhóm / Tag:")
        lbl_cat.setStyleSheet("font-weight: 600; color: #94A3B8;")
        layout.addWidget(lbl_cat)

        self.cb_category_filter = QComboBox()
        self.cb_category_filter.setFixedHeight(32)
        self.cb_category_filter.addItem("Tất cả")
        self.cb_category_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cb_category_filter, 1)

        # Filter by Country
        lbl_ctry = QLabel("Quốc gia:")
        lbl_ctry.setStyleSheet("font-weight: 600; color: #94A3B8;")
        layout.addWidget(lbl_ctry)

        self.cb_country_filter = QComboBox()
        self.cb_country_filter.setFixedHeight(32)
        self.cb_country_filter.addItem("Tất cả")
        self.cb_country_filter.addItems(COUNTRY_OPTIONS[1:] + ["Chưa chọn (--)"]) # Mỹ, Anh, Pháp, Đức, Nhật, Hàn, Mexico, Chưa chọn
        self.cb_country_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cb_country_filter, 1)

        # Filter by Phone Code
        lbl_phone = QLabel("Mã ĐT:")
        lbl_phone.setStyleSheet("font-weight: 600; color: #94A3B8;")
        layout.addWidget(lbl_phone)

        self.cb_phone_filter = QComboBox()
        self.cb_phone_filter.setFixedHeight(32)
        self.cb_phone_filter.addItem("Tất cả")
        self.cb_phone_filter.addItems([str(i) for i in range(1, 101)] + ["Chưa có mã (--)"])
        self.cb_phone_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cb_phone_filter, 1)

        # Filter by RPM
        lbl_rpm = QLabel("RPM:")
        lbl_rpm.setStyleSheet("font-weight: 600; color: #34D399;")
        layout.addWidget(lbl_rpm)

        self.cb_rpm_filter = QComboBox()
        self.cb_rpm_filter.setFixedHeight(32)
        self.cb_rpm_filter.addItems([
            "Tất cả",
            "💰 Đã có RPM (> 0)",
            "⚪ Chưa nhập RPM (= 0)",
            "🔥 RPM >= 0.5",
            "🔥 RPM >= 1.0",
            "🔥 RPM >= 5.0",
            "🔥 RPM >= 10.0",
            "🔥 RPM >= 50.0"
        ])
        self.cb_rpm_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cb_rpm_filter, 1)

        # Filter by Growth Status
        lbl_growth = QLabel("Lọc:")
        lbl_growth.setStyleSheet("font-weight: 600; color: #94A3B8;")
        layout.addWidget(lbl_growth)

        self.cb_growth_filter = QComboBox()
        self.cb_growth_filter.setFixedHeight(32)
        self.cb_growth_filter.addItems(["Tất cả", "🟢 Đang tăng Follow", "🔴 Sụt giảm Follow", "⚡ Chưa quét hôm nay"])
        self.cb_growth_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cb_growth_filter, 1)

        # Sắp xếp (Sort Selector)
        lbl_sort = QLabel("Sắp xếp:")
        lbl_sort.setStyleSheet("font-weight: 600; color: #94A3B8;")
        layout.addWidget(lbl_sort)

        self.cb_sort = QComboBox()
        self.cb_sort.setFixedHeight(32)
        self.cb_sort.addItems([
            "Mặc định (STT)",
            "💵 Dash ($) cao nhất (Giảm dần)",
            "💵 Dash ($) thấp nhất (Tăng dần)",
            "💰 RPM cao nhất (Giảm dần)",
            "💸 RPM thấp nhất (Tăng dần)",
            "🔥 V1 cao nhất (Giảm dần)",
            "❄️ V1 thấp nhất (Tăng dần)",
            "🔥 V2 cao nhất",
            "🔥 V3 cao nhất",
            "🔥 V4 cao nhất",
            "🔥 V5 cao nhất",
            "📊 View TB cao nhất",
            "👥 Followers nhiều nhất",
            "📈 Tăng Follow nhiều nhất",
            "❤️ Tổng Tym nhiều nhất",
            "🌐 Quốc gia (A-Z)",
            "📱 Mã ĐT (1-100)",
            "🏷️ Nhóm / Tag"
        ])
        self.cb_sort.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self.cb_sort, 1)

        # Refresh button
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedHeight(32)
        btn_refresh.setToolTip("Làm mới bảng dữ liệu")
        btn_refresh.clicked.connect(self._refresh_all)
        layout.addWidget(btn_refresh)

        return layout

    def _create_statusbar_layout(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Footer Row
        h = QHBoxLayout()
        self.lbl_status = QLabel("🟢 Sẵn sàng làm việc.")
        self.lbl_status.setStyleSheet("color: #94A3B8; font-size: 12px;")
        h.addWidget(self.lbl_status, 1)

        self.lbl_selected_count = QLabel("Đang chọn: 0 kênh")
        self.lbl_selected_count.setStyleSheet("color: #10B981; font-weight: 700; font-size: 12px; margin-right: 15px;")
        h.addWidget(self.lbl_selected_count)

        self.lbl_table_summary = QLabel("0 kênh")
        self.lbl_table_summary.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 12px;")
        h.addWidget(self.lbl_table_summary)
        layout.addLayout(h)

        return layout

    # --- SELECTION HELPERS ---

    def _on_sort_changed(self, idx: int):
        sort_map = {
            0: (1, Qt.SortOrder.AscendingOrder),   # STT
            1: (19, Qt.SortOrder.DescendingOrder), # Dash ($) cao nhất
            2: (19, Qt.SortOrder.AscendingOrder),  # Dash ($) thấp nhất
            3: (18, Qt.SortOrder.DescendingOrder), # RPM cao nhất
            4: (18, Qt.SortOrder.AscendingOrder),  # RPM thấp nhất
            5: (12, Qt.SortOrder.DescendingOrder), # V1 giảm dần
            6: (12, Qt.SortOrder.AscendingOrder),  # V1 tăng dần
            7: (13, Qt.SortOrder.DescendingOrder), # V2
            8: (14, Qt.SortOrder.DescendingOrder), # V3
            9: (15, Qt.SortOrder.DescendingOrder), # V4
            10: (16, Qt.SortOrder.DescendingOrder),# V5
            11: (17, Qt.SortOrder.DescendingOrder),# View TB
            12: (7, Qt.SortOrder.DescendingOrder), # Followers
            13: (8, Qt.SortOrder.DescendingOrder), # Tăng Follow
            14: (9, Qt.SortOrder.DescendingOrder), # Tổng Tym
            15: (4, Qt.SortOrder.AscendingOrder),  # Quốc gia
            16: (5, Qt.SortOrder.AscendingOrder),  # Mã ĐT
            17: (6, Qt.SortOrder.AscendingOrder)   # Nhóm / Tag
        }
        if idx in sort_map:
            col, order = sort_map[idx]
            self.table.sortItems(col, order)

    def _apply_category_style(self, combo, val: str):
        style_base = CATEGORY_STYLES.get(val, CATEGORY_STYLES.get("Mặc định", "background-color: #1E293B; color: #94A3B8; border: 1px solid #334155;"))
        combo.setStyleSheet(f"""
            QComboBox {{
                {style_base}
                border-radius: 8px;
                padding: 1px 6px;
                font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; width: 14px; }}
            QComboBox QAbstractItemView {{
                background-color: #1E293B;
                color: #F8FAFC;
                selection-background-color: #0284C7;
            }}
        """)

    def _on_channel_category_changed(self, channel_id: int, category: str, row: int):
        val = category.strip()
        self.db.update_channel_category(channel_id, val)
        ch = self._get_channel_at_row(row)
        if ch:
            ch["category"] = val
            self._sync_channel_at_row(row, ch)
        item = self.table.item(row, 6)
        if item:
            item.setText(val)

    def _on_channel_country_changed(self, channel_id: int, country: str, row: int):
        save_val = "" if country == "--" else country
        self.db.update_channel_country(channel_id, save_val)
        ch = self._get_channel_at_row(row)
        if ch:
            ch["country"] = save_val
            self._sync_channel_at_row(row, ch)
        item = self.table.item(row, 4)
        if item:
            item.setText(country)

    def _on_channel_phone_code_changed(self, channel_id: int, phone_code: str, row: int):
        save_val = "" if phone_code == "--" else phone_code
        self.db.update_channel_phone_code(channel_id, save_val)
        ch = self._get_channel_at_row(row)
        if ch:
            ch["phone_code"] = save_val
            self._sync_channel_at_row(row, ch)
        item = self.table.item(row, 5)
        if item:
            item.setText(phone_code)
            if hasattr(item, "num_val"):
                item.num_val = float(save_val) if save_val.isdigit() else 0.0

    def _get_channel_at_row(self, row: int) -> Optional[Dict]:
        chk_item = self.table.item(row, 0)
        if chk_item:
            ch = chk_item.data(Qt.ItemDataRole.UserRole)
            if ch:
                return ch
        if 0 <= row < len(self.current_channels):
            return self.current_channels[row]
        return None

    def _sync_channel_at_row(self, row: int, ch: Dict):
        chk_item = self.table.item(row, 0)
        if chk_item:
            chk_item.setData(Qt.ItemDataRole.UserRole, ch)
        cid = ch.get("id")
        if cid is not None:
            for idx, c in enumerate(self.current_channels):
                if c.get("id") == cid:
                    self.current_channels[idx] = ch
                    break

    def _get_visible_total_dash(self) -> float:
        total = 0.0
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 19)
            if it and hasattr(it, "num_val"):
                total += float(it.num_val or 0.0)
        return total

    def _select_all_rows(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._update_selected_counter()

    def _deselect_all_rows(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._update_selected_counter()

    def _select_unscanned_today(self):
        today_str = date.today().strftime("%Y-%m-%d")
        self.table.blockSignals(True)
        matched_count = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            ch = self._get_channel_at_row(row)
            if item and ch:
                scan_date = ch.get("scan_date") or ""
                if scan_date != today_str:
                    item.setCheckState(Qt.CheckState.Checked)
                    matched_count += 1
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._update_selected_counter()
        self.lbl_status.setText(f"⚡ Đã chọn {matched_count} kênh chưa quét hôm nay.")

    @staticmethod
    def _format_rpm(val: float) -> str:
        if not val:
            return "0"
        if val == int(val):
            return f"{int(val):,}"
        return f"{val:,.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_usd(val: float) -> str:
        if not val:
            return "$0"
        if val == int(val):
            return f"${int(val):,}"
        return f"${val:,.2f}"

    def _on_table_item_changed(self, item):
        col = item.column()
        row = item.row()
        if col == 0:
            self._update_selected_counter()
            return

        if col in (18, 19, 20):
            ch = self._get_channel_at_row(row)
            if not ch:
                return
            self.table.blockSignals(True)
            try:
                if col == 18:
                    raw_txt = item.text().replace(",", "").replace("$", "").replace("đ", "").replace(" ", "").strip()
                    try:
                        rpm_val = float(raw_txt) if raw_txt else 0.0
                    except ValueError:
                        rpm_val = float(ch.get("rpm") or 0.0)
                    disp_rpm = self._format_rpm(rpm_val)
                    item.setText(disp_rpm)
                    if hasattr(item, "num_val"):
                        item.num_val = rpm_val
                    item.setForeground(QColor("#34D399") if rpm_val > 0 else QColor("#94A3B8"))
                    f = item.font()
                    f.setBold(rpm_val > 0)
                    item.setFont(f)
                    ch["rpm"] = rpm_val
                    self._sync_channel_at_row(row, ch)
                    self.db.update_channel_rpm(ch["id"], ch.get("username", ""), rpm_val)
                    self._update_kpi_cards()
                    self.lbl_status.setText(f"💰 Đã lưu RPM ngày hôm nay cho kênh @{ch.get('username')}: {disp_rpm}")
                elif col == 19:
                    raw_txt = item.text().replace(",", "").replace("$", "").replace("usd", "").replace("USD", "").replace(" ", "").strip()
                    try:
                        dash_val = float(raw_txt) if raw_txt else 0.0
                    except ValueError:
                        dash_val = float(ch.get("dash") or 0.0)
                    disp_dash = self._format_usd(dash_val)
                    item.setText(disp_dash)
                    if hasattr(item, "num_val"):
                        item.num_val = dash_val
                    item.setForeground(QColor("#38BDF8") if dash_val > 0 else QColor("#94A3B8"))
                    f = item.font()
                    f.setBold(dash_val > 0)
                    item.setFont(f)
                    ch["dash"] = dash_val
                    self._sync_channel_at_row(row, ch)
                    self.db.update_channel_dash(ch["id"], ch.get("username", ""), dash_val)
                    self._update_kpi_cards()
                    total_dash = self._get_visible_total_dash()
                    self.lbl_table_summary.setText(f"💵 Tổng Dash đang lọc: {self._format_usd(total_dash)}   |   Hiển thị: {self.table.rowCount()} kênh")
                    self.lbl_status.setText(f"💵 Đã lưu Dash cho kênh @{ch.get('username')}: {disp_dash}  |  Tổng Dash: {self._format_usd(total_dash)}")
                elif col == 20:
                    note_txt = item.text().strip()
                    item.setText(note_txt)
                    item.setToolTip(note_txt if note_txt else "📝 Bấm vào để nhập ghi chú cho tài khoản này")
                    ch["note"] = note_txt
                    self._sync_channel_at_row(row, ch)
                    self.db.update_channel_note(ch["id"], note_txt)
                    self.lbl_status.setText(f"📝 Đã lưu ghi chú cho kênh @{ch.get('username')}.")
            finally:
                self.table.blockSignals(False)

    def _update_selected_counter(self):
        selected_count = len(self._get_selected_channels())
        self.lbl_selected_count.setText(f"Đang chọn: {selected_count}/{len(self.current_channels)} kênh")

    def _get_selected_channels(self) -> List[Dict]:
        selected = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                ch = self._get_channel_at_row(row)
                if ch:
                    selected.append(ch)
        if not selected:
            selected_rows = set(index.row() for index in self.table.selectedIndexes())
            for r in selected_rows:
                ch = self._get_channel_at_row(r)
                if ch:
                    selected.append(ch)
        return selected

    # --- DATA REFRESH & POPULATION ---

    def _refresh_all(self):
        self._update_category_filter_list()
        self._load_table_data()
        self._update_kpi_cards()
        self._update_selected_counter()

    def _update_category_filter_list(self):
        current_selection = self.cb_category_filter.currentText()
        self.cb_category_filter.blockSignals(True)
        self.cb_category_filter.clear()
        self.cb_category_filter.addItem("Tất cả")
        cats = self.db.get_categories()
        all_cats = list(dict.fromkeys(CATEGORY_OPTIONS + cats))
        self.cb_category_filter.addItems(all_cats)
        
        idx = self.cb_category_filter.findText(current_selection)
        if idx >= 0:
            self.cb_category_filter.setCurrentIndex(idx)
        self.cb_category_filter.blockSignals(False)

    def _update_kpi_cards(self):
        kpi = self.db.get_dashboard_kpi()
        total_ch = kpi["total_channels"]
        scanned_ch = kpi["scanned_channels"]
        total_flw = kpi["total_followers"]
        total_hrt = kpi["total_hearts"]
        delta_flw = kpi["total_growth_followers"]
        delta_hrt = kpi["total_growth_hearts"]

        self.card_total.lbl_val.setText(f"{total_ch:,} kênh")
        self.card_followers.lbl_val.setText(f"{total_flw:,}")
        
        if delta_flw > 0:
            self.card_followers.lbl_sub.setText(f"📈 +{delta_flw:,} Follow hôm nay")
            self.card_followers.lbl_sub.setObjectName("kpiGrowthPos")
        elif delta_flw < 0:
            self.card_followers.lbl_sub.setText(f"📉 {delta_flw:,} Follow hôm nay")
            self.card_followers.lbl_sub.setObjectName("kpiGrowthNeg")
        else:
            self.card_followers.lbl_sub.setText("+0 Follow hôm nay")
            self.card_followers.lbl_sub.setObjectName("kpiTitle")

        self.card_hearts.lbl_val.setText(f"{total_hrt:,}")
        if delta_hrt > 0:
            self.card_hearts.lbl_sub.setText(f"📈 +{delta_hrt:,} Tym hôm nay")
            self.card_hearts.lbl_sub.setObjectName("kpiGrowthPos")
        elif delta_hrt < 0:
            self.card_hearts.lbl_sub.setText(f"📉 {delta_hrt:,} Tym hôm nay")
            self.card_hearts.lbl_sub.setObjectName("kpiGrowthNeg")
        else:
            self.card_hearts.lbl_sub.setText("+0 Tym hôm nay")
            self.card_hearts.lbl_sub.setObjectName("kpiTitle")

        self.card_status.lbl_val.setText(f"{scanned_ch}/{total_ch} kênh")

        total_dash = kpi.get("total_dash", 0.0)
        dash_ch = kpi.get("dash_channels", 0)
        avg_rpm = kpi.get("avg_rpm", 0.0)
        self.card_dash.lbl_val.setText(self._format_usd(total_dash))
        self.card_dash.lbl_val.setStyleSheet("color: #34D399; font-size: 22px; font-weight: 800;")
        self.card_dash.lbl_sub.setText(f"💰 {dash_ch} kênh có tiền | RPM TB: {self._format_rpm(avg_rpm)}")
        self.card_dash.lbl_sub.setObjectName("kpiGrowthPos" if total_dash > 0 else "kpiTitle")

        for c in [self.card_followers, self.card_hearts, self.card_dash]:
            c.lbl_sub.style().unpolish(c.lbl_sub)
            c.lbl_sub.style().polish(c.lbl_sub)

    def _on_filter_changed(self):
        self._load_table_data()
        self._update_selected_counter()

    def _load_table_data(self):
        cat_filter = self.cb_category_filter.currentText()
        ctry_filter = self.cb_country_filter.currentText() if hasattr(self, "cb_country_filter") else "Tất cả"
        phone_filter = self.cb_phone_filter.currentText() if hasattr(self, "cb_phone_filter") else "Tất cả"
        search_txt = self.txt_search.text().strip()
        growth_filter = self.cb_growth_filter.currentIndex()

        channels = self.db.get_all_channels(
            category_filter=cat_filter if cat_filter != "Tất cả" else None,
            country_filter=ctry_filter if ctry_filter != "Tất cả" else None,
            phone_code_filter=phone_filter if phone_filter != "Tất cả" else None,
            search_query=search_txt if search_txt else None
        )

        today_str = date.today().strftime("%Y-%m-%d")

        rpm_filter = self.cb_rpm_filter.currentIndex() if hasattr(self, "cb_rpm_filter") else 0

        filtered_channels = []
        for ch in channels:
            d_flw = ch.get("delta_followers") or 0
            s_date = ch.get("scan_date") or ""
            rpm_v = float(ch.get("rpm") or 0.0)
            if growth_filter == 1 and d_flw <= 0:
                continue
            if growth_filter == 2 and d_flw >= 0:
                continue
            if growth_filter == 3 and s_date == today_str:
                continue
            if rpm_filter == 1 and rpm_v <= 0:
                continue
            if rpm_filter == 2 and rpm_v != 0:
                continue
            if rpm_filter == 3 and rpm_v < 0.5:
                continue
            if rpm_filter == 4 and rpm_v < 1.0:
                continue
            if rpm_filter == 5 and rpm_v < 5.0:
                continue
            if rpm_filter == 6 and rpm_v < 10.0:
                continue
            if rpm_filter == 7 and rpm_v < 50.0:
                continue
            filtered_channels.append(ch)

        self.current_channels = filtered_channels
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered_channels))

        for row_idx, ch in enumerate(filtered_channels):
            # Cột 0: Checkbox (Lưu object channel vào UserRole để mapping chuẩn xác kể cả sau khi Sort)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, ch)
            self.table.setItem(row_idx, 0, chk_item)

            # Cột 1: STT
            self._set_cell(row_idx, 1, str(row_idx + 1), align=Qt.AlignmentFlag.AlignCenter, num_val=row_idx + 1)

            # Cột 2: Tên Kênh
            nick = ch.get("nickname") or ch.get("username")
            self._set_cell(row_idx, 2, nick, bold=True)

            # Cột 3: TikTok ID (Bấm vào để mở trình duyệt xem kênh)
            uname = ch.get('username') or ''
            self._set_cell(
                row_idx, 3, f"@{uname}",
                color=QColor("#38BDF8"),
                underline=True,
                tooltip=f"🌐 Bấm vào để mở kênh @{uname} trên trình duyệt web"
            )

            # Cột 4: Quốc gia (Dropdown chọn: Mỹ, Anh, Pháp, Đức, Nhật, Hàn, Mexico)
            cb_ctry = QComboBox()
            cb_ctry.addItems(COUNTRY_OPTIONS)
            cb_ctry.setStyleSheet("""
                QComboBox {
                    background-color: #1E293B;
                    color: #38BDF8;
                    font-weight: 700;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 11px;
                }
                QComboBox QAbstractItemView {
                    background-color: #1E293B;
                    color: #F8FAFC;
                    selection-background-color: #0284C7;
                }
            """)
            cur_ctry = ch.get("country") or "--"
            idx_c = cb_ctry.findText(cur_ctry)
            cb_ctry.setCurrentIndex(idx_c if idx_c >= 0 else 0)
            cb_ctry.currentTextChanged.connect(
                lambda val, cid=ch['id'], r=row_idx: self._on_channel_country_changed(cid, val, r)
            )
            self._set_cell(row_idx, 4, cur_ctry, align=Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row_idx, 4, cb_ctry)

            # Cột 5: Mã điện thoại (Dropdown chọn từ 1 đến 100)
            cb_ph = QComboBox()
            cb_ph.addItems(PHONE_OPTIONS)
            cb_ph.setStyleSheet("""
                QComboBox {
                    background-color: #1E293B;
                    color: #FBBF24;
                    font-weight: 700;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 11px;
                }
                QComboBox QAbstractItemView {
                    background-color: #1E293B;
                    color: #F8FAFC;
                    selection-background-color: #0284C7;
                }
            """)
            cur_ph = str(ch.get("phone_code") or "--")
            idx_p = cb_ph.findText(cur_ph)
            cb_ph.setCurrentIndex(idx_p if idx_p >= 0 else 0)
            cb_ph.currentTextChanged.connect(
                lambda val, cid=ch['id'], r=row_idx: self._on_channel_phone_code_changed(cid, val, r)
            )
            ph_num = int(cur_ph) if cur_ph.isdigit() else 0
            self._set_cell(row_idx, 5, cur_ph, align=Qt.AlignmentFlag.AlignCenter, num_val=ph_num)
            self.table.setCellWidget(row_idx, 5, cb_ph)

            # Cột 6: Nhóm / Tag (Dropdown Pill Badge: BKT, TKT NT, TKT BM, NUÔI, OUT, Mặc định...)
            cb_cat = QComboBox()
            cur_cat = ch.get("category") or "Mặc định"
            combo_items = list(dict.fromkeys(CATEGORY_OPTIONS + ([cur_cat] if cur_cat else [])))
            cb_cat.addItems(combo_items)
            idx_cat = cb_cat.findText(cur_cat)
            cb_cat.setCurrentIndex(idx_cat if idx_cat >= 0 else 0)
            self._apply_category_style(cb_cat, cur_cat)
            cb_cat.currentTextChanged.connect(
                lambda val, cid=ch['id'], r=row_idx, c=cb_cat: (
                    self._on_channel_category_changed(cid, val, r),
                    self._apply_category_style(c, val)
                )
            )
            self._set_cell(row_idx, 6, cur_cat, align=Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row_idx, 6, cb_cat)

            # Cột 7: Followers
            flw = ch.get("followers") or 0
            self._set_cell(row_idx, 7, f"{flw:,}", align=Qt.AlignmentFlag.AlignRight, num_val=flw)

            # Cột 8: Tăng trưởng Follow (vs Hôm qua)
            d_flw = ch.get("delta_followers") or 0
            d_flw_str = f"+{d_flw:,}" if d_flw > 0 else (f"{d_flw:,}" if d_flw < 0 else "0")
            d_flw_col = QColor("#10B981") if d_flw > 0 else (QColor("#EF4444") if d_flw < 0 else None)
            self._set_cell(row_idx, 8, d_flw_str, align=Qt.AlignmentFlag.AlignRight, color=d_flw_col, bold=True, num_val=d_flw)

            # Cột 9: Tổng Tym
            hrt = ch.get("hearts") or 0
            self._set_cell(row_idx, 9, f"{hrt:,}", align=Qt.AlignmentFlag.AlignRight, num_val=hrt)

            # Cột 10: Tăng trưởng Tym (vs Hôm qua)
            d_hrt = ch.get("delta_hearts") or 0
            d_hrt_str = f"+{d_hrt:,}" if d_hrt > 0 else (f"{d_hrt:,}" if d_hrt < 0 else "0")
            d_hrt_col = QColor("#10B981") if d_hrt > 0 else (QColor("#EF4444") if d_hrt < 0 else None)
            self._set_cell(row_idx, 10, d_hrt_str, align=Qt.AlignmentFlag.AlignRight, color=d_hrt_col, bold=True, num_val=d_hrt)

            # Cột 11: Tổng Video
            v_cnt = ch.get("video_count") or 0
            self._set_cell(row_idx, 11, f"{v_cnt:,}", align=Qt.AlignmentFlag.AlignRight, num_val=v_cnt)

            # Cột 12-16: V1 - V5 Views (Tô màu vàng nổi bật cho video >= 10,000 views)
            v_views = [
                ch.get("v1_view") or 0,
                ch.get("v2_view") or 0,
                ch.get("v3_view") or 0,
                ch.get("v4_view") or 0,
                ch.get("v5_view") or 0
            ]
            for col_offset, v_val in enumerate(v_views):
                col_idx = 12 + col_offset
                if v_val >= 10000:
                    self._set_cell(
                        row_idx, col_idx, f"{v_val:,}",
                        align=Qt.AlignmentFlag.AlignRight,
                        color=QColor("#FEF08A"),            # Chữ màu vàng sáng
                        bg_color=QColor(234, 179, 8, 85),   # Nền màu vàng hổ phách nổi bật
                        bold=True,
                        num_val=v_val
                    )
                else:
                    self._set_cell(row_idx, col_idx, f"{v_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=v_val)

            # Cột 17: View TB (5 video)
            avg_v = ch.get("avg_views") or 0.0
            self._set_cell(row_idx, 17, f"{avg_v:,.1f}", align=Qt.AlignmentFlag.AlignRight, bold=True, color=QColor("#FBBF24"), num_val=avg_v)

            # Cột 18: RPM (Bấm vào để nhập số tiền / RPM cập nhật theo ngày)
            rpm_val = float(ch.get("rpm") or 0.0)
            rpm_disp = self._format_rpm(rpm_val)
            self._set_cell(
                row_idx, 18, rpm_disp,
                align=Qt.AlignmentFlag.AlignRight,
                bold=(rpm_val > 0),
                color=QColor("#34D399") if rpm_val > 0 else QColor("#94A3B8"),
                num_val=rpm_val,
                tooltip="💰 Bấm vào để nhập RPM hôm nay (Nhấn Enter để lưu)",
                editable=True
            )

            # Cột 19: Dash (Bấm vào để cập nhật số tiền USD đã kiếm được đến hiện tại)
            dash_val = float(ch.get("dash") or 0.0)
            dash_disp = self._format_usd(dash_val)
            self._set_cell(
                row_idx, 19, dash_disp,
                align=Qt.AlignmentFlag.AlignRight,
                bold=(dash_val > 0),
                color=QColor("#38BDF8") if dash_val > 0 else QColor("#94A3B8"),
                num_val=dash_val,
                tooltip="💵 Bấm vào để nhập số tiền Dash ($) đã kiếm được đến hiện tại (Nhấn Enter để lưu)",
                editable=True
            )

            # Cột 20: Ghi chú (Bấm vào để ghi chú thông tin liên quan đến acc)
            note_txt = str(ch.get("note") or "")
            self._set_cell(
                row_idx, 20, note_txt,
                align=Qt.AlignmentFlag.AlignLeft,
                color=QColor("#E2E8F0"),
                tooltip=note_txt if note_txt else "📝 Bấm vào để nhập ghi chú cho tài khoản này (Nhấn Enter để lưu)",
                editable=True
            )

            # Cột 21: Trạng thái & Giờ quét
            st = str(ch.get("status") or "Chưa quét")
            last_t = str(ch.get("last_scanned_at") or "")
            time_part = ""
            if last_t and " " in last_t:
                parts = last_t.split(" ")
                time_part = parts[1] if len(parts) > 1 else parts[0]
            elif last_t:
                time_part = last_t
            st_display = f"{st} ({time_part})" if time_part else st
            st_col = QColor("#10B981") if "Hoạt động" in st else (QColor("#EF4444") if "Lỗi" in st else QColor("#94A3B8"))
            self._set_cell(row_idx, 21, st_display, align=Qt.AlignmentFlag.AlignCenter, color=st_col)

        self.table.setSortingEnabled(True)
        if hasattr(self, "cb_sort") and self.cb_sort.currentIndex() > 0:
            self._on_sort_changed(self.cb_sort.currentIndex())

        self.table.blockSignals(False)
        filtered_dash = sum(float(c.get("dash") or 0.0) for c in filtered_channels)
        self.lbl_table_summary.setText(f"💵 Tổng Dash đang lọc: {self._format_usd(filtered_dash)}   |   Hiển thị: {len(filtered_channels)} kênh")

    def _set_cell(self, row: int, col: int, text: str, align=Qt.AlignmentFlag.AlignLeft, color=None, bold=False, bg_color=None, num_val=None, underline=False, tooltip=None, editable=False):
        if num_val is not None:
            item = NumericTableWidgetItem(str(text), num_val)
        else:
            item = QTableWidgetItem(str(text))
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if editable:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if color:
            item.setForeground(color)
        if bg_color:
            item.setBackground(bg_color)
        if bold or underline:
            f = item.font()
            if bold:
                f.setBold(True)
            if underline:
                f.setUnderline(True)
            item.setFont(f)
        if tooltip:
            item.setToolTip(tooltip)
        self.table.setItem(row, col, item)

    # --- ACTIONS ---

    def _open_add_channel_dialog(self):
        dlg = AddChannelDialog(self.db, parent=self)
        if dlg.exec():
            self._refresh_all()

    def _delete_selected_channels(self):
        selected_channels = self._get_selected_channels()
        if not selected_channels:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng tick chọn ít nhất 1 kênh để xóa!")
            return

        reply = QMessageBox.question(
            self, "Xác nhận xóa hàng loạt",
            f"Bạn có chắc chắn muốn xóa {len(selected_channels)} kênh đã chọn và toàn bộ lịch sử liên quan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ids = [ch['id'] for ch in selected_channels]
            self.db.delete_channels_bulk(ids)
            self._refresh_all()
            QMessageBox.information(self, "Đã xóa", f"✅ Đã xóa thành công {len(ids)} kênh khỏi hệ thống.")

    def _start_scan_all(self):
        channels = self.db.get_all_channels()
        if not channels:
            QMessageBox.warning(self, "Danh sách trống", "Chưa có kênh nào trong hệ thống! Vui lòng bấm '➕ Nhập danh sách ID' trước.")
            return
        self._execute_scan(channels)

    def _start_scan_selected(self):
        selected = self._get_selected_channels()
        if not selected:
            QMessageBox.warning(self, "Chưa chọn kênh", "Vui lòng tick chọn các kênh cần chạy hôm nay!")
            return
        self._execute_scan(selected)

    def _execute_scan(self, channels_to_scan: List[Dict]):
        if self.scan_worker and self.scan_worker.isRunning():
            QMessageBox.warning(self, "Đang quét", "Tiến trình quét đang chạy! Vui lòng chờ hoàn thành hoặc bấm Dừng.")
            return

        cfg = load_config()
        threads = cfg.get("threads", 3)
        delay = cfg.get("delay_min", 1.5)

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(channels_to_scan))
        self.progress_bar.setValue(0)

        self.btn_scan_all.setEnabled(False)
        self.btn_scan_selected.setEnabled(False)
        self.btn_stop_scan.setVisible(True)

        self.scan_worker = ScanWorker(channels_to_scan, threads=threads, delay=delay, parent=self)
        self.scan_worker.progress_updated.connect(self._on_scan_progress)
        self.scan_worker.channel_scanned.connect(self._on_channel_scanned)
        self.scan_worker.log_message.connect(self._on_scan_log)
        self.scan_worker.scan_finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_channel_scanned(self, data: dict):
        try:
            username = data.get("username", "").strip().lstrip("@").lower()
            stats = data.get("stats") or {}
            videos = data.get("videos") or []
            v_views = [v.get("play_count", 0) for v in videos[:5]]
            while len(v_views) < 5:
                v_views.append(0)
            avg_v = sum(v_views) / max(1, len([v for v in v_views if v > 0])) if any(v > 0 for v in v_views) else 0.0

            for row in range(self.table.rowCount()):
                user_item = self.table.item(row, 3)
                if user_item and user_item.text().strip().lstrip("@").lower() == username:
                    self.table.blockSignals(True)
                    if stats.get("nickname"):
                        self._set_cell(row, 2, stats["nickname"], bold=True)
                    flw_val = stats.get('follower_count', 0)
                    self._set_cell(row, 7, f"{flw_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=flw_val)
                    hrt_val = stats.get('heart_count', 0)
                    self._set_cell(row, 9, f"{hrt_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=hrt_val)
                    vid_val = stats.get('video_count', 0)
                    self._set_cell(row, 11, f"{vid_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=vid_val)
                    for vi in range(5):
                        v_val = v_views[vi]
                        if v_val >= 10000:
                            self._set_cell(
                                row, 12 + vi, f"{v_val:,}",
                                align=Qt.AlignmentFlag.AlignRight,
                                color=QColor("#FEF08A"),
                                bg_color=QColor(234, 179, 8, 85),
                                bold=True,
                                num_val=v_val
                            )
                        else:
                            self._set_cell(row, 12 + vi, f"{v_val:,}", align=Qt.AlignmentFlag.AlignRight, num_val=v_val)
                    self._set_cell(row, 17, f"{avg_v:,.1f}", align=Qt.AlignmentFlag.AlignRight, bold=True, color=QColor("#FBBF24"), num_val=avg_v)
                    
                    now_time = datetime.now().strftime("%H:%M:%S")
                    self._set_cell(row, 21, f"Hoạt động ({now_time})", align=Qt.AlignmentFlag.AlignCenter, color=QColor("#10B981"))
                    self.table.blockSignals(False)
                    break
        except Exception:
            pass

    def _on_scan_progress(self, current: int, total: int, username: str, status_text: str):
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"⏳ [{current}/{total}] @{username}: {status_text}")
        if current % 5 == 0 or current == total:
            self._update_kpi_cards()

    def _on_scan_log(self, msg: str, level: str):
        self.lbl_status.setText(msg)

    def _on_scan_finished(self, success_cnt: int, error_cnt: int):
        self.btn_scan_all.setEnabled(True)
        self.btn_scan_selected.setEnabled(True)
        self.btn_stop_scan.setVisible(False)
        self.progress_bar.setVisible(False)

        self._refresh_all()

        if self.chk_auto_scan.isChecked():
            self.seconds_remaining = self.spin_auto_minutes.value() * 60

        if self.is_auto_running:
            self.is_auto_running = False
            self._export_excel(silent=True)
            self.lbl_status.setText(f"🎉 [Tự động quét hoàn tất]: {success_cnt} thành công, {error_cnt} lỗi. Đã tự xuất Excel!")
        else:
            cfg = load_config()
            if cfg.get("auto_export_excel"):
                self._export_excel(silent=True)

            QMessageBox.information(
                self, "Hoàn tất quét hôm nay",
                f"🎉 Quá trình cập nhật hoàn tất!\n\n"
                f"✅ Thành công: {success_cnt} kênh\n"
                f"❌ Thất bại: {error_cnt} kênh\n\n"
                f"Đã lưu mốc dữ liệu ngày {date.today().strftime('%d/%m/%Y')} và tự động tính tăng trưởng."
            )

    # --- AUTO SCAN HANDLERS ---

    def _on_auto_scan_toggled(self, checked: bool):
        cfg = load_config()
        cfg["auto_scan_enabled"] = checked
        cfg["auto_scan_interval_minutes"] = self.spin_auto_minutes.value()
        save_config(cfg)

        if checked:
            ok, msg = register_windows_task(self.spin_auto_minutes.value())
            self.seconds_remaining = self.spin_auto_minutes.value() * 60
            self.auto_timer.start()
            self.lbl_auto_countdown.setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px;")
            self.lbl_status.setText(f"⏰ Đã bật tự động quét mỗi {self.spin_auto_minutes.value()} phút ({msg})")
        else:
            ok, msg = remove_windows_task()
            self.auto_timer.stop()
            self.lbl_auto_countdown.setText("Đang tắt")
            self.lbl_auto_countdown.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 11px;")
            self.lbl_status.setText("⏹️ Đã tắt chế độ tự động quét.")

    def _on_auto_interval_changed(self, val: int):
        cfg = load_config()
        cfg["auto_scan_interval_minutes"] = val
        save_config(cfg)
        if self.chk_auto_scan.isChecked():
            register_windows_task(val)
            self.seconds_remaining = val * 60
            self.lbl_status.setText(f"⏰ Đã cập nhật chu kỳ tự động quét thành mỗi {val} phút.")

    def _on_auto_timer_tick(self):
        if not self.chk_auto_scan.isChecked():
            return
        if self.scan_worker and self.scan_worker.isRunning():
            self.lbl_auto_countdown.setText("⏳ Đang quét...")
            return

        self.seconds_remaining -= 1
        if self.seconds_remaining <= 0:
            self.seconds_remaining = self.spin_auto_minutes.value() * 60
            self.lbl_auto_countdown.setText("🚀 Đang chạy...")
            self.is_auto_running = True
            self._start_scan_all()
        else:
            mins, secs = divmod(self.seconds_remaining, 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
            else:
                time_str = f"{mins:02d}:{secs:02d}"
            self.lbl_auto_countdown.setText(f"⏳ Còn: {time_str}")

    def _stop_scan(self):
        if self.scan_worker:
            self.scan_worker.stop()
            self.lbl_status.setText("⏹️ Đang dừng tiến trình quét...")

    def _export_excel(self, silent: bool = False):
        try:
            cat_filter = self.cb_category_filter.currentText()
            ctry_filter = self.cb_country_filter.currentText() if hasattr(self, "cb_country_filter") else "Tất cả"
            phone_filter = self.cb_phone_filter.currentText() if hasattr(self, "cb_phone_filter") else "Tất cả"
            
            filepath = self.exporter.export_growth_report(
                category_filter=cat_filter if cat_filter != "Tất cả" else None,
                country_filter=ctry_filter if ctry_filter != "Tất cả" else None,
                phone_code_filter=phone_filter if phone_filter != "Tất cả" else None
            )
            
            if not silent:
                reply = QMessageBox.information(
                    self, "Xuất Excel Thành Công",
                    f"✅ Đã xuất báo cáo Excel thành công!\n\n📁 Vị trí lưu:\n{filepath}\n\nBạn có muốn mở thư mục chứa file không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(EXPORTS_DIR)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất Excel", f"Không thể xuất file: {e}")

    def _open_selected_history(self):
        selected = self._get_selected_channels()
        if not selected:
            QMessageBox.warning(self, "Chưa chọn kênh", "Vui lòng chọn 1 kênh trên bảng để xem lịch sử tăng trưởng!")
            return
        ch = selected[0]
        dlg = HistoryDialog(ch, self.db, parent=self)
        dlg.exec()

    def _on_table_cell_entered(self, row: int, col: int):
        if col == 3:
            self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        elif col in (18, 19, 20):
            self.table.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.table.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def _on_table_cell_clicked(self, row: int, col: int):
        if col == 3:
            ch = self._get_channel_at_row(row)
            username = ""
            if ch and ch.get("username"):
                username = ch["username"].strip().lstrip("@")
            else:
                item = self.table.item(row, 3)
                if item:
                    username = item.text().strip().lstrip("@")
            if username:
                url = f"https://www.tiktok.com/@{username}"
                webbrowser.open(url)
                self.lbl_status.setText(f"🌐 Đang mở kênh @{username} trên trình duyệt web...")
        elif col in (18, 19, 20):
            item = self.table.item(row, col)
            if item:
                self.table.editItem(item)

    def _on_table_double_click(self, index):
        if index.column() in (3, 18, 19, 20):
            return
        ch = self._get_channel_at_row(index.row())
        if ch:
            dlg = HistoryDialog(ch, self.db, parent=self)
            dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    def _open_update_dialog(self):
        dlg = UpdateDialog(parent=self)
        dlg.exec()

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        ch = self._get_channel_at_row(item.row())
        if not ch:
            return

        menu = QMenu(self)

        act_history = menu.addAction("📈 Xem lịch sử tăng trưởng")
        act_rescan = menu.addAction("⚡ Quét lại kênh này")
        act_open_web = menu.addAction("🌐 Mở kênh trên TikTok (Trình duyệt)")
        menu.addSeparator()
        act_change_cat = menu.addAction("🏷️ Đổi Nhóm / Tag")
        act_delete = menu.addAction("🗑️ Xóa kênh này")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_history:
            dlg = HistoryDialog(ch, self.db, parent=self)
            dlg.exec()
        elif action == act_rescan:
            self._execute_scan([ch])
        elif action == act_open_web:
            webbrowser.open(f"https://www.tiktok.com/@{ch['username']}")
        elif action == act_change_cat:
            new_cat, ok = QInputDialog.getText(self, "Đổi Nhóm / Tag", "Nhập tên nhóm mới:", text=ch.get("category", ""))
            if ok and new_cat.strip():
                self.db.update_channel_category(ch['id'], new_cat.strip())
                self._refresh_all()
        elif action == act_delete:
            reply = QMessageBox.question(
                self, "Xác nhận xóa", f"Bạn có chắc muốn xóa kênh @{ch['username']}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_channel(ch['id'])
                self._refresh_all()
