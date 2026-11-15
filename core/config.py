import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "threads": 6,
    "delay_min": 0.2,
    "delay_max": 0.5,
    "timeout": 15,
    "proxies": [],
    "use_proxy": False,
    "tiktok_cookie": "",
    "tiktok_cookies": [],
    "auto_export_excel": False,
    "retry_count": 1,
    "headless": True,
    "block_heavy_resources": True,
    "auto_scan_enabled": False,
    "auto_scan_interval_minutes": 30
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config_data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")
