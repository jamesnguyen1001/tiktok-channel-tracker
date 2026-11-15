import os
import requests
from typing import List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QSpinBox, QCheckBox, QPlainTextEdit, QMessageBox, QGroupBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.config import load_config, save_config
from core.scanner import parse_proxy, TikTokLoginWorker, ProxyCheckWorker


class ProxyResultsDialog(QDialog):
    """Hộp thoại kiểm tra toàn bộ danh sách Proxy theo từng dòng"""

    def __init__(self, proxies: List[str], parent_editor, parent=None):
        super().__init__(parent)
        self.raw_proxies = proxies
        self.parent_editor = parent_editor
        self.setWindowTitle("🔍 Kiểm Tra Kết Nối Toàn Bộ Proxy Từng Dòng")
        self.resize(680, 440)
        self.working_proxies = []
        self._init_ui()
        self._start_checking()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.lbl_info = QLabel(f"Đang kiểm tra 0/{len(self.raw_proxies)} proxy...")
        self.lbl_info.setStyleSheet("font-weight: 700; color: #38BDF8; font-size: 13px;")
        layout.addWidget(self.lbl_info)

        self.progress = QProgressBar()
        self.progress.setMaximum(len(self.raw_proxies))
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Dòng", "Proxy", "Trạng thái", "IP thực tế / Chi tiết", "Ping"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setRowCount(len(self.raw_proxies))

        for i, p in enumerate(self.raw_proxies):
            self._set_cell(i, 0, str(i + 1), align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(i, 1, p)
            self._set_cell(i, 2, "⏳ Đang chờ...", color=QColor("#94A3B8"), align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(i, 3, "--")
            self._set_cell(i, 4, "--", align=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.table, 1)

        h_btn = QHBoxLayout()
        self.btn_clean = QPushButton("🧹 Chỉ giữ lại proxy sống (Lọc bỏ proxy lỗi)")
        self.btn_clean.setEnabled(False)
        self.btn_clean.clicked.connect(self._apply_clean)
        h_btn.addWidget(self.btn_clean)

        h_btn.addStretch()

        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        h_btn.addWidget(self.btn_close)

        layout.addLayout(h_btn)

    def _set_cell(self, row, col, text, align=Qt.AlignmentFlag.AlignLeft, color=None, bold=False):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(color)
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        self.table.setItem(row, col, item)

    def _start_checking(self):
        self.worker = ProxyCheckWorker(self.raw_proxies, parent=self)
        self.worker.proxy_checked.connect(self._on_proxy_checked)
        self.worker.check_finished.connect(self._on_check_finished)
        self.worker.start()

    def _on_proxy_checked(self, idx, raw_p, is_ok, ip_or_error, ping_ms):
        row = idx - 1
        self.progress.setValue(idx)
        self.lbl_info.setText(f"Đang kiểm tra dòng {idx}/{len(self.raw_proxies)}: {raw_p[:35]}...")
        if is_ok:
            self.working_proxies.append(raw_p)
            self._set_cell(row, 2, "🟢 Hoạt động", color=QColor("#10B981"), bold=True, align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(row, 3, ip_or_error, color=QColor("#F8FAFC"))
            self._set_cell(row, 4, f"{ping_ms:.0f} ms", color=QColor("#FBBF24"), align=Qt.AlignmentFlag.AlignCenter)
        else:
            self._set_cell(row, 2, "🔴 Lỗi", color=QColor("#EF4444"), bold=True, align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(row, 3, ip_or_error, color=QColor("#F87171"))
            self._set_cell(row, 4, "--", color=QColor("#94A3B8"), align=Qt.AlignmentFlag.AlignCenter)

    def _on_check_finished(self, success_cnt, fail_cnt):
        total = len(self.raw_proxies)
        if success_cnt == total:
            self.lbl_info.setText(f"🎉 Hoàn tất kiểm tra: 100% ({success_cnt}/{total}) proxy đều hoạt động xuất sắc!")
            self.lbl_info.setStyleSheet("font-weight: 700; color: #10B981; font-size: 13px;")
        else:
            self.lbl_info.setText(f"📊 Hoàn tất: {success_cnt}/{total} proxy sống, {fail_cnt} proxy lỗi kết nối.")
            self.lbl_info.setStyleSheet("font-weight: 700; color: #F59E0B; font-size: 13px;")
            if success_cnt > 0:
                self.btn_clean.setEnabled(True)

    def _apply_clean(self):
        if self.working_proxies:
            self.parent_editor.setPlainText("\n".join(self.working_proxies))
            QMessageBox.information(
                self, "Đã Lọc Proxy",
                f"✅ Đã cập nhật lại ô cấu hình Proxy!\n\nChỉ giữ lại {len(self.working_proxies)} proxy hoạt động tốt."
            )
            self.accept()

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
        super().closeEvent(event)

class SettingsDialog(QDialog):
    """Hộp thoại cài đặt cấu hình quét, Cookie và Proxy"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Cài Đặt Cấu Hình, Cookie & Proxy")
        self.setMinimumSize(580, 680)
        self.setModal(True)
        self.config = load_config()
        self.login_worker = None
        self._init_ui()
        self._load_values()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Performance & Delay Group
        gb_perf = QGroupBox("⏱️ Tốc độ & Số luồng song song (Performance)")
        v_perf = QVBoxLayout(gb_perf)
        v_perf.setSpacing(10)

        # Số luồng quét song song (Threads)
        h_threads = QHBoxLayout()
        lbl_threads = QLabel("Số luồng quét song song (Parallel Workers):")
        lbl_threads.setStyleSheet("font-weight: 600; color: #38BDF8;")
        h_threads.addWidget(lbl_threads)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 20)
        self.spin_threads.setValue(6)
        self.spin_threads.setSuffix(" luồng")
        self.spin_threads.setToolTip("Số luồng quét đồng thời (1 - 20 luồng). Khuyên dùng 5 - 10 luồng để đạt tốc độ cao nhất.")
        h_threads.addWidget(self.spin_threads)

        self.btn_turbo_preset = QPushButton("⚡ Chế độ Siêu Tốc")
        self.btn_turbo_preset.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: #FFFFFF; font-weight: bold;
                padding: 4px 10px; border-radius: 5px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.btn_turbo_preset.setToolTip("Đặt nhanh: 6 luồng song song, thời gian nghỉ 0.2 - 0.5s, thử lại 1 lần")
        self.btn_turbo_preset.clicked.connect(self._apply_turbo_preset)
        h_threads.addWidget(self.btn_turbo_preset)
        v_perf.addLayout(h_threads)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Thời gian nghỉ ngẫu nhiên giữa các kênh:"))
        
        self.spin_delay_min = QDoubleSpinBox()
        self.spin_delay_min.setRange(0.1, 30.0)
        self.spin_delay_min.setSingleStep(0.1)
        self.spin_delay_min.setValue(0.2)
        self.spin_delay_min.setSuffix(" giây")
        h1.addWidget(self.spin_delay_min)

        lbl_to = QLabel("đến")
        lbl_to.setStyleSheet("color: #94A3B8;")
        h1.addWidget(lbl_to)

        self.spin_delay_max = QDoubleSpinBox()
        self.spin_delay_max.setRange(0.2, 60.0)
        self.spin_delay_max.setSingleStep(0.2)
        self.spin_delay_max.setValue(0.5)
        self.spin_delay_max.setSuffix(" giây")
        h1.addWidget(self.spin_delay_max)

        v_perf.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Số lần tự động thử lại khi gặp lỗi (Retries):"))
        self.spin_retry = QSpinBox()
        self.spin_retry.setRange(0, 5)
        self.spin_retry.setValue(1)
        h2.addWidget(self.spin_retry)
        v_perf.addLayout(h2)

        layout.addWidget(gb_perf)

        # TikTok Cookie Group (Bypass 100% Captcha & Get all video views)
        gb_cookie = QGroupBox("🍪 Cookie TikTok (Mở khóa 100% View 5 video & Không lo Captcha)")
        v_cookie = QVBoxLayout(gb_cookie)
        v_cookie.setSpacing(8)

        lbl_cookie_hint = QLabel(
            "💡 Nạp Cookie để TikTok mở toàn quyền xem View 5 video & chống Captcha:\n"
            "   (Mỗi dòng là 1 Tài khoản Cookie độc lập — hỗ trợ bấm nút đăng nhập tự động bên dưới)"
        )
        lbl_cookie_hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        v_cookie.addWidget(lbl_cookie_hint)

        self.lbl_cookie_count = QLabel("📊 Trạng thái: Chưa có Cookie nào (0 tài khoản)")
        self.lbl_cookie_count.setStyleSheet(
            "background-color: #0F172A; color: #10B981; font-weight: 700; font-size: 12px; "
            "padding: 6px 10px; border-radius: 6px; border: 1px solid #1E293B;"
        )
        self.lbl_cookie_count.setWordWrap(True)
        v_cookie.addWidget(self.lbl_cookie_count)

        self.txt_cookie = QPlainTextEdit()
        self.txt_cookie.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_cookie.setPlaceholderText("Dòng 1: Cookie Acc 1 (sessionid=xxxx; ttwid=xxxx; ...)\nDòng 2: Cookie Acc 2 (sessionid=yyyy; ttwid=yyyy; ...)")
        self.txt_cookie.setFixedHeight(85)
        self.txt_cookie.textChanged.connect(self._update_cookie_summary)
        v_cookie.addWidget(self.txt_cookie)

        h_cookie_actions = QHBoxLayout()
        self.btn_auto_login = QPushButton("🌐 Đăng nhập lấy Cookie Acc 1")
        self.btn_auto_login.setObjectName("btnPrimary")
        self.btn_auto_login.setToolTip("Mở trình duyệt để bạn đăng nhập hoặc quét mã QR nick đầu tiên!")
        self.btn_auto_login.clicked.connect(self._start_auto_login)
        h_cookie_actions.addWidget(self.btn_auto_login)

        self.btn_add_acc = QPushButton("➕ Đăng nhập thêm Acc mới (Nick 2, Nick 3...)")
        self.btn_add_acc.setToolTip("Mở trình duyệt sạch để bạn quét mã QR hoặc đăng nhập thêm nick khác, tự động nối thêm dòng mới!")
        self.btn_add_acc.clicked.connect(self._start_auto_login)
        h_cookie_actions.addWidget(self.btn_add_acc)

        btn_clear_cookie = QPushButton("🗑️ Xóa hết")
        btn_clear_cookie.setToolTip("Xóa toàn bộ cookie trong ô")
        btn_clear_cookie.clicked.connect(self._clear_cookie)
        h_cookie_actions.addWidget(btn_clear_cookie)
        h_cookie_actions.addStretch()
        v_cookie.addLayout(h_cookie_actions)

        # Tùy chọn đăng nhập qua Proxy
        h_proxy_login = QHBoxLayout()
        lbl_proxy_mode = QLabel("🛡️ Đăng nhập TikTok bằng Proxy:")
        lbl_proxy_mode.setStyleSheet("color: #38BDF8; font-weight: 700;")
        h_proxy_login.addWidget(lbl_proxy_mode)

        self.cb_login_proxy = QComboBox()
        self.cb_login_proxy.setFixedHeight(30)
        self.cb_login_proxy.setToolTip("Chọn proxy cụ thể hoặc tự động gán theo thứ tự Acc")
        h_proxy_login.addWidget(self.cb_login_proxy, 1)
        v_cookie.addLayout(h_proxy_login)

        self.lbl_login_status = QLabel("")
        self.lbl_login_status.setStyleSheet("color: #38BDF8; font-size: 11px;")
        v_cookie.addWidget(self.lbl_login_status)

        layout.addWidget(gb_cookie)

        # Proxy Group
        gb_proxy = QGroupBox("🛡️ Cấu hình Proxy (Tĩnh hoặc Xoay)")
        v_proxy = QVBoxLayout(gb_proxy)
        v_proxy.setSpacing(8)

        self.chk_use_proxy = QCheckBox("Bật sử dụng Proxy khi quét")
        self.chk_use_proxy.setStyleSheet("font-weight: 700; color: #10B981;")
        v_proxy.addWidget(self.chk_use_proxy)

        lbl_proxy_hint = QLabel(
            "💡 Hỗ trợ: IP:PORT:USER:PASS, IP:PORT, http://user:pass@ip:port, socks5://...\n"
            "🔗 Quy tắc gán cặp: Luồng 1 (Acc dòng 1 + Proxy dòng 1) | Luồng 2 (Acc dòng 2 + Proxy dòng 2)..."
        )
        lbl_proxy_hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        v_proxy.addWidget(lbl_proxy_hint)

        self.txt_proxies = QPlainTextEdit()
        self.txt_proxies.setPlaceholderText("103.151.240.10:8080:admin:pass123\n103.151.240.11:8080\nhttp://user:pass@ip:port\n(Mỗi dòng 1 proxy)")
        self.txt_proxies.setFixedHeight(85)
        self.txt_proxies.textChanged.connect(self._update_login_proxy_list)
        v_proxy.addWidget(self.txt_proxies)

        # Test Proxy Button Row
        h_proxy_test = QHBoxLayout()
        btn_test_proxy = QPushButton("🔍 Kiểm tra kết nối Proxy")
        btn_test_proxy.clicked.connect(self._test_proxy)
        h_proxy_test.addWidget(btn_test_proxy)
        h_proxy_test.addStretch()
        v_proxy.addLayout(h_proxy_test)

        layout.addWidget(gb_proxy)

        # Auto Export
        self.chk_auto_export = QCheckBox("Tự động xuất file Excel (.xlsx) sau khi quét xong toàn bộ")
        layout.addWidget(self.chk_auto_export)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Lưu Cài Đặt")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _apply_turbo_preset(self):
        self.spin_threads.setValue(6)
        self.spin_delay_min.setValue(0.2)
        self.spin_delay_max.setValue(0.5)
        self.spin_retry.setValue(1)

    def _load_values(self):
        self.spin_threads.setValue(self.config.get("threads", 6))
        self.spin_delay_min.setValue(self.config.get("delay_min", 0.2))
        self.spin_delay_max.setValue(self.config.get("delay_max", 0.5))
        self.spin_retry.setValue(self.config.get("retry_count", 1))
        self.chk_use_proxy.setChecked(self.config.get("use_proxy", False))
        self.chk_auto_export.setChecked(self.config.get("auto_export_excel", False))
        self.txt_cookie.setPlainText(self.config.get("tiktok_cookie", ""))
        self._update_cookie_summary()
        
        proxies = self.config.get("proxies", [])
        self.txt_proxies.setPlainText("\n".join(proxies))
        self._update_login_proxy_list()
        saved_mode = self.config.get("login_proxy_mode", "")
        if saved_mode:
            idx = self.cb_login_proxy.findText(saved_mode)
            if idx >= 0:
                self.cb_login_proxy.setCurrentIndex(idx)

    def _update_cookie_summary(self):
        raw_text = self.txt_cookie.toPlainText().strip()
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if not lines:
            self.lbl_cookie_count.setText("⚠️ Trạng thái: Chưa có Cookie nào (0 tài khoản)")
            self.lbl_cookie_count.setStyleSheet(
                "background-color: #0F172A; color: #F59E0B; font-weight: 700; font-size: 12px; "
                "padding: 6px 10px; border-radius: 6px; border: 1px solid #334155;"
            )
            return

        badges = []
        for idx, line in enumerate(lines, 1):
            sid = ""
            for part in line.split(";"):
                part = part.strip()
                if part.startswith("sessionid="):
                    val = part.split("=", 1)[1].strip()
                    sid = f"...{val[-6:]}" if len(val) > 6 else val
                    break
            if sid:
                badges.append(f"Acc {idx} (ID: {sid})")
            else:
                badges.append(f"Acc {idx} (Khách/Chưa có sessionid)")

        detail_str = "  |  ".join(badges)
        self.lbl_cookie_count.setText(f"✅ Đã nạp: {len(lines)} Cookie tài khoản  ➔  {detail_str}")
        self.lbl_cookie_count.setStyleSheet(
            "background-color: #064E3B; color: #34D399; font-weight: 700; font-size: 12px; "
            "padding: 6px 10px; border-radius: 6px; border: 1px solid #10B981;"
        )

    def _update_login_proxy_list(self):
        current_text = self.cb_login_proxy.currentText()
        self.cb_login_proxy.clear()
        proxies = [p.strip() for p in self.txt_proxies.toPlainText().splitlines() if p.strip()]
        if not proxies:
            self.cb_login_proxy.addItem("🚫 Không dùng Proxy (Chưa có proxy bên dưới)")
            return

        self.cb_login_proxy.addItem("⚡ Tự động gán (Acc 1 -> Proxy 1, Acc 2 -> Proxy 2...)")
        for i, p in enumerate(proxies, 1):
            short_p = p if len(p) <= 35 else p[:32] + "..."
            self.cb_login_proxy.addItem(f"Dòng {i}: {short_p}")
        self.cb_login_proxy.addItem("🚫 Không dùng Proxy (Dùng mạng trực tiếp máy tính)")

        idx = self.cb_login_proxy.findText(current_text)
        if idx >= 0:
            self.cb_login_proxy.setCurrentIndex(idx)
        else:
            self.cb_login_proxy.setCurrentIndex(0)

    def _start_auto_login(self):
        if self.login_worker and self.login_worker.isRunning():
            QMessageBox.warning(self, "Đang mở", "Trình duyệt đăng nhập đang mở! Vui lòng thao tác trên cửa sổ trình duyệt vừa hiện.")
            return

        proxies = [p.strip() for p in self.txt_proxies.toPlainText().splitlines() if p.strip()]
        selected_proxy = None
        proxy_display_name = ""

        combo_text = self.cb_login_proxy.currentText()
        combo_idx = self.cb_login_proxy.currentIndex()

        if not combo_text.startswith("🚫") and proxies:
            if combo_idx == 0:
                # Tự động gán theo số lượng acc đã có
                acc_idx = len([l for l in self.txt_cookie.toPlainText().splitlines() if l.strip()])
                target_raw = proxies[acc_idx % len(proxies)]
                proxy_display_name = f"Proxy dòng {(acc_idx % len(proxies)) + 1}"
            else:
                target_raw = proxies[combo_idx - 1]
                proxy_display_name = f"Proxy dòng {combo_idx}"

            selected_proxy = parse_proxy(target_raw)

        self.btn_auto_login.setEnabled(False)
        self.btn_add_acc.setEnabled(False)

        if selected_proxy:
            srv = selected_proxy.get("server", "").replace("http://", "")
            self.lbl_login_status.setText(f"⏳ Đang mở trình duyệt qua {proxy_display_name} ({srv})... Hãy đăng nhập TikTok trên cửa sổ hiện ra!")
        else:
            self.lbl_login_status.setText("⏳ Đang khởi động trình duyệt (Mạng trực tiếp)... Hãy quét mã QR hoặc đăng nhập trên cửa sổ TikTok!")

        self.login_worker = TikTokLoginWorker(proxy=selected_proxy, parent=self)
        self.login_worker.status_updated.connect(lambda msg: self.lbl_login_status.setText(msg))
        self.login_worker.login_success.connect(self._on_login_success)
        self.login_worker.login_failed.connect(self._on_login_failed)
        self.login_worker.start()

    def _on_login_success(self, cookie_str: str):
        self.btn_auto_login.setEnabled(True)
        self.btn_add_acc.setEnabled(True)
        current = self.txt_cookie.toPlainText().strip()
        if current and cookie_str not in current:
            new_text = current + "\n" + cookie_str
        elif not current:
            new_text = cookie_str
        else:
            new_text = current
        self.txt_cookie.setPlainText(new_text)

        acc_count = len([l for l in new_text.splitlines() if l.strip()])
        self.lbl_login_status.setText(f"✅ Đã kết nối thành công {acc_count} tài khoản TikTok!")
        QMessageBox.information(
            self, "Đăng Nhập Thành Công",
            f"🎉 Đã lưu Cookie thành công!\n\n"
            f"Hiện tại trong danh sách có: {acc_count} tài khoản TikTok.\n"
            f"Các tài khoản này sẽ được luân phiên tự động phân bổ cho các luồng quét."
        )

    def _on_login_failed(self, err_msg: str):
        self.btn_auto_login.setEnabled(True)
        self.btn_add_acc.setEnabled(True)
        self.lbl_login_status.setText(f"❌ {err_msg}")

    def _clear_cookie(self):
        self.txt_cookie.clear()
        self.lbl_login_status.setText("🗑️ Đã xóa Cookie.")

    def _test_proxy(self):
        proxies = [p.strip() for p in self.txt_proxies.toPlainText().splitlines() if p.strip()]
        if not proxies:
            QMessageBox.warning(self, "Chưa có Proxy", "Vui lòng nhập ít nhất 1 proxy để kiểm tra!")
            return

        dlg = ProxyResultsDialog(proxies, parent_editor=self.txt_proxies, parent=self)
        dlg.exec()

    def _save(self):
        proxies = [p.strip() for p in self.txt_proxies.toPlainText().splitlines() if p.strip()]
        d_min = self.spin_delay_min.value()
        d_max = self.spin_delay_max.value()

        if d_min > d_max:
            d_min, d_max = d_max, d_min

        self.config["threads"] = self.spin_threads.value()
        self.config["delay_min"] = d_min
        self.config["delay_max"] = d_max
        self.config["retry_count"] = self.spin_retry.value()
        self.config["use_proxy"] = self.chk_use_proxy.isChecked()
        self.config["login_proxy_mode"] = self.cb_login_proxy.currentText()
        self.config["auto_export_excel"] = self.chk_auto_export.isChecked()
        self.config["tiktok_cookie"] = self.txt_cookie.toPlainText().strip()
        self.config["proxies"] = proxies

        save_config(self.config)
        QMessageBox.information(self, "Thành công", "✅ Đã lưu cài đặt cấu hình, Cookie & Proxy thành công!")
        self.accept()
