import os
import sys
import subprocess
from typing import Tuple

TASK_NAME = "TikTokTracker_AutoScan"

def get_pythonw_path() -> str:
    """Tìm đường dẫn tới pythonw.exe để chạy ngầm hoàn toàn không hiện cửa sổ đen CMD"""
    exe_dir = os.path.dirname(sys.executable)
    pw = os.path.join(exe_dir, "pythonw.exe")
    return pw if os.path.exists(pw) else sys.executable

def get_script_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "auto_scan_cli.py")

def register_windows_task(interval_minutes: int = 30) -> Tuple[bool, str]:
    """Đăng ký lịch tự động chạy ngầm vào Windows Task Scheduler"""
    interval_minutes = max(5, min(interval_minutes, 1440))
    pythonw = get_pythonw_path()
    script = get_script_path()

    if not os.path.exists(script):
        return False, f"Không tìm thấy file: {script}"

    # Command line chuẩn Windows schtasks
    cmd_tr = f'"{pythonw}" "{script}"'
    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", cmd_tr,
        "/sc", "minute",
        "/mo", str(interval_minutes),
        "/f"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if res.returncode == 0:
            return True, f"Đã lên lịch thành công cho Windows tự động quét mỗi {interval_minutes} phút."
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"Lỗi tạo lịch Windows: {err}"
    except Exception as e:
        return False, str(e)

def remove_windows_task() -> Tuple[bool, str]:
    """Hủy lịch tự động chạy ngầm khỏi Windows Task Scheduler"""
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if res.returncode == 0:
            return True, "Đã hủy lịch tự động quét trên Windows."
        else:
            err = res.stderr.strip() or res.stdout.strip()
            if "cannot find" in err.lower() or "không tìm thấy" in err.lower():
                return True, "Lịch chưa từng được tạo hoặc đã hủy trước đó."
            return False, f"Lỗi hủy lịch Windows: {err}"
    except Exception as e:
        return False, str(e)

def is_windows_task_registered() -> bool:
    """Kiểm tra xem lịch Windows Task Scheduler hiện có đang bật không"""
    cmd = ["schtasks", "/query", "/tn", TASK_NAME]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        return res.returncode == 0
    except Exception:
        return False

