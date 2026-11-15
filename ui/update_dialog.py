import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt

from core.updater import (
    get_local_version_info, UpdateWorker, PublishWorker
)


class UpdateDialog(QDialog):
    """Hộp thoại Tự động Cập nhật phiên bản mới từ GitHub & Đẩy bản cập nhật sạch (Không kèm dữ liệu cá nhân)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔄 Cập Nhật Phiên Bản Mới (GitHub Auto-Update)")
        self.setMinimumSize(580, 440)
        self.setModal(True)
        self.update_worker = None
        self.publish_worker = None
        self.ver_info = get_local_version_info()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        cur_ver = self.ver_info.get("version", "2.2")
        lbl_title = QLabel(f"🚀 Trung Tâm Cập Nhật Tự Động — Phiên bản hiện tại: v{cur_ver}")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38BDF8;")
        layout.addWidget(lbl_title)

        lbl_safe = QLabel(
            "🛡️ Cam kết an toàn 100%: Quá trình cập nhật hoặc đẩy lên GitHub TUYỆT ĐỐI KHÔNG đụng chạm hay gửi đi\n"
            "   bất kỳ dữ liệu cá nhân nào (Danh sách kênh, Lịch sử, RPM, Dash, Cookie, Proxy, File Excel đều được giữ nguyên)."
        )
        lbl_safe.setStyleSheet(
            "background-color: #064E3B; color: #34D399; font-size: 11px; font-weight: 600; "
            "padding: 8px 10px; border-radius: 6px; border: 1px solid #10B981;"
        )
        layout.addWidget(lbl_safe)

        # Repo URL Group
        gb_repo = QGroupBox("🔗 Kho lưu trữ GitHub (GitHub Repository)")
        v_repo = QVBoxLayout(gb_repo)
        v_repo.setSpacing(8)

        lbl_repo_hint = QLabel("Link GitHub chứa bản cập nhật của Tool (chỉ cần điền 1 lần, Tool sẽ tự nhớ):")
        lbl_repo_hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        v_repo.addWidget(lbl_repo_hint)

        self.txt_repo = QLineEdit()
        self.txt_repo.setFixedHeight(34)
        self.txt_repo.setPlaceholderText("Ví dụ: https://github.com/jamesnguyen1001/tiktok-channel-tracker")
        self.txt_repo.setText(self.ver_info.get("github_repo", "https://github.com/jamesnguyen1001/tiktok-channel-tracker"))
        v_repo.addWidget(self.txt_repo)

        layout.addWidget(gb_repo)

        # 1. Phần dành cho Người dùng / Bạn bè: Bấm 1 nút để cập nhật về máy
        gb_pull = QGroupBox("📥 1. Dành cho Người dùng / Bạn bè: Tải bản mới về máy")
        v_pull = QVBoxLayout(gb_pull)
        v_pull.setSpacing(8)

        lbl_pull_desc = QLabel(
            "Bấm nút bên dưới để tự động tải toàn bộ tính năng mới nhất từ GitHub về máy.\n"
            "(Hoạt động trên mọi máy tính, kể cả máy chưa cài đặt phần mềm Git!)"
        )
        lbl_pull_desc.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        v_pull.addWidget(lbl_pull_desc)

        self.btn_pull_update = QPushButton("🔄 Bấm Vào Đây Để Cập Nhật Bản Mới Nhất Ngay")
        self.btn_pull_update.setObjectName("btnSuccess")
        self.btn_pull_update.setFixedHeight(40)
        self.btn_pull_update.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: #FFFFFF; font-weight: 800;
                font-size: 13px; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #334155; color: #94A3B8; }
        """)
        self.btn_pull_update.clicked.connect(self._start_pull_update)
        v_pull.addWidget(self.btn_pull_update)

        layout.addWidget(gb_pull)

        # 2. Phần dành cho Chủ Tool (Admin): Đẩy bản mới lên GitHub
        gb_push = QGroupBox("☁️ 2. Dành cho Chủ Tool (Admin): Đẩy bản mới lên GitHub cho bạn bè")
        v_push = QVBoxLayout(gb_push)
        v_push.setSpacing(8)

        h_ver = QHBoxLayout()
        h_ver.addWidget(QLabel("Mã phiên bản:"))
        self.txt_version = QLineEdit(self.ver_info.get("version", "2.1.0"))
        self.txt_version.setFixedWidth(90)
        h_ver.addWidget(self.txt_version)

        h_ver.addWidget(QLabel("Ghi chú bản cập nhật:"))
        self.txt_commit_msg = QLineEdit("Nang cap toc do & them cot RPM, Dash, Ghi chu")
        h_ver.addWidget(self.txt_commit_msg, 1)
        v_push.addLayout(h_ver)

        self.btn_push_github = QPushButton("☁️ Đẩy Code Sạch Lên GitHub (Không kèm Kênh, Cookie, Proxy)")
        self.btn_push_github.setFixedHeight(36)
        self.btn_push_github.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: #FFFFFF; font-weight: 700;
                font-size: 12px; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #0369A1; }
            QPushButton:disabled { background-color: #334155; color: #94A3B8; }
        """)
        self.btn_push_github.clicked.connect(self._start_push_github)
        v_push.addWidget(self.btn_push_github)

        layout.addWidget(gb_push)

        # Status Label
        self.lbl_status = QLabel("🟢 Sẵn sàng kiểm tra và cập nhật.")
        self.lbl_status.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 12px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Close Button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.reject)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _start_pull_update(self):
        repo_url = self.txt_repo.text().strip()
        if not repo_url:
            QMessageBox.warning(self, "Thiếu link GitHub", "Vui lòng nhập link GitHub của Tool vào ô bên trên!")
            return

        self.btn_pull_update.setEnabled(False)
        self.btn_push_github.setEnabled(False)
        self.lbl_status.setText("⏳ Đang tải bản cập nhật mới nhất từ GitHub...")

        self.update_worker = UpdateWorker(repo_url=repo_url, parent=self)
        self.update_worker.progress_msg.connect(lambda msg: self.lbl_status.setText(msg))
        self.update_worker.update_finished.connect(self._on_pull_finished)
        self.update_worker.start()

    def _on_pull_finished(self, ok: bool, msg: str, new_ver: str):
        self.btn_pull_update.setEnabled(True)
        self.btn_push_github.setEnabled(True)
        if ok:
            self.lbl_status.setText(f"✅ Cập nhật thành công lên phiên bản {new_ver}!")
            reply = QMessageBox.information(
                self, "Cập Nhật Thành Công",
                f"{msg}\n\nBạn có muốn tự động khởi động lại Tool ngay bây giờ để áp dụng bản mới không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._restart_app()
        else:
            self.lbl_status.setText(f"❌ {msg}")
            QMessageBox.warning(self, "Không thể cập nhật", msg)

    def _start_push_github(self):
        repo_url = self.txt_repo.text().strip()
        if not repo_url:
            QMessageBox.warning(self, "Thiếu link GitHub", "Vui lòng nhập link GitHub của bạn vào ô bên trên!")
            return

        self.btn_pull_update.setEnabled(False)
        self.btn_push_github.setEnabled(False)
        self.lbl_status.setText("⏳ Đang đóng gói code sạch và đẩy lên GitHub...")

        self.publish_worker = PublishWorker(
            repo_url=repo_url,
            new_version=self.txt_version.text().strip(),
            commit_msg=self.txt_commit_msg.text().strip(),
            parent=self
        )
        self.publish_worker.progress_msg.connect(lambda msg: self.lbl_status.setText(msg))
        self.publish_worker.publish_finished.connect(self._on_push_finished)
        self.publish_worker.start()

    def _on_push_finished(self, ok: bool, msg: str):
        self.btn_pull_update.setEnabled(True)
        self.btn_push_github.setEnabled(True)
        if ok:
            self.lbl_status.setText("✅ Đã đẩy bản cập nhật sạch lên GitHub thành công!")
            QMessageBox.information(self, "Đẩy Lên GitHub Thành Công", msg)
        else:
            self.lbl_status.setText("❌ Chưa đẩy được lên GitHub. Xem hướng dẫn trong hộp thoại.")
            QMessageBox.warning(self, "Hướng dẫn đẩy lên GitHub", msg)

    def _restart_app(self):
        try:
            exe_dir = os.path.dirname(sys.executable)
            pythonw_exe = os.path.join(exe_dir, "pythonw.exe")
            target_exe = pythonw_exe if os.path.exists(pythonw_exe) else sys.executable
            flags = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt" else 0
            )
            subprocess.Popen(
                [target_exe] + sys.argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=flags,
            )
        except Exception:
            pass
        os._exit(0)
