import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt

from core.database import Database

class AddChannelDialog(QDialog):
    """Hộp thoại nhập hàng loạt ID TikTok (Mỗi ID một dòng)"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("➕ Nhập Danh Sách ID Kênh TikTok")
        self.resize(520, 560)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info
        lbl_title = QLabel("📋 Dán danh sách TikTok ID cần theo dõi")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38BDF8;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Nhập hoặc dán danh sách ID (mỗi ID trên một dòng).\nTool sẽ tự động loại bỏ ký tự @ thừa và lọc bỏ các ID trùng lặp.")
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Text Area for IDs
        self.txt_ids = QPlainTextEdit()
        self.txt_ids.setPlaceholderText(
            "Ví dụ:\nvtv24news\n@tiktok\nkhaby.lame\nnguyen_van_a\n..."
        )
        self.txt_ids.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;")
        self.txt_ids.textChanged.connect(self._update_line_count)
        layout.addWidget(self.txt_ids, 1)

        # Bottom Controls: Category, Country, Phone Code & Line Counter
        h_controls = QHBoxLayout()
        h_controls.setSpacing(8)

        lbl_cat = QLabel("Nhóm / Tag:")
        lbl_cat.setStyleSheet("font-weight: 600;")
        h_controls.addWidget(lbl_cat)

        self.cb_category = QComboBox()
        self.cb_category.setEditable(True)
        # Các lựa chọn phân loại chuẩn theo yêu cầu: BKT, TKT NT, TKT BM, NUÔI, OUT
        standard_tags = ["BKT", "TKT NT", "TKT BM", "NUÔI", "OUT", "Mặc định"]
        self.cb_category.addItems(standard_tags)
        
        # Load thêm các nhóm cũ nếu có trong DB
        existing_cats = self.db.get_categories()
        for cat in existing_cats:
            if self.cb_category.findText(cat) < 0:
                self.cb_category.addItem(cat)

        h_controls.addWidget(self.cb_category, 2)

        lbl_ctry = QLabel("Quốc gia:")
        lbl_ctry.setStyleSheet("font-weight: 600;")
        h_controls.addWidget(lbl_ctry)

        self.cb_country = QComboBox()
        self.cb_country.addItems(["--", "Mỹ", "Anh", "Pháp", "Đức", "Nhật", "Hàn", "Mexico"])
        h_controls.addWidget(self.cb_country, 1)

        lbl_ph = QLabel("Mã ĐT:")
        lbl_ph.setStyleSheet("font-weight: 600;")
        h_controls.addWidget(lbl_ph)

        self.cb_phone = QComboBox()
        self.cb_phone.addItems(["--"] + [str(i) for i in range(1, 101)])
        h_controls.addWidget(self.cb_phone, 1)

        self.lbl_count = QLabel("Số lượng: 0 ID")
        self.lbl_count.setStyleSheet("color: #10B981; font-weight: 700;")
        h_controls.addWidget(self.lbl_count)

        layout.addLayout(h_controls)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_clean = QPushButton("🧹 Dọn dẹp khoảng trắng")
        btn_clean.setToolTip("Xóa các dòng trống và ký tự khoảng trắng thừa")
        btn_clean.clicked.connect(self._clean_text)
        btn_box.addWidget(btn_clean)

        btn_box.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Lưu vào danh sách")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save_channels)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _update_line_count(self):
        lines = [line.strip() for line in self.txt_ids.toPlainText().splitlines() if line.strip()]
        self.lbl_count.setText(f"Số lượng: {len(lines)} ID")

    def _clean_text(self):
        raw = self.txt_ids.toPlainText()
        lines = []
        for line in raw.splitlines():
            s = re.sub(r'https?://(?:www\.|m\.|vm\.|vt\.)?tiktok\.com/@?', '', line, flags=re.IGNORECASE).strip()
            s = s.lstrip('@').split('?')[0].split('#')[0].split('/')[0].strip()
            if s:
                lines.append(s)
        cleaned = lines
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for l in cleaned:
            if l.lower() not in seen:
                seen.add(l.lower())
                deduped.append(l)
        self.txt_ids.setPlainText("\n".join(deduped))

    def _save_channels(self):
        self._clean_text()
        raw = self.txt_ids.toPlainText()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]

        if not lines:
            QMessageBox.warning(self, "Chưa nhập ID", "Vui lòng nhập ít nhất một TikTok ID!")
            return

        category = self.cb_category.currentText().strip() or "Mặc định"
        country_val = self.cb_country.currentText().strip()
        country = "" if country_val == "--" else country_val
        phone_val = self.cb_phone.currentText().strip()
        phone_code = "" if phone_val == "--" else phone_val

        added, skipped = self.db.add_channels_bulk(lines, category=category, country=country, phone_code=phone_code)

        details = [f"nhóm '{category}'"]
        if country:
            details.append(f"quốc gia '{country}'")
        if phone_code:
            details.append(f"mã ĐT '{phone_code}'")

        msg = f"✅ Đã thêm thành công: {added} kênh ({', '.join(details)})."
        if skipped > 0:
            msg += f"\nℹ️ Đã bỏ qua: {skipped} kênh do đã tồn tại sẵn trong hệ thống."

        QMessageBox.information(self, "Hoàn tất thêm kênh", msg)
        self.accept()
