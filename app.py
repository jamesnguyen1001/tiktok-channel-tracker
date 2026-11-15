import sys
import os
import subprocess
import importlib.util

# Set working directory to project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Khi chạy bằng pythonw.exe (không có CMD), stdout/stderr là None -> chuyển hướng vào devnull để tránh lỗi print()
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="ignore")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="ignore")

NO_WINDOW_FLAG = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

REQUIRED_MODULES = [
    ("PyQt6", "PyQt6"),
    ("playwright", "playwright"),
    ("openpyxl", "openpyxl"),
    ("requests", "requests"),
    ("PIL", "pillow"),
    ("numpy", "numpy"),
]


def detach_from_console_if_needed():
    """
    Nếu người dùng mở bằng python.exe (có cửa sổ CMD đen),
    tự động chuyển sang chạy bằng pythonw.exe (chỉ hiện giao diện GUI) và đóng ngay cửa sổ CMD.
    """
    if os.name != "nt":
        return
    exe_name = os.path.basename(sys.executable).lower()
    if exe_name == "python.exe" and os.environ.get("TIKTOK_TRACKER_NO_DETACH") != "1":
        pythonw_exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(pythonw_exe):
            try:
                env = os.environ.copy()
                env["TIKTOK_TRACKER_NO_DETACH"] = "1"
                subprocess.Popen(
                    [pythonw_exe, os.path.abspath(__file__)] + sys.argv[1:],
                    cwd=BASE_DIR,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                os._exit(0)
            except Exception:
                pass


def ensure_environment():
    """Tự động kiểm tra và cài đặt các thư viện & trình duyệt còn thiếu trên máy mới (chạy ngầm không hiện CMD)"""
    missing = []
    for mod_name, pkg_name in REQUIRED_MODULES:
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)

    if missing:
        req_file = os.path.join(BASE_DIR, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                creationflags=NO_WINDOW_FLAG
            )
        else:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing,
                creationflags=NO_WINDOW_FLAG
            )

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
                subprocess.check_call(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    creationflags=NO_WINDOW_FLAG
                )
            with open(pw_marker, "w", encoding="utf-8") as f:
                f.write("ok")
        except Exception:
            pass


def main():
    detach_from_console_if_needed()
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
    if os.name == "nt":
        try:
            import ctypes
            hwnd = int(window.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
