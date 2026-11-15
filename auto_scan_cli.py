import os
import sys
import json
import time
import random
import asyncio
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="ignore")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="ignore")

from playwright.async_api import async_playwright
from core.config import load_config, DATA_DIR, EXPORTS_DIR
from core.database import Database
from core.excel_exporter import ExcelExporter
from core.scanner import TikTokScraper, parse_cookie_pool, parse_proxy, STEALTH_JS

LOG_FILE = os.path.join(DATA_DIR, "auto_scan.log")

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

async def run_scan_async():
    db = Database()
    cfg = load_config()
    channels = db.get_all_channels()
    total = len(channels)

    if total == 0:
        log("⚠️ Danh sách kênh trống, không có gì để quét.")
        return

    delay_min = cfg.get("delay_min", 1.5)
    delay_max = cfg.get("delay_max", 3.0)
    proxies = cfg.get("proxies", [])
    use_proxy = cfg.get("use_proxy", False) and len(proxies) > 0
    retry_count = cfg.get("retry_count", 2)
    timeout_sec = cfg.get("timeout", 20)

    cookie_str = cfg.get("tiktok_cookie", "").strip()
    cookie_pool = parse_cookie_pool(cookie_str)

    cfg_threads = cfg.get("threads", 3)
    num_workers = max(1, min(cfg_threads, total, 10))

    log(f"🚀 BẮT ĐẦU TỰ ĐỘNG QUÉT: {total} kênh với {num_workers} luồng song song (Proxy: {use_proxy}, Cookies: {len(cookie_pool)} acc)...")

    queue = asyncio.Queue()
    for ch in channels:
        queue.put_nowait(ch)

    success_count = 0
    error_count = 0
    lock = asyncio.Lock()
    scraper = TikTokScraper(timeout=timeout_sec)
    t_start = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage"
            ]
        )

        async def worker_loop(worker_id: int):
            nonlocal success_count, error_count

            worker_proxy = None
            if use_proxy and proxies:
                worker_proxy = parse_proxy(proxies[worker_id % len(proxies)])

            worker_cookies = None
            if cookie_pool:
                worker_cookies = cookie_pool[worker_id % len(cookie_pool)]

            context = await browser.new_context(
                proxy=worker_proxy,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="vi-VN",
                viewport={"width": 1280, "height": 720}
            )
            await context.add_init_script(STEALTH_JS)

            if worker_cookies:
                try:
                    await context.add_cookies(worker_cookies)
                except Exception:
                    pass

            while True:
                try:
                    ch = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                username = ch['username']
                attempt = 0
                success = False
                stats = None
                videos = []
                msg = ""

                while attempt <= retry_count and not success:
                    attempt += 1
                    try:
                        success, stats, videos, msg = await scraper.scan_single_channel_async(context, username)
                        if success and stats:
                            break
                        elif attempt <= retry_count:
                            await asyncio.sleep(1.0)
                    except Exception as e:
                        msg = str(e)
                        if attempt <= retry_count:
                            await asyncio.sleep(1.0)

                async with lock:
                    if success and stats:
                        success_count += 1
                        db.update_channel_info(
                            username=stats.get('username', username),
                            nickname=stats.get('nickname', username),
                            avatar_url=stats.get('avatar_url', ''),
                            bio=stats.get('bio', ''),
                            is_verified=stats.get('is_verified', 0),
                            status="Hoạt động"
                        )
                        db.save_snapshot(
                            channel_id=ch['id'],
                            username=stats.get('username', username),
                            stats=stats,
                            videos=videos or []
                        )
                        flw_cnt = stats.get('follower_count', 0)
                        hrt_cnt = stats.get('heart_count', 0)
                        log(f"  [L{worker_id+1}] ✅ @{username}: {flw_cnt:,} Flw | {hrt_cnt:,} Tym | {len(videos)} Vids")
                    else:
                        error_count += 1
                        db.update_channel_info(
                            username=username,
                            nickname=ch.get('nickname', ''),
                            avatar_url=ch.get('avatar_url', ''),
                            bio=ch.get('bio', ''),
                            is_verified=ch.get('is_verified', 0),
                            status=f"Lỗi: {msg}"
                        )
                        log(f"  [L{worker_id+1}] ❌ @{username}: {msg}")

                queue.task_done()
                sleep_sec = random.uniform(delay_min, delay_max)
                await asyncio.sleep(sleep_sec)

            try:
                await context.close()
            except Exception:
                pass

        tasks = [asyncio.create_task(worker_loop(w_id)) for w_id in range(num_workers)]
        await asyncio.gather(*tasks, return_exceptions=True)
        await browser.close()

    elapsed = time.time() - t_start
    log(f"🎉 HOÀN THÀNH ĐỢT QUÉT NGẦM: {success_count} thành công, {error_count} lỗi trong {elapsed:.1f}s.")

    # Tự động xuất file Excel báo cáo
    try:
        exporter = ExcelExporter(db)
        filepath = exporter.export_growth_report()
        log(f"📊 Đã tự động xuất báo cáo Excel: {os.path.basename(filepath)}")
    except Exception as e:
        log(f"⚠️ Lỗi xuất file Excel: {e}")

def main():
    try:
        asyncio.run(run_scan_async())
    except Exception as e:
        log(f"❌ Lỗi tiến trình auto scan: {e}")

if __name__ == "__main__":
    main()

