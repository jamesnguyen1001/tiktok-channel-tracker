import sys
import os
import subprocess
import importlib.util

# Set working directory to project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

REQUIRED_MODULES = [
    ("PyQt6", "PyQt6"),
    ("playwright", "playwright"),
    ("openpyxl", "openpyxl"),
    ("requests", "requests"),
    ("PIL", "pillow"),
    ("numpy", "numpy"),
]


def ensure_environment():
    """Tự động kiểm tra và cài đặt các thư viện & trình duyệt còn thiếu trên máy mới"""
    missing = []
    for mod_name, pkg_name in REQUIRED_MODULES:
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)

    if missing:
        print(f"[Auto-Setup] Dang tu dong cai dat thu vien con thieu: {', '.join(missing)}...")
        req_file = os.path.join(BASE_DIR, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)

    # Kiểm tra xem trình duyệt Chromium của Playwright đã được tải chưa
    pw_marker = os.path.join(BASE_DIR, "data", ".playwright_ready")
    if not os.path.exists(pw_marker):
        try:
            os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
            pw_browsers = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
            has_chromium = os.path.isdir(pw_browsers) and any(
                d.startswith("chromium") for d in os.listdir(pw_browsers)
            )
            if not has_chromium:
                print("[Auto-Setup] Dang tai trinh duyet Chromium cho Playwright (chi chay 1 lan dau)...")
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            with open(pw_marker, "w", encoding="utf-8") as f:
                f.write("ok")
        except Exception as e:
            print(f"[Auto-Setup] Luu y khi kiem tra Playwright: {e}")


def main():
    ensure_environment()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from ui.main_window import MainWindow

    # Enable High DPI Scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("TikTok Channel Growth Tracker")
    app.setOrganizationName("TikTokTracker")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
