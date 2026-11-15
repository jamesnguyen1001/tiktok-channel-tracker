import sqlite3
import os
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

from core.config import DATA_DIR

DB_FILE = os.path.join(DATA_DIR, "tiktok_growth.db")

class Database:
    """Quản lý cơ sở dữ liệu SQLite lưu danh sách kênh và lịch sử tăng trưởng hàng ngày"""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Bảng danh sách kênh
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    nickname TEXT,
                    avatar_url TEXT,
                    category TEXT DEFAULT 'Mặc định',
                    country TEXT DEFAULT '',
                    phone_code TEXT DEFAULT '',
                    account_type TEXT DEFAULT '',
                    bio TEXT,
                    is_verified INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Hoạt động',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tự động nâng cấp bảng nếu thiếu cột country, phone_code, account_type, rpm, note
            cursor.execute("PRAGMA table_info(channels)")
            col_names = [col[1] for col in cursor.fetchall()]
            if "country" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN country TEXT DEFAULT ''")
            if "phone_code" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN phone_code TEXT DEFAULT ''")
            if "account_type" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN account_type TEXT DEFAULT ''")
            if "rpm" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN rpm REAL DEFAULT 0.0")
            if "dash" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN dash REAL DEFAULT 0.0")
            if "note" not in col_names:
                cursor.execute("ALTER TABLE channels ADD COLUMN note TEXT DEFAULT ''")

            # Bảng lưu snapshot dữ liệu theo từng ngày
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    scan_date DATE NOT NULL,
                    scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    follower_count INTEGER DEFAULT 0,
                    following_count INTEGER DEFAULT 0,
                    heart_count INTEGER DEFAULT 0,
                    video_count INTEGER DEFAULT 0,
                    v1_view INTEGER DEFAULT 0,
                    v2_view INTEGER DEFAULT 0,
                    v3_view INTEGER DEFAULT 0,
                    v4_view INTEGER DEFAULT 0,
                    v5_view INTEGER DEFAULT 0,
                    avg_views REAL DEFAULT 0.0,
                    rpm REAL DEFAULT 0.0,
                    dash REAL DEFAULT 0.0,
                    videos_json TEXT,
                    delta_followers INTEGER DEFAULT 0,
                    delta_hearts INTEGER DEFAULT 0,
                    delta_videos INTEGER DEFAULT 0,
                    FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
                    UNIQUE(channel_id, scan_date)
                )
            ''')

            cursor.execute("PRAGMA table_info(snapshots)")
            snap_cols = [col[1] for col in cursor.fetchall()]
            if "rpm" not in snap_cols:
                cursor.execute("ALTER TABLE snapshots ADD COLUMN rpm REAL DEFAULT 0.0")
            if "dash" not in snap_cols:
                cursor.execute("ALTER TABLE snapshots ADD COLUMN dash REAL DEFAULT 0.0")

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(scan_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_channel ON snapshots(channel_id)')
            conn.commit()

    def add_channels_bulk(self, usernames: List[str], category: str = "Mặc định", country: str = "", phone_code: str = "") -> Tuple[int, int]:
        added = 0
        skipped = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for raw_u in usernames:
                u = raw_u.strip().lstrip('@').lower()
                if not u:
                    continue
                try:
                    cursor.execute('''
                        INSERT INTO channels (username, nickname, category, country, phone_code, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (u, u, category, country, phone_code))
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1
            conn.commit()
        return added, skipped

    def update_channel_info(self, username: str, nickname: str, avatar_url: str, bio: str, is_verified: int, status: str = "Hoạt động"):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE channels 
                SET nickname = ?, avatar_url = ?, bio = ?, is_verified = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (nickname, avatar_url, bio, is_verified, status, username.strip().lstrip('@').lower()))
            conn.commit()

    def update_channel_category(self, channel_id: int, new_category: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET category = ? WHERE id = ?', (new_category.strip(), channel_id))
            conn.commit()

    def update_channel_country(self, channel_id: int, country: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET country = ? WHERE id = ?', (country.strip(), channel_id))
            conn.commit()

    def update_channel_phone_code(self, channel_id: int, phone_code: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET phone_code = ? WHERE id = ?', (str(phone_code).strip(), channel_id))
            conn.commit()

    def update_channel_account_type(self, channel_id: int, account_type: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET account_type = ? WHERE id = ?', (str(account_type).strip(), channel_id))
            conn.commit()

    def update_channel_rpm(self, channel_id: int, username: str, rpm_val: float):
        today = date.today().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET rpm = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (float(rpm_val), channel_id))
            # Cập nhật RPM theo ngày vào bảng snapshots để lưu lịch sử hàng ngày
            cursor.execute('SELECT id FROM snapshots WHERE channel_id = ? AND scan_date = ?', (channel_id, today))
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE snapshots SET rpm = ? WHERE id = ?', (float(rpm_val), row[0]))
            else:
                cursor.execute('SELECT * FROM snapshots WHERE channel_id = ? ORDER BY scan_date DESC LIMIT 1', (channel_id,))
                prev = cursor.fetchone()
                if prev:
                    cursor.execute('''
                        INSERT INTO snapshots (
                            channel_id, username, scan_date, scanned_at,
                            follower_count, following_count, heart_count, video_count,
                            v1_view, v2_view, v3_view, v4_view, v5_view, avg_views, rpm,
                            videos_json, delta_followers, delta_hearts, delta_videos
                        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                    ''', (
                        channel_id, username, today,
                        prev["follower_count"], prev["following_count"], prev["heart_count"], prev["video_count"],
                        prev["v1_view"], prev["v2_view"], prev["v3_view"], prev["v4_view"], prev["v5_view"],
                        prev["avg_views"], float(rpm_val), prev["videos_json"]
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO snapshots (channel_id, username, scan_date, scanned_at, rpm)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ''', (channel_id, username, today, float(rpm_val)))
            conn.commit()

    def update_channel_dash(self, channel_id: int, username: str, dash_val: float):
        today = date.today().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET dash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (float(dash_val), channel_id))
            cursor.execute('SELECT id FROM snapshots WHERE channel_id = ? AND scan_date = ?', (channel_id, today))
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE snapshots SET dash = ? WHERE id = ?', (float(dash_val), row[0]))
            else:
                cursor.execute('SELECT * FROM snapshots WHERE channel_id = ? ORDER BY scan_date DESC LIMIT 1', (channel_id,))
                prev = cursor.fetchone()
                if prev:
                    cursor.execute('''
                        INSERT INTO snapshots (
                            channel_id, username, scan_date, scanned_at,
                            follower_count, following_count, heart_count, video_count,
                            v1_view, v2_view, v3_view, v4_view, v5_view, avg_views, rpm, dash,
                            videos_json, delta_followers, delta_hearts, delta_videos
                        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                    ''', (
                        channel_id, username, today,
                        prev["follower_count"], prev["following_count"], prev["heart_count"], prev["video_count"],
                        prev["v1_view"], prev["v2_view"], prev["v3_view"], prev["v4_view"], prev["v5_view"],
                        prev["avg_views"], prev["rpm"] if "rpm" in prev.keys() else 0.0, float(dash_val), prev["videos_json"]
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO snapshots (channel_id, username, scan_date, scanned_at, dash)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ''', (channel_id, username, today, float(dash_val)))
            conn.commit()

    def update_channel_note(self, channel_id: int, note: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET note = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (str(note).strip(), channel_id))
            conn.commit()

    def delete_channel(self, channel_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM snapshots WHERE channel_id = ?', (channel_id,))
            cursor.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
            conn.commit()

    def delete_channels_bulk(self, channel_ids: List[int]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('DELETE FROM snapshots WHERE channel_id = ?', [(cid,) for cid in channel_ids])
            cursor.executemany('DELETE FROM channels WHERE id = ?', [(cid,) for cid in channel_ids])
            conn.commit()

    def save_snapshot(self, channel_id: int, username: str, stats: dict, videos: List[dict]):
        today = date.today().strftime("%Y-%m-%d")
        v_views = [v.get("play_count", 0) for v in videos[:5]]
        while len(v_views) < 5:
            v_views.append(0)

        avg_v = sum(v_views) / max(1, len([v for v in v_views if v > 0])) if any(v > 0 for v in v_views) else 0.0

        prev_snap = self.get_latest_snapshot_before(channel_id, today)
        delta_flw = 0
        delta_hrt = 0
        delta_vid = 0

        if prev_snap:
            delta_flw = stats.get("follower_count", 0) - prev_snap["follower_count"]
            delta_hrt = stats.get("heart_count", 0) - prev_snap["heart_count"]
            delta_vid = stats.get("video_count", 0) - prev_snap["video_count"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT rpm, dash FROM channels WHERE id = ?', (channel_id,))
            ch_row = cursor.fetchone()
            cur_rpm = float(ch_row[0] or 0.0) if ch_row else 0.0
            cur_dash = float(ch_row[1] or 0.0) if ch_row else 0.0

            cursor.execute('''
                INSERT INTO snapshots (
                    channel_id, username, scan_date, scanned_at,
                    follower_count, following_count, heart_count, video_count,
                    v1_view, v2_view, v3_view, v4_view, v5_view, avg_views, rpm, dash,
                    videos_json, delta_followers, delta_hearts, delta_videos
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id, scan_date) DO UPDATE SET
                    scanned_at = CURRENT_TIMESTAMP,
                    follower_count = excluded.follower_count,
                    following_count = excluded.following_count,
                    heart_count = excluded.heart_count,
                    video_count = excluded.video_count,
                    v1_view = excluded.v1_view,
                    v2_view = excluded.v2_view,
                    v3_view = excluded.v3_view,
                    v4_view = excluded.v4_view,
                    v5_view = excluded.v5_view,
                    avg_views = excluded.avg_views,
                    videos_json = excluded.videos_json,
                    delta_followers = excluded.delta_followers,
                    delta_hearts = excluded.delta_hearts,
                    delta_videos = excluded.delta_videos
            ''', (
                channel_id, username, today,
                stats.get("follower_count", 0),
                stats.get("following_count", 0),
                stats.get("heart_count", 0),
                stats.get("video_count", 0),
                v_views[0], v_views[1], v_views[2], v_views[3], v_views[4], avg_v, cur_rpm, cur_dash,
                json.dumps(videos, ensure_ascii=False),
                delta_flw, delta_hrt, delta_vid
            ))
            conn.commit()

    def get_latest_snapshot_before(self, channel_id: int, target_date: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM snapshots 
                WHERE channel_id = ? AND scan_date < ?
                ORDER BY scan_date DESC LIMIT 1
            ''', (channel_id, target_date))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_channels(self, category_filter: Optional[str] = None, search_query: Optional[str] = None, country_filter: Optional[str] = None, phone_code_filter: Optional[str] = None) -> List[dict]:
        query = '''
            SELECT 
                c.id, c.username, c.nickname, c.avatar_url, c.category,
                COALESCE(c.country, '') as country,
                COALESCE(c.phone_code, '') as phone_code,
                COALESCE(c.account_type, '') as account_type,
                COALESCE(c.rpm, 0.0) as rpm,
                COALESCE(c.dash, 0.0) as dash,
                COALESCE(c.note, '') as note,
                c.bio, c.is_verified, c.status,
                s.scan_date, s.scanned_at as last_scanned_at,
                COALESCE(s.follower_count, 0) as followers,
                COALESCE(s.following_count, 0) as following,
                COALESCE(s.heart_count, 0) as hearts,
                COALESCE(s.video_count, 0) as video_count,
                COALESCE(s.v1_view, 0) as v1_view,
                COALESCE(s.v2_view, 0) as v2_view,
                COALESCE(s.v3_view, 0) as v3_view,
                COALESCE(s.v4_view, 0) as v4_view,
                COALESCE(s.v5_view, 0) as v5_view,
                COALESCE(s.avg_views, 0.0) as avg_views,
                COALESCE(s.delta_followers, 0) as delta_followers,
                COALESCE(s.delta_hearts, 0) as delta_hearts,
                COALESCE(s.delta_videos, 0) as delta_videos,
                s.videos_json
            FROM channels c
            LEFT JOIN snapshots s ON c.id = s.channel_id AND s.id = (
                SELECT id FROM snapshots WHERE channel_id = c.id ORDER BY scan_date DESC LIMIT 1
            )
            WHERE 1=1
        '''
        params = []
        if category_filter and category_filter != "Tất cả":
            if category_filter == "Mặc định":
                query += " AND (c.category = 'Mặc định' OR c.category IS NULL OR c.category = '')"
            else:
                query += " AND c.category = ?"
                params.append(category_filter)

        if country_filter and country_filter != "Tất cả":
            if country_filter in ["Chưa chọn (--)", "--"]:
                query += " AND (c.country IS NULL OR c.country = '' OR c.country = '--')"
            else:
                query += " AND c.country = ?"
                params.append(country_filter)

        if phone_code_filter and phone_code_filter != "Tất cả":
            if phone_code_filter in ["Chưa chọn (--)", "Chưa có mã (--)", "--"]:
                query += " AND (c.phone_code IS NULL OR c.phone_code = '' OR c.phone_code = '--')"
            else:
                query += " AND c.phone_code = ?"
                params.append(phone_code_filter)

        if search_query:
            query += " AND (c.username LIKE ? OR c.nickname LIKE ? OR c.note LIKE ?)"
            sq = f"%{search_query.strip()}%"
            params.extend([sq, sq, sq])

        query += " ORDER BY c.id ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_categories(self) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM channels WHERE category IS NOT NULL AND category != "" ORDER BY category ASC')
            return [row[0] for row in cursor.fetchall()]

    def get_channel_history(self, channel_id: int) -> List[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM snapshots 
                WHERE channel_id = ? 
                ORDER BY scan_date ASC
            ''', (channel_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_kpi(self) -> dict:
        today = date.today().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM channels')
            total_channels = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT channel_id) FROM snapshots WHERE scan_date = ?', (today,))
            scanned_today = cursor.fetchone()[0]

            cursor.execute('''
                SELECT 
                    SUM(COALESCE(s.follower_count, 0)),
                    SUM(COALESCE(s.heart_count, 0)),
                    SUM(COALESCE(s.delta_followers, 0)),
                    SUM(COALESCE(s.delta_hearts, 0)),
                    SUM(COALESCE(c.dash, 0.0)),
                    SUM(CASE WHEN COALESCE(c.dash, 0.0) > 0 THEN 1 ELSE 0 END),
                    AVG(CASE WHEN COALESCE(c.rpm, 0.0) > 0 THEN c.rpm ELSE NULL END)
                FROM channels c
                LEFT JOIN snapshots s ON c.id = s.channel_id AND s.id = (
                    SELECT id FROM snapshots WHERE channel_id = c.id ORDER BY scan_date DESC LIMIT 1
                )
            ''')
            row = cursor.fetchone()
            return {
                "total_channels": total_channels,
                "scanned_channels": scanned_today,
                "total_followers": row[0] or 0,
                "total_hearts": row[1] or 0,
                "total_growth_followers": row[2] or 0,
                "total_growth_hearts": row[3] or 0,
                "total_dash": float(row[4] or 0.0),
                "dash_channels": int(row[5] or 0),
                "avg_rpm": round(float(row[6] or 0.0), 2)
            }
