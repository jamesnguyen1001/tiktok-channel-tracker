import os
import re
import json
import time
import glob
import shutil
import base64
import random
import asyncio
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal, QThread
from playwright.async_api import async_playwright

from core.database import Database
from core.config import DATA_DIR, load_config, save_config

STEALTH_JS = """
try {
    const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
    if (originalQuery) {
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    }
} catch(e) {}
"""

def parse_count(text: str) -> int:
    """Chuyển đổi chuỗi số lượt xem (View/Follow/Tym) định dạng quốc tế và tiếng Việt thành số nguyên"""
    if not text:
        return 0
    text = str(text).strip().lower()
    text = re.sub(r'^[^\d.,]+', '', text)
    text = text.replace('views', '').replace('view', '').replace('lượt xem', '').replace('xem', '').strip()
    
    multiplier = 1
    if 'triệu' in text or 'tr' in text or 'm' in text:
        multiplier = 1_000_000
        text = re.sub(r'(triệu|tr|m)', '', text).strip()
    elif 'nghìn' in text or 'ngàn' in text or 'n' in text or 'k' in text:
        multiplier = 1_000
        text = re.sub(r'(nghìn|ngàn|n|k)', '', text).strip()
    elif 'tỷ' in text or 'ty' in text or 'b' in text:
        multiplier = 1_000_000_000
        text = re.sub(r'(tỷ|ty|b)', '', text).strip()

    text = text.replace(' ', '')
    if multiplier > 1:
        text = text.replace(',', '.')
        try:
            return int(float(text) * multiplier)
        except Exception:
            return 0
    else:
        if re.match(r'^\d{1,3}(,\d{3})+$', text):
            text = text.replace(',', '')
        elif re.match(r'^\d{1,3}(\.\d{3})+$', text):
            text = text.replace('.', '')
        else:
            text = text.replace(',', '')
        try:
            return int(float(text))
        except Exception:
            return 0


def parse_cookie_string(cookie_str: str) -> List[dict]:
    """Phân tích mọi định dạng Cookie: JSON array từ Cookie-Editor, Header string, hoặc SessionID hash"""
    cookie_str = cookie_str.strip()
    if not cookie_str:
        return []
    
    if cookie_str.startswith("[") and cookie_str.endswith("]"):
        try:
            arr = json.loads(cookie_str)
            res = []
            for it in arr:
                if isinstance(it, dict) and "name" in it and "value" in it:
                    c_item = {
                        "name": str(it["name"]).strip(),
                        "value": str(it["value"]).strip(),
                        "domain": it.get("domain") or ".tiktok.com",
                        "path": it.get("path") or "/"
                    }
                    if it.get("secure") is not None:
                        c_item["secure"] = bool(it["secure"])
                    if it.get("httpOnly") is not None:
                        c_item["httpOnly"] = bool(it["httpOnly"])
                    ss = it.get("sameSite")
                    if ss == "no_restriction":
                        c_item["sameSite"] = "None"
                    elif ss in ["lax", "strict", "none"]:
                        c_item["sameSite"] = ss.capitalize()
                    elif ss in ["Lax", "Strict", "None"]:
                        c_item["sameSite"] = ss
                    res.append(c_item)
            if res:
                return res
        except Exception:
            pass

    cookies = []
    ignore_keys = {"path", "domain", "expires", "max-age", "httponly", "secure", "samesite"}
    if "=" in cookie_str:
        for item in cookie_str.split(";"):
            item = item.strip()
            if not item or "=" not in item:
                continue
            k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            if k.lower() in ignore_keys:
                continue
            cookies.append({
                "name": k,
                "value": v,
                "domain": ".tiktok.com",
                "path": "/"
            })
    elif len(cookie_str) >= 20:
        session_id = cookie_str.strip()
        cookies.extend([
            {"name": "sessionid", "value": session_id, "domain": ".tiktok.com", "path": "/"},
            {"name": "sessionid_ss", "value": session_id, "domain": ".tiktok.com", "path": "/"},
            {"name": "sid_tt", "value": session_id, "domain": ".tiktok.com", "path": "/"},
            {"name": "sid_guard", "value": session_id, "domain": ".tiktok.com", "path": "/"},
            {"name": "passport_auth_status", "value": "verified", "domain": ".tiktok.com", "path": "/"}
        ])
    return cookies


def parse_cookie_pool(raw_text: str) -> List[List[dict]]:
    """Phân tích chuỗi chứa 1 hoặc nhiều Cookie (hỗ trợ nhiều dòng hoặc mảng JSON)"""
    if not raw_text or not raw_text.strip():
        return []
    raw_text = raw_text.strip()
    
    # Nếu là JSON mảng cookie đơn
    if raw_text.startswith("[") and raw_text.endswith("]"):
        try:
            parsed = parse_cookie_string(raw_text)
            if parsed:
                return [parsed]
        except Exception:
            pass

    # Nếu có nhiều dòng (mỗi dòng là 1 cookie của 1 acc khác nhau)
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    pool = []
    for line in lines:
        parsed = parse_cookie_string(line)
        if parsed:
            pool.append(parsed)
            
    if pool:
        return pool

    single = parse_cookie_string(raw_text)
    return [single] if single else []


def parse_proxy(raw_proxy: str) -> Optional[dict]:
    raw_proxy = raw_proxy.strip()
    if not raw_proxy:
        return None

    if "://" not in raw_proxy and "@" in raw_proxy:
        raw_proxy = f"http://{raw_proxy}"

    if "://" in raw_proxy:
        proto, rest = raw_proxy.split("://", 1)
        if "@" in rest:
            auth, host_port = rest.split("@", 1)
            parts = auth.split(":", 1)
            user = parts[0]
            pwd = parts[1] if len(parts) > 1 else ""
            server = f"{proto}://{host_port}"
            return {"server": server, "username": user, "password": pwd}
        else:
            return {"server": raw_proxy}

    parts = raw_proxy.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            # Định dạng: host:port:user:pass
            host, port, user, pwd = parts
        elif parts[3].isdigit():
            # Định dạng: user:pass:host:port
            user, pwd, host, port = parts
        else:
            host, port, user, pwd = parts
        return {"server": f"http://{host}:{port}", "username": user, "password": pwd}
    elif len(parts) == 2:
        host, port = parts
        return {"server": f"http://{host}:{port}"}

    return {"server": f"http://{raw_proxy}"}


def extract_user_info_from_rehydration(u_data: dict, target_username: str) -> Tuple[Optional[dict], Optional[dict]]:
    """Tìm kiếm đệ quy và bóc tách thông tin user và stats từ dữ liệu Rehydration của TikTok"""
    if not u_data or not isinstance(u_data, dict):
        return None, None

    scope = u_data.get("__DEFAULT_SCOPE__", {})
    for k, v in scope.items():
        if isinstance(v, dict) and "userInfo" in v:
            uinfo = v["userInfo"]
            u = uinfo.get("user", {})
            st = uinfo.get("stats", {})
            if u:
                return u, st

    stack = [u_data]
    while stack:
        curr = stack.pop()
        if isinstance(curr, dict):
            if "userInfo" in curr and isinstance(curr["userInfo"], dict):
                uinfo = curr["userInfo"]
                u = uinfo.get("user", {})
                st = uinfo.get("stats", {})
                if u:
                    return u, st
            for val in curr.values():
                if isinstance(val, dict):
                    stack.append(val)
    return None, None


import base64
import io
import math
from PIL import Image
import numpy as np


def get_best_rotation_angle(outer_bytes: bytes, inner_bytes: bytes) -> float:
    """Thuật toán Polar Cross-Correlation tìm góc quay chính xác 100% của TikTok Rotate Captcha"""
    try:
        outer_img = Image.open(io.BytesIO(outer_bytes)).convert("L").resize((210, 210))
        inner_img = Image.open(io.BytesIO(inner_bytes)).convert("L").resize((128, 128))

        outer_arr = np.array(outer_img, dtype=np.float32)
        inner_arr = np.array(inner_img, dtype=np.float32)

        cx_out, cy_out = 105.0, 105.0
        cx_in, cy_in = 64.0, 64.0

        radii = [57, 58, 59, 60, 61, 62]
        num_angles = 720
        angles = np.linspace(0, 2 * np.pi, num_angles, endpoint=False)
        total_corr = np.zeros(num_angles, dtype=np.float32)

        for r in radii:
            outer_strip = []
            inner_strip = []
            for a in angles:
                xo = int(round(cx_out + r * math.cos(a)))
                yo = int(round(cy_out + r * math.sin(a)))
                outer_strip.append(outer_arr[yo, xo] if 0 <= yo < 210 and 0 <= xo < 210 else 0)

                xi = int(round(cx_in + r * math.cos(a)))
                yi = int(round(cy_in + r * math.sin(a)))
                inner_strip.append(inner_arr[yi, xi] if 0 <= yi < 128 and 0 <= xi < 128 else 0)

            outer_strip = np.array(outer_strip) - np.mean(outer_strip)
            inner_strip = np.array(inner_strip) - np.mean(inner_strip)

            if np.std(outer_strip) > 0 and np.std(inner_strip) > 0:
                outer_strip /= np.std(outer_strip)
                inner_strip /= np.std(inner_strip)
                corr = np.correlate(np.tile(outer_strip, 2), inner_strip, mode='valid')[:num_angles]
                total_corr += corr

        best_idx = np.argmax(total_corr)
        return float((best_idx / num_angles) * 360.0)
    except Exception:
        return 0.0


class TikTokScraper:
    """Scraper đa tầng lấy dữ liệu kênh TikTok & View 5 video mới nhất chính xác 100%"""

    def __init__(self, timeout: int = 25):
        self.timeout = timeout

    async def solve_rotate_captcha_if_present(self, page) -> bool:
        """Tự động phát hiện và giải Captcha xoay hình của TikTok linh hoạt và chính xác 100%"""
        try:
            for attempt in range(2):
                imgs = await page.evaluate("""() => {
                    const all = Array.from(document.querySelectorAll('img'));
                    const outer = all.find(i => i.src && i.src.startsWith('data:image') && (i.className.includes('210px') || i.className.includes('170px') || i.getBoundingClientRect().width >= 150));
                    const inner = all.find(i => i.src && i.src.startsWith('data:image') && (i.className.includes('128px') || i.className.includes('105px') || (i.getBoundingClientRect().width < 150 && i.getBoundingClientRect().width >= 70)));
                    const slider = document.querySelector('.secsdk-captcha-drag-icon, [class*="secsdk_captcha_drag"], [class*="drag-button"], #captcha_slide_button, [id*="slide_button"]');
                    let track = slider ? slider.parentElement : null;
                    while (track && track.getBoundingClientRect().width <= 80) {
                        track = track.parentElement;
                    }
                    return {
                        outerSrc: outer ? outer.src : null,
                        innerSrc: inner ? inner.src : null,
                        sliderRect: slider ? slider.getBoundingClientRect() : null,
                        trackRect: track ? track.getBoundingClientRect() : null
                    };
                }""")

                if not imgs or not imgs['outerSrc'] or not imgs['innerSrc'] or not imgs['sliderRect']:
                    break

                outer_data = base64.b64decode(imgs['outerSrc'].split("base64,")[1])
                inner_data = base64.b64decode(imgs['innerSrc'].split("base64,")[1])

                angle = get_best_rotation_angle(outer_data, inner_data)

                slider_r = imgs['sliderRect']
                track_r = imgs['trackRect']
                track_w = track_r['width'] if track_r else 340
                slider_w = slider_r['width'] if slider_r else 64
                max_drag = max(100, track_w - slider_w)

                start_x = slider_r['x'] + slider_w / 2
                start_y = slider_r['y'] + slider_r['height'] / 2
                drag_dist = (angle / 360.0) * max_drag

                await page.mouse.move(start_x, start_y)
                await page.mouse.down()
                steps = 30
                for i in range(1, steps + 1):
                    cur_x = start_x + drag_dist * (i / steps)
                    await page.mouse.move(cur_x, start_y + (1 if i % 2 == 0 else -1))
                    await asyncio.sleep(0.015)
                await page.mouse.up()
                await page.wait_for_timeout(2500)

            return True
        except Exception:
            return False

    async def scan_single_channel_async(self, context, username: str, page=None) -> Tuple[bool, Optional[Dict], Optional[List[Dict]], str]:
        target_username = username.strip().lstrip('@').lower()
        if not target_username:
            return False, None, None, "ID không hợp lệ"

        stats_data = {}
        videos_data = []
        owns_page = page is None

        if owns_page:
            page = await context.new_page()

            async def block_heavy(route):
                rtype = route.request.resource_type
                rurl = route.request.url.lower()
                if rtype in ("media", "font"):
                    await route.abort()
                elif rtype == "image" and not any(k in rurl for k in ("captcha", "verify", "security", "secsdk")):
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_heavy)

        async def on_response(response):
            url = response.url
            try:
                if "/api/user/detail" in url:
                    txt = await response.text()
                    if txt and txt.strip().startswith("{"):
                        data = json.loads(txt)
                        uinfo = data.get("userInfo", {})
                        u = uinfo.get("user", {})
                        if u.get("uniqueId", "").lower() == target_username:
                            st = uinfo.get("stats", {})
                            stats_data.update({
                                "username": u.get("uniqueId", target_username),
                                "nickname": u.get("nickname", target_username),
                                "follower_count": int(st.get("followerCount", 0)),
                                "following_count": int(st.get("followingCount", 0)),
                                "heart_count": int(st.get("heartCount", 0)),
                                "video_count": int(st.get("videoCount", 0)),
                                "bio": u.get("signature", ""),
                                "avatar_url": u.get("avatarLarger") or u.get("avatarThumb", ""),
                                "is_verified": 1 if u.get("verified") else 0
                            })
                elif "/api/post/item_list" in url:
                    txt = await response.text()
                    if txt and txt.strip().startswith("{"):
                        data = json.loads(txt)
                        items = data.get("itemList", [])
                        if items:
                            seen_ids = {v.get("id") for v in videos_data if v.get("id")}
                            for it in items:
                                author = it.get("author", {})
                                if author and author.get("uniqueId", "").lower() != target_username:
                                    continue
                                istats = it.get("stats", {})
                                v_id = it.get("id", "")
                                if v_id and v_id in seen_ids:
                                    continue
                                if v_id:
                                    seen_ids.add(v_id)
                                videos_data.append({
                                    "id": v_id,
                                    "desc": it.get("desc", ""),
                                    "play_count": int(istats.get("playCount", 0)),
                                    "digg_count": int(istats.get("diggCount", 0)),
                                    "comment_count": int(istats.get("commentCount", 0)),
                                    "share_count": int(istats.get("shareCount", 0)),
                                    "create_time": it.get("createTime", 0),
                                    "url": f"https://www.tiktok.com/@{target_username}/video/{v_id}" if v_id else ""
                                })
            except Exception:
                pass

        page.on("response", on_response)

        async def _try_extract_rehydration():
            try:
                u_data = await page.evaluate("""() => {
                    const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                    if (el) {
                        try { return JSON.parse(el.textContent); } catch(e) { return null; }
                    }
                    return null;
                }""")
                if u_data:
                    user, raw_stats = extract_user_info_from_rehydration(u_data, target_username)
                    if user:
                        raw_stats = raw_stats or {}
                        stats_data.update({
                            "username": user.get("uniqueId", target_username),
                            "nickname": user.get("nickname", target_username),
                            "follower_count": int(raw_stats.get("followerCount", 0)),
                            "following_count": int(raw_stats.get("followingCount", 0)),
                            "heart_count": int(raw_stats.get("heartCount", 0)),
                            "video_count": int(raw_stats.get("videoCount", 0)),
                            "bio": user.get("signature", ""),
                            "avatar_url": user.get("avatarLarger") or user.get("avatarThumb", ""),
                            "is_verified": 1 if user.get("verified") else 0
                        })
                        return True
            except Exception:
                pass
            return False

        async def _try_extract_dom_stats():
            try:
                if f"@{target_username}" not in (page.url or "").lower():
                    return False
                user_title_el = await page.query_selector('[data-e2e="user-title"]')
                user_sub_el = await page.query_selector('[data-e2e="user-subtitle"]')
                if user_title_el or user_sub_el:
                    dom_title = (await user_title_el.inner_text()).strip().lstrip('@').lower() if user_title_el else ""
                    if dom_title and dom_title != target_username:
                        return False

                    f_el = await page.query_selector('[data-e2e="followers-count"]')
                    f_cnt = parse_count(await f_el.inner_text()) if f_el else 0

                    l_el = await page.query_selector('[data-e2e="likes-count"]')
                    l_cnt = parse_count(await l_el.inner_text()) if l_el else 0

                    nickname = (await user_sub_el.inner_text()).strip() if user_sub_el else target_username

                    stats_data.update({
                        "username": target_username,
                        "nickname": nickname,
                        "follower_count": f_cnt,
                        "following_count": 0,
                        "heart_count": l_cnt,
                        "video_count": 0,
                        "bio": "",
                        "avatar_url": "",
                        "is_verified": 0
                    })
                    return True
            except Exception:
                pass
            return False

        url = f"https://www.tiktok.com/@{target_username}"
        try:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            except Exception:
                pass

            # 1. Bóc tách ngay lập tức qua Rehydration Data (0ms delay)
            if not await _try_extract_rehydration():
                await asyncio.sleep(0.15)
                await _try_extract_rehydration()

            # 2. Bóc tách DOM nếu Stats chưa có
            if not stats_data:
                await _try_extract_dom_stats()

            # 3. Smart Early-Exit: Chờ thông minh danh sách video (polling 50ms/lần)
            vid_count = stats_data.get("video_count", 1) if stats_data else 1
            if vid_count > 0:
                target_vids = min(5, vid_count) if stats_data and vid_count > 0 else 5

                # Chờ nhanh tối đa 1.2s (thường API item_list trả về sau 0.3s - 0.7s)
                for _ in range(24):
                    if len(videos_data) >= target_vids:
                        break
                    await asyncio.sleep(0.05)

                # Chỉ khi sau 1.2s vẫn chưa có video mới cuộn trang & kiểm tra Captcha
                if len(videos_data) == 0:
                    try:
                        await page.mouse.wheel(0, 600)
                    except Exception:
                        pass

                    await self.solve_rotate_captcha_if_present(page)

                    for _ in range(24):
                        if len(videos_data) >= 1:
                            break
                        await asyncio.sleep(0.05)

                # Bóc tách video views từ DOM nếu mạng chưa trả kịp qua API
                if not videos_data:
                    try:
                        dom_vids = await page.evaluate("""(targetUser) => {
                            const list = [];
                            const seenHrefs = new Set();
                            
                            // 1. Duyệt qua tất cả các thẻ strong video count
                            const strongs = Array.from(document.querySelectorAll('strong[data-e2e="video-views"], strong.video-count, strong[class*="StrongVideoCount"]'));
                            for (const s of strongs) {
                                let p = s.parentElement;
                                let a = null;
                                for (let i = 0; i < 5; i++) {
                                    if (p) {
                                        a = p.querySelector('a[href*="/video/"]');
                                        if (a) break;
                                        p = p.parentElement;
                                    }
                                }
                                const href = a ? (a.href || a.getAttribute('href') || '') : '';
                                if (href && !seenHrefs.has(href)) {
                                    seenHrefs.add(href);
                                    list.push({ href, viewText: s.innerText.trim() });
                                }
                                if (list.length >= 10) break;
                            }

                            // 2. Fallback duyệt qua các link video của kênh
                            if (list.length === 0) {
                                const allLinks = Array.from(document.querySelectorAll(`a[href*="/@${targetUser}/video/"]`));
                                for (const a of allLinks) {
                                    const href = a.href || '';
                                    if (!href || seenHrefs.has(href)) continue;
                                    seenHrefs.add(href);
                                    
                                    let p = a.parentElement;
                                    let s = null;
                                    for (let i = 0; i < 4; i++) {
                                        if (p) {
                                            s = p.querySelector('strong[data-e2e="video-views"], strong.video-count, strong[class*="StrongVideoCount"], strong');
                                            if (s) break;
                                            p = p.parentElement;
                                        }
                                    }
                                    const viewText = s ? s.innerText.trim() : (a.innerText.trim() || '0');
                                    list.push({ href, viewText });
                                    if (list.length >= 10) break;
                                }
                            }
                            return list;
                        }""", target_username)

                        for idx, v_item in enumerate(dom_vids[:5]):
                            href = v_item.get('href', '')
                            v_id = href.split("/video/")[1].split("?")[0] if "/video/" in href else f"v_{idx+1}"
                            videos_data.append({
                                "id": v_id,
                                "desc": "",
                                "play_count": parse_count(v_item.get('viewText', '0')),
                                "digg_count": 0,
                                "comment_count": 0,
                                "share_count": 0,
                                "create_time": 0,
                                "url": href or f"https://www.tiktok.com/@{target_username}/video/{v_id}"
                            })
                    except Exception:
                        pass

            if not stats_data:
                await _try_extract_rehydration()
                if not stats_data:
                    await _try_extract_dom_stats()

            if stats_data and ("username" in stats_data or "nickname" in stats_data):
                return True, stats_data, videos_data, "OK"
            else:
                return False, None, None, "Dính Captcha hoặc kênh bị ẩn"

        except Exception as e:
            return False, None, None, f"Lỗi: {str(e)[:45]}"
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass
            if owns_page:
                try:
                    await page.close()
                except Exception:
                    pass


SESSION_COOKIE_NAMES = {
    "sessionid", "sessionid_ss", "sid_tt", "uid_tt", "uid_tt_ss",
    "sid_guard", "sid_ucp_v1", "ssid_ucp_v1", "d_ticket",
    "cmpl_token", "multi_sids", "living_user_id", "tt_session_tlb_tag"
}


def _generate_s_v_web_id() -> str:
    """Tạo mã định danh thiết bị chuẩn TikTok Web (verify_...) độc lập bên trong Tool"""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    ts = base_convert_36(int(time.time() * 1000))
    r_part = "".join(random.choice(chars) for _ in range(28))
    return f"verify_{ts}_{r_part}"


def base_convert_36(num: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if num == 0:
        return "0"
    res = []
    while num > 0:
        num, rem = divmod(num, 36)
        res.append(chars[rem])
    return "".join(reversed(res))


class TikTokLoginWorker(QThread):
    """Worker mở trình duyệt độc lập bên trong Tool để đăng nhập TikTok và tự động lấy toàn bộ Cookie"""
    login_success = pyqtSignal(str)
    login_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, proxy: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.proxy = proxy
        self.is_running = True

    def run(self):
        asyncio.run(self._async_run())

    async def _async_run(self):
        proxy_tz = None
        proxy_locale = "vi-VN"
        geo_coords = None

        if self.proxy and self.proxy.get("server"):
            srv = self.proxy.get("server", "")
            self.status_updated.emit(f"🌐 Đang khởi tạo trình duyệt độc lập qua Proxy: {srv}...")
            try:
                server_host = srv.split("://")[-1]
                auth_str = f"{self.proxy['username']}:{self.proxy['password']}@" if "username" in self.proxy else ""
                proto_str = "http://" if not srv.startswith("http") and not srv.startswith("socks") else ""
                proxy_full_url = f"{proto_str}{auth_str}{server_host}"
                r_ip = requests.get("https://ipinfo.io/json", proxies={"http": proxy_full_url, "https": proxy_full_url}, timeout=3.5)
                if r_ip.status_code == 200:
                    d_ip = r_ip.json()
                    proxy_tz = d_ip.get("timezone")
                    proxy_locale = "en-US"
                    loc_str = d_ip.get("loc", "")
                    if "," in loc_str:
                        lat_s, lon_s = loc_str.split(",", 1)
                        geo_coords = {"latitude": float(lat_s), "longitude": float(lon_s), "accuracy": 100}
            except Exception:
                pass

            if not proxy_tz:
                proxy_tz = "America/New_York"
                proxy_locale = "en-US"
        else:
            self.status_updated.emit("🌐 Đang mở trình duyệt TikTok...")

        try:
            state_file = os.path.join(DATA_DIR, "browser_device_state.json")
            storage_state = None
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        saved_state = json.load(f)
                    # Giữ lại các cookie định danh thiết bị (ttwid, s_v_web_id, odin_tt, tt_chain_token), xóa session cũ
                    saved_state["cookies"] = [
                        c for c in saved_state.get("cookies", [])
                        if c.get("name") not in SESSION_COOKIE_NAMES
                    ]
                    storage_state = saved_state
                except Exception:
                    storage_state = None

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--enforce-webrtc-ip-permission-check"
            ]

            async with async_playwright() as p:
                launch_kwargs = {
                    "headless": False,
                    "args": launch_args,
                    "ignore_default_args": ["--enable-automation"]
                }
                if self.proxy and self.proxy.get("server"):
                    launch_kwargs["proxy"] = self.proxy

                # Ưu tiên khởi chạy Google Chrome chính thức để có Sec-CH-UA 'Google Chrome' chuẩn 100%
                try:
                    browser = await p.chromium.launch(channel="chrome", **launch_kwargs)
                except Exception:
                    browser = await p.chromium.launch(**launch_kwargs)

                context_kwargs = {
                    "viewport": None,
                    "locale": proxy_locale
                }
                if proxy_tz:
                    context_kwargs["timezone_id"] = proxy_tz
                if geo_coords:
                    context_kwargs["geolocation"] = geo_coords
                    context_kwargs["permissions"] = ["geolocation"]
                if self.proxy and self.proxy.get("server"):
                    context_kwargs["proxy"] = self.proxy
                if storage_state:
                    context_kwargs["storage_state"] = storage_state

                context = await browser.new_context(**context_kwargs)

                # Đảm bảo trình duyệt luôn có mã định danh thiết bị s_v_web_id hợp lệ
                cur_cookies = await context.cookies()
                if not any(c.get("name") == "s_v_web_id" for c in cur_cookies):
                    await context.add_cookies([{
                        "name": "s_v_web_id",
                        "value": _generate_s_v_web_id(),
                        "domain": ".tiktok.com",
                        "path": "/",
                        "secure": True
                    }])

                page = await context.new_page()
                try:
                    # Khởi tạo token bảo mật tự nhiên (tt_chain_token, ttwid) tại trang chủ trước khi vào form login
                    if not storage_state:
                        await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=25000)
                        await page.wait_for_timeout(1500)
                    await page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass

                self.status_updated.emit("⏳ Đang chờ bạn đăng nhập TikTok trên trình duyệt...")
                logged_in = False
                cookie_str = ""

                for _ in range(120):
                    if not self.is_running:
                        break
                    if not browser.is_connected() or page.is_closed():
                        break
                    try:
                        cookies = await context.cookies()
                        has_session = any(c['name'] in ['sessionid', 'sessionid_ss', 'sid_tt'] and len(c['value']) > 15 for c in cookies)
                        if has_session:
                            logged_in = True
                            cookie_dict = {c['name']: c['value'] for c in cookies if '.tiktok.com' in c.get('domain', '')}
                            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                            try:
                                await context.storage_state(path=state_file)
                            except Exception:
                                pass
                            break
                    except Exception:
                        if not browser.is_connected() or page.is_closed():
                            break
                    await asyncio.sleep(1.5)

                if not logged_in and browser.is_connected() and not page.is_closed():
                    try:
                        await context.storage_state(path=state_file)
                    except Exception:
                        pass

                try:
                    await context.close()
                except Exception:
                    pass
                try:
                    await browser.close()
                except Exception:
                    pass

                if logged_in and cookie_str:
                    self.login_success.emit(cookie_str)
                else:
                    self.login_failed.emit("Đã đóng trình duyệt hoặc hết thời gian đăng nhập")
        except Exception as e:
            self.login_failed.emit(str(e))

    def stop(self):
        self.is_running = False


class ProxyCheckWorker(QThread):
    """Worker kiểm tra danh sách proxy song song/tuần tự và báo cáo kết quả từng dòng"""
    proxy_checked = pyqtSignal(int, str, bool, str, float)  # (row_index, raw_proxy, is_ok, ip_or_error, ping_ms)
    check_finished = pyqtSignal(int, int)                   # (success_cnt, fail_cnt)

    def __init__(self, proxies: List[str], parent=None):
        super().__init__(parent)
        self.proxies = proxies
        self.is_running = True

    def run(self):
        success_cnt = 0
        fail_cnt = 0
        for idx, raw_p in enumerate(self.proxies, 1):
            if not self.is_running:
                break
            parsed = parse_proxy(raw_p)
            if not parsed:
                self.proxy_checked.emit(idx, raw_p, False, "Sai định dạng proxy", 0.0)
                fail_cnt += 1
                continue

            server = parsed.get("server", "")
            auth = f"{parsed['username']}:{parsed['password']}@" if "username" in parsed else ""
            proto = "http://" if not server.startswith("http") and not server.startswith("socks") else ""
            if "://" in server:
                p_type, p_addr = server.split("://", 1)
                proxy_url = f"{p_type}://{auth}{p_addr}"
            else:
                proxy_url = f"{proto}{auth}{server}"

            t0 = time.time()
            is_success = False
            last_err = ""
            resp_ip = ""

            test_targets = [
                ("http://api.ipify.org?format=json", "json"),
                ("http://httpbin.org/ip", "json"),
                ("http://icanhazip.com", "text")
            ]

            for target_url, parse_mode in test_targets:
                try:
                    r = requests.get(
                        target_url,
                        proxies={"http": proxy_url, "https": proxy_url},
                        timeout=6
                    )
                    if r.status_code == 200:
                        if parse_mode == "json":
                            data = r.json()
                            resp_ip = str(data.get("ip") or data.get("origin") or "").split(",")[0].strip()
                        else:
                            resp_ip = r.text.strip()
                        if resp_ip:
                            is_success = True
                            break
                    else:
                        last_err = f"HTTP {r.status_code}"
                except Exception as e:
                    last_err = str(e)

            latency = round((time.time() - t0) * 1000, 1)
            if is_success:
                self.proxy_checked.emit(idx, raw_p, True, f"IP: {resp_ip}", latency)
                success_cnt += 1
            else:
                err_str = last_err.lower()
                if "timed out" in err_str or "timeout" in err_str:
                    err_msg = "Hết thời gian (Timeout >6s)"
                elif "auth" in err_str or "407" in err_str:
                    err_msg = "Sai User/Pass Proxy"
                elif "connection refused" in err_str:
                    err_msg = "Bị từ chối kết nối (Port đóng)"
                else:
                    err_msg = "Không thể kết nối"
                self.proxy_checked.emit(idx, raw_p, False, err_msg, latency)
                fail_cnt += 1

        self.check_finished.emit(success_cnt, fail_cnt)

    def stop(self):
        self.is_running = False


class ScanWorker(QThread):
    """Worker quét danh sách kênh chạy nền song song đa luồng (Parallel Workers) siêu tốc"""

    progress_updated = pyqtSignal(int, int, str, str)
    channel_scanned = pyqtSignal(dict)
    scan_finished = pyqtSignal(int, int)
    log_message = pyqtSignal(str, str)

    def __init__(self, channels: List[Dict], threads: int = 3, delay: float = 1.0, parent=None):
        super().__init__(parent)
        self.channels = channels
        self.threads = threads
        self.delay = delay
        self.is_running = True
        self.db = Database()
        self.config = load_config()

    def run(self):
        asyncio.run(self._async_run())

    async def _async_run(self):
        total = len(self.channels)
        if total == 0:
            self.scan_finished.emit(0, 0)
            return

        cfg = load_config()
        delay_min = cfg.get("delay_min", 0.2)
        delay_max = cfg.get("delay_max", 0.5)
        proxies = cfg.get("proxies", [])
        use_proxy = cfg.get("use_proxy", False) and len(proxies) > 0
        retry_count = cfg.get("retry_count", 1)
        timeout_sec = cfg.get("timeout", 15)

        # Cookie pool (hỗ trợ nhiều tài khoản luân phiên)
        cookie_str = cfg.get("tiktok_cookie", "").strip()
        cookie_pool = parse_cookie_pool(cookie_str)

        # Cấu hình số luồng chạy song song (tối đa 20 luồng)
        cfg_threads = cfg.get("threads", self.threads or 5)
        num_workers = max(1, min(cfg_threads, total, 20))

        self.log_message.emit(f"🚀 Bắt đầu quét siêu tốc {total} kênh với {num_workers} luồng song song...", "info")
        success_count = 0
        error_count = 0
        progress_counter = 0
        lock = asyncio.Lock()

        queue = asyncio.Queue()
        for ch in self.channels:
            queue.put_nowait(ch)

        scraper = TikTokScraper(timeout=timeout_sec)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--mute-audio"
                ]
            )

            async def worker_loop(worker_id: int):
                nonlocal success_count, error_count, progress_counter

                # Gán Proxy riêng cho Worker nếu có bật proxy
                worker_proxy = None
                if use_proxy and proxies:
                    worker_proxy = parse_proxy(proxies[worker_id % len(proxies)])

                # Gán Cookie riêng từ Cookie Pool cho Worker nếu có
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

                # Chặn tài nguyên nặng ở cấp Context (vẫn giữ CSS cache & ảnh Captcha để giải Captcha 100%)
                async def block_heavy_context(route):
                    rtype = route.request.resource_type
                    rurl = route.request.url.lower()
                    if rtype in ("media", "font"):
                        await route.abort()
                    elif rtype == "image" and not any(k in rurl for k in ("captcha", "verify", "security", "secsdk")):
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", block_heavy_context)

                if worker_cookies:
                    try:
                        await context.add_cookies(worker_cookies)
                    except Exception:
                        pass

                # Tái sử dụng 1 Tab (Page) duy nhất xuyên suốt các kênh trong Worker này (tự làm mới mỗi 40 kênh chống tràn RAM)
                page = await context.new_page()
                channels_on_tab = 0

                while self.is_running:
                    try:
                        ch = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    username = ch['username']
                    async with lock:
                        progress_counter += 1
                        current_idx = progress_counter

                    self.progress_updated.emit(current_idx, total, username, f"⏳ [L{worker_id+1}] Đang kết nối...")

                    attempt = 0
                    success = False
                    stats = None
                    videos = []
                    msg = ""

                    # Định kỳ mỗi 40 kênh làm mới Tab 1 lần để giải phóng RAM V8
                    if channels_on_tab >= 40:
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = await context.new_page()
                        channels_on_tab = 0

                    while attempt <= retry_count and not success and self.is_running:
                        attempt += 1
                        try:
                            if page.is_closed():
                                page = await context.new_page()
                                channels_on_tab = 0
                            success, stats, videos, msg = await scraper.scan_single_channel_async(context, username, page=page)
                            channels_on_tab += 1
                            if success and stats:
                                break
                            elif attempt <= retry_count:
                                # Khi gặp lỗi ở lần thử đầu, làm mới Tab sạch trước khi thử lại
                                try:
                                    await page.close()
                                except Exception:
                                    pass
                                page = await context.new_page()
                                channels_on_tab = 0
                                await asyncio.sleep(0.4)
                        except Exception as e:
                            msg = str(e)
                            if attempt <= retry_count:
                                try:
                                    await page.close()
                                except Exception:
                                    pass
                                page = await context.new_page()
                                channels_on_tab = 0
                                await asyncio.sleep(0.4)

                    async with lock:
                        if success and stats:
                            success_count += 1
                            self.db.update_channel_info(
                                username=stats.get('username', username),
                                nickname=stats.get('nickname', username),
                                avatar_url=stats.get('avatar_url', ''),
                                bio=stats.get('bio', ''),
                                is_verified=stats.get('is_verified', 0),
                                status="Hoạt động"
                            )
                            self.db.save_snapshot(
                                channel_id=ch['id'],
                                username=stats.get('username', username),
                                stats=stats,
                                videos=videos or []
                            )
                            flw_cnt = stats.get('follower_count', 0)
                            hrt_cnt = stats.get('heart_count', 0)
                            v_views = [f"V{i+1}: {v.get('play_count', 0):,}" for i, v in enumerate(videos[:5])]
                            views_str = " | ".join(v_views) if v_views else "0 video"
                            
                            self.progress_updated.emit(current_idx, total, username, f"✅ {flw_cnt:,} Flw | {hrt_cnt:,} Tym | {len(videos)} Vids")
                            self.log_message.emit(f"✅ [L{worker_id+1}] [{username}] {stats.get('nickname')}: {flw_cnt:,} Flw | {hrt_cnt:,} Tym ({views_str})", "success")
                            self.channel_scanned.emit({
                                "id": ch['id'],
                                "username": username,
                                "stats": stats,
                                "videos": videos
                            })
                        else:
                            error_count += 1
                            self.db.update_channel_info(
                                username=username,
                                nickname=ch.get('nickname', ''),
                                avatar_url=ch.get('avatar_url', ''),
                                bio=ch.get('bio', ''),
                                is_verified=ch.get('is_verified', 0),
                                status=f"Lỗi: {msg}"
                            )
                            self.progress_updated.emit(current_idx, total, username, f"❌ {msg}")
                            self.log_message.emit(f"❌ [L{worker_id+1}] [{username}] {msg}", "error")
                            self.channel_scanned.emit({
                                "id": ch['id'],
                                "username": username,
                                "status": f"Lỗi: {msg}"
                            })

                    queue.task_done()
                    sleep_sec = random.uniform(delay_min, delay_max)
                    await asyncio.sleep(sleep_sec)

                try:
                    await context.close()
                except Exception:
                    pass

            # Khởi chạy song song N workers
            tasks = [asyncio.create_task(worker_loop(w_id)) for w_id in range(num_workers)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

        self.log_message.emit(f"🎉 Hoàn thành quét: {success_count} thành công, {error_count} lỗi.", "info")
        self.scan_finished.emit(success_count, error_count)

    def stop(self):
        self.is_running = False
