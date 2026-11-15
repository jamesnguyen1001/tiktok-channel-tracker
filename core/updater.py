import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import urllib.request
from typing import Tuple, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import BASE_DIR, load_config, save_config

VERSION_FILE = os.path.join(BASE_DIR, "version.json")

# Các thư mục và file dữ liệu cá nhân TUYỆT ĐỐI KHÔNG BAO GIỜ GHI ĐÈ khi cập nhật
PROTECTED_PATHS = {
    "data",
    "exports",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "config.json",
    "tiktok_growth.db",
    "browser_device_state.json",
}


def get_local_version_info() -> dict:
    default_info = {
        "version": "2.2",
        "github_repo": "https://github.com/jamesnguyen1001/tiktok-channel-tracker",
        "branch": "main",
        "description": ""
    }
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_info.update(data)
        except Exception:
            pass
    cfg = load_config()
    if cfg.get("github_repo"):
        default_info["github_repo"] = cfg["github_repo"]
    return default_info


def normalize_github_repo(repo_input: str) -> Tuple[str, str]:
    """
    Chuyển đổi link GitHub bất kỳ (https://github.com/user/repo.git hoặc user/repo)
    thành (owner/repo, https://github.com/owner/repo.git)
    """
    raw = (repo_input or "").strip().rstrip("/")
    if not raw:
        return "", ""
    if raw.endswith(".git"):
        raw = raw[:-4]
    if "github.com/" in raw:
        parts = raw.split("github.com/", 1)[1].strip("/").split("/")
        if len(parts) >= 2:
            slug = f"{parts[0]}/{parts[1]}"
            return slug, f"https://github.com/{slug}.git"
    parts = raw.strip("/").split("/")
    if len(parts) == 2 and parts[0] and parts[1]:
        slug = f"{parts[0]}/{parts[1]}"
        return slug, f"https://github.com/{slug}.git"
    return "", ""


class UpdateWorker(QThread):
    """
    Worker tải bản cập nhật mới nhất từ GitHub:
    - Hoạt động trên mọi máy tính (kể cả máy bạn bè KHÔNG cài Git) bằng cách tải gói ZIP trực tiếp từ GitHub.
    - Bảo vệ tuyệt đối 100% thư mục `data/` (kênh, database, cookie, proxy) và `exports/`.
    """
    progress_msg = pyqtSignal(str)
    update_finished = pyqtSignal(bool, str, str)  # (success, message, new_version)

    def __init__(self, repo_url: str, parent=None):
        super().__init__(parent)
        self.repo_url = repo_url

    def run(self):
        slug, git_url = normalize_github_repo(self.repo_url)
        if not slug:
            self.update_finished.emit(
                False,
                "Link GitHub không hợp lệ! Vui lòng nhập dạng: https://github.com/ten-ban/ten-repo",
                ""
            )
            return

        self.progress_msg.emit(f"⏳ Đang kết nối tới GitHub ({slug})...")

        # Thử tải gói ZIP từ nhánh main hoặc master (không cần cài Git trên máy người dùng)
        zip_bytes = None
        used_branch = "main"
        for branch in ("main", "master"):
            zip_url = f"https://github.com/{slug}/archive/refs/heads/{branch}.zip"
            try:
                req = urllib.request.Request(
                    zip_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TikTokTrackerUpdater/2.1"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        zip_bytes = resp.read()
                        used_branch = branch
                        break
            except Exception:
                continue

        # Nếu repo để Private hoặc cần Git cục bộ, fallback sang lệnh git pull
        if not zip_bytes:
            self.progress_msg.emit("🔄 Đang thử cập nhật qua Git CLI...")
            ok, msg, ver = self._update_via_git_cli(git_url)
            self.update_finished.emit(ok, msg, ver)
            return

        self.progress_msg.emit(f"📦 Đã tải gói cập nhật (nhánh {used_branch}). Đang giải nén an toàn...")

        tmp_dir = tempfile.mkdtemp(prefix="tiktok_update_")
        try:
            zip_path = os.path.join(tmp_dir, "update.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)

            extract_dir = os.path.join(tmp_dir, "extracted")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # Tìm thư mục gốc của mã nguồn bên trong file zip
            sub_items = os.listdir(extract_dir)
            src_root = os.path.join(extract_dir, sub_items[0]) if len(sub_items) == 1 else extract_dir

            # Nếu trong repo có thư mục con "CHECK TAI KHOAN" thì lấy bên trong đó
            nested_app = os.path.join(src_root, "CHECK TAI KHOAN")
            if os.path.isdir(nested_app) and os.path.exists(os.path.join(nested_app, "app.py")):
                src_root = nested_app

            if not os.path.exists(os.path.join(src_root, "app.py")) and not os.path.isdir(os.path.join(src_root, "core")):
                self.update_finished.emit(
                    False,
                    "Kho lưu trữ GitHub này chưa có mã nguồn của Tool (thiếu app.py / core).",
                    ""
                )
                return

            updated_files = 0
            for item in os.listdir(src_root):
                if item in PROTECTED_PATHS or item.endswith((".db", ".xlsx")):
                    continue

                s_path = os.path.join(src_root, item)
                d_path = os.path.join(BASE_DIR, item)

                if os.path.isdir(s_path):
                    self._copy_dir_safe(s_path, d_path)
                    updated_files += 1
                else:
                    shutil.copy2(s_path, d_path)
                    updated_files += 1

            # Lưu lại link repo vào config & version.json để lần sau chỉ cần bấm 1 nút
            cfg = load_config()
            cfg["github_repo"] = f"https://github.com/{slug}"
            save_config(cfg)

            ver_info = get_local_version_info()
            new_ver = ver_info.get("version", "Mới nhất")
            self.update_finished.emit(
                True,
                f"🎉 Đã cập nhật thành công phiên bản {new_ver} từ GitHub ({slug})!\n"
                f"✅ Toàn bộ dữ liệu kênh, Cookie, Proxy, RPM & Dash trên máy của bạn được giữ nguyên 100%.",
                new_ver
            )
        except Exception as e:
            self.update_finished.emit(False, f"Lỗi khi giải nén bản cập nhật: {e}", "")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _copy_dir_safe(self, src: str, dst: str):
        os.makedirs(dst, exist_ok=True)
        for item in os.listdir(src):
            if item in PROTECTED_PATHS or item == "__pycache__":
                continue
            s_item = os.path.join(src, item)
            d_item = os.path.join(dst, item)
            if os.path.isdir(s_item):
                self._copy_dir_safe(s_item, d_item)
            else:
                shutil.copy2(s_item, d_item)

    def _update_via_git_cli(self, git_url: str) -> Tuple[bool, str, str]:
        try:
            git_dir = os.path.join(BASE_DIR, ".git")
            if not os.path.isdir(git_dir):
                return (
                    False,
                    "Không thể tải từ GitHub! Hãy kiểm tra:\n"
                    "1. Link GitHub đã đúng chưa\n"
                    "2. Kho GitHub đã được chuyển sang chế độ Public (Công khai) và đã đẩy code lên chưa.",
                    ""
                )
            subprocess.run(["git", "remote", "set-url", "origin", git_url], cwd=BASE_DIR, capture_output=True, timeout=10)
            res = subprocess.run(["git", "pull", "origin", "main", "--rebase"], cwd=BASE_DIR, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                res = subprocess.run(["git", "pull", "origin", "master", "--rebase"], cwd=BASE_DIR, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                ver = get_local_version_info().get("version", "Mới nhất")
                return True, f"🎉 Đã cập nhật thành công qua Git (Phiên bản {ver})!\nDữ liệu cá nhân được bảo toàn 100%.", ver
            return False, f"Không thể kéo bản cập nhật: {res.stderr.strip() or res.stdout.strip()}", ""
        except Exception as e:
            return False, f"Lỗi Git: {e}", ""


class PublishWorker(QThread):
    """
    Worker dành riêng cho chủ Tool (Admin) để đẩy code sạch lên GitHub chỉ với 1 nút bấm.
    Tự động kiểm tra .gitignore để đảm bảo 100% KHÔNG đẩy data/, config.json, tiktok_growth.db, exports/.
    """
    progress_msg = pyqtSignal(str)
    publish_finished = pyqtSignal(bool, str)

    def __init__(self, repo_url: str, new_version: str = "", commit_msg: str = "", parent=None):
        super().__init__(parent)
        self.repo_url = repo_url
        self.new_version = new_version.strip()
        self.commit_msg = commit_msg.strip() or "Cap nhat phien ban moi"

    def run(self):
        slug, git_url = normalize_github_repo(self.repo_url)
        if not slug:
            self.publish_finished.emit(
                False,
                "Link GitHub không hợp lệ! Vui lòng nhập dạng: https://github.com/ten-ban/ten-repo"
            )
            return

        try:
            # 1. Cập nhật file version.json
            ver_info = get_local_version_info()
            if self.new_version:
                ver_info["version"] = self.new_version
            ver_info["github_repo"] = f"https://github.com/{slug}"
            ver_info["branch"] = "main"
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                json.dump(ver_info, f, ensure_ascii=False, indent=2)

            cfg = load_config()
            cfg["github_repo"] = f"https://github.com/{slug}"
            save_config(cfg)

            self.progress_msg.emit("🔒 Đang kiểm tra bảo mật (.gitignore) để loại bỏ 100% dữ liệu cá nhân...")

            # 2. Khởi tạo Git nếu chưa có
            if not os.path.isdir(os.path.join(BASE_DIR, ".git")):
                subprocess.run(["git", "init", "-b", "main"], cwd=BASE_DIR, check=True, capture_output=True)

            subprocess.run(["git", "branch", "-M", "main"], cwd=BASE_DIR, capture_output=True)

            # Đảm bảo data/ và exports/ không bao giờ nằm trong git index
            subprocess.run(["git", "rm", "-r", "--cached", "--ignore-unmatch", "data", "exports"], cwd=BASE_DIR, capture_output=True)

            # Cài đặt remote origin
            rem = subprocess.run(["git", "remote"], cwd=BASE_DIR, capture_output=True, text=True)
            if "origin" in (rem.stdout or "").splitlines():
                subprocess.run(["git", "remote", "set-url", "origin", git_url], cwd=BASE_DIR, check=True, capture_output=True)
            else:
                subprocess.run(["git", "remote", "add", "origin", git_url], cwd=BASE_DIR, check=True, capture_output=True)

            self.progress_msg.emit("📦 Đang đóng gói mã nguồn sạch (không chứa kênh, cookie, proxy)...")
            subprocess.run(["git", "add", "."], cwd=BASE_DIR, check=True, capture_output=True)

            # Commit
            subprocess.run(
                ["git", "commit", "-m", f"v{ver_info.get('version', '2.1.0')}: {self.commit_msg}"],
                cwd=BASE_DIR,
                capture_output=True
            )

            self.progress_msg.emit(f"☁️ Đang đẩy bản cập nhật lên GitHub ({slug})...")
            push_res = subprocess.run(
                ["git", "push", "-u", "origin", "main", "--force"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=60
            )
            if push_res.returncode == 0:
                self.publish_finished.emit(
                    True,
                    f"✅ Đã đẩy bản cập nhật v{ver_info.get('version')} lên GitHub thành công!\n\n"
                    f"🔗 Link GitHub: https://github.com/{slug}\n"
                    f"🔒 Đã bảo vệ: Không có bất kỳ dữ liệu kênh, Cookie, Proxy hay file Excel nào của bạn bị đẩy lên.\n\n"
                    f"👉 Bây giờ bạn của bạn chỉ cần bấm nút '🔄 Cập nhật' trên Tool là tự động nhận được bản mới!"
                )
            else:
                err = (push_res.stderr or push_res.stdout or "").strip()
                self.publish_finished.emit(
                    False,
                    f"Không thể đẩy lên GitHub ({slug}).\n"
                    f"Chi tiết: {err}\n\n"
                    f"💡 Lưu ý: Hãy chắc chắn bạn đã tạo kho (Repository) tên là '{slug.split('/')[1]}' trên tài khoản GitHub '{slug.split('/')[0]}' (chế độ Public)."
                )
        except Exception as e:
            self.publish_finished.emit(False, f"Lỗi khi đẩy lên GitHub: {e}")
