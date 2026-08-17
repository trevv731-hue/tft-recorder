# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import sqlite3
import threading
import subprocess
import ctypes  # <--- 引入底层系统API
from datetime import datetime
import requests
import eel
import pystray
import pygetwindow as gw
from PIL import Image, ImageDraw

# =========================
# 基础配置
# =========================
APP_TITLE = "云顶助手"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
START_PAGE = "index.html"
DB_PATH = os.path.join(BASE_DIR, "tft_assistant.db")

tray_icon = None

# =========================
# 数据库
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        placement INTEGER NOT NULL,
        tier TEXT,
        division TEXT,
        lp INTEGER DEFAULT 0,
        comp TEXT,
        time TEXT NOT NULL,
        season TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES accounts(id)
    )
    """)
    conn.commit()
    conn.close()

# =========================
# LCU 检测核心
# =========================
def get_common_lcu_paths():
    drives = ["C:", "D:", "E:", "F:"]
    sub_paths = [
        r"Riot Games\League of Legends\lockfile",
        r"Program Files\Tencent\英雄联盟\LeagueClient\lockfile",
        r"WeGameApps\英雄联盟\LeagueClient\lockfile",
        r"WeGame\英雄联盟\LeagueClient\lockfile",
        r"英雄联盟\LeagueClient\lockfile"
    ]
    paths = []
    for drive in drives:
        for sub in sub_paths:
            paths.append(os.path.join(drive, sub))
    return paths

def find_lcu_lockfile():
    for path in get_common_lcu_paths():
        if os.path.exists(path):
            return path
    return None

def read_lockfile(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        parts = content.split(":")
        if len(parts) >= 5:
            return int(parts[2]), parts[3]
    except Exception:
        pass
    return None, None

def fetch_current_summoner(port, password):
    url = f"https://127.0.0.1:{port}/lol-summoner/v1/current-summoner"
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(url, auth=requests.auth.HTTPBasicAuth("riot", password), verify=False, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            game_name = data.get("gameName", "")
            tag_line = data.get("tagLine", "")
            if game_name:
                display_name = f"{game_name}#{tag_line}" if tag_line else game_name
                return {"riot_id": display_name, "puuid": data.get("puuid", "")}
    except Exception:
        pass
    return None

def detect_lcu():
    lockfile = find_lcu_lockfile()
    if not lockfile:
        return None
    port, password = read_lockfile(lockfile)
    if port is None or password is None:
        return None
    return fetch_current_summoner(port, password)

# =========================
# 段位与统计
# =========================
TIER_BASE = {
    "黑铁": 100, "青铜": 200, "白银": 300, "黄金": 400, "铂金": 500,
    "翡翠": 600, "钻石": 700, "大师": 800, "宗师": 900, "王者": 1000
}
DIV_SCORE = {"IV": 0, "III": 25, "II": 50, "I": 75, "-": 0}

def tier_score(tier, division, lp):
    base = TIER_BASE.get(tier or "", 0)
    div = DIV_SCORE.get(division or "-", 0)
    try:
        lpv = int(lp or 0)
    except Exception:
        lpv = 0
    return base + div + lpv

def safe_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def normalize_time(t):
    if t and str(t).strip():
        return str(t).strip()
    return safe_now_str()

def highest_season_label(rows):
    if not rows:
        return "无记录"
    best = None
    best_score = -1
    for r in rows:
        s = tier_score(r["tier"], r["division"], r["lp"])
        if s > best_score:
            best_score = s
            best = r
    if not best:
        return "无记录"
    return f'{best["tier"] or "未知"} {best["division"] or "-"} {best["lp"] or 0} LP'

def to_percent(v):
    return f"{v:.1f}%"

# =========================
# 托盘与底层无缝窗口控制
# =========================
FRONTEND_ALIVE = True
ACTION_QUEUE = []

def build_tray_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 58, 58), fill=(229, 184, 105, 255))
    d.text((24, 20), "云", fill=(20, 20, 20, 255))
    return img

def find_app_window():
    try:
        wins = gw.getWindowsWithTitle(APP_TITLE)
        if not wins:
            return None
        for w in wins:
            if APP_TITLE in w.title:
                return w
        return wins[0]
    except Exception:
        return None

def _do_show_window():
    """在主线程执行：底层秒开"""
    global FRONTEND_ALIVE
    w = find_app_window()
    
    if FRONTEND_ALIVE and w is not None:
        try:
            # 核心：调用底层 API 瞬间恢复窗口 (9 = SW_RESTORE)
            # 绝对没有任何缩放、跳跃、闪烁动画
            ctypes.windll.user32.ShowWindow(w._hWnd, 9)
            w.activate()
        except Exception:
            pass
            
        try:
            eel.restore_window_from_tray()()
        except Exception:
            pass
    else:
        FRONTEND_ALIVE = True
        try:
            eel.show(START_PAGE)
        except Exception:
            pass

def show_window_native():
    ACTION_QUEUE.append("SHOW")

def hide_window_native():
    w = find_app_window()
    if w:
        try:
            # 核心：调用底层 API 真隐藏 (0 = SW_HIDE)
            # 直接从屏幕和任务栏消失，杜绝最小化动画
            ctypes.windll.user32.ShowWindow(w._hWnd, 0)
            return True
        except Exception:
            pass
    return False

def on_window_close(page, sockets):
    global FRONTEND_ALIVE
    FRONTEND_ALIVE = False

@eel.expose
def hide_to_tray():
    ok = hide_window_native()
    return {"status": "ok" if ok else "fail"}

def on_tray_show(icon, item):
    show_window_native()

def on_tray_exit(icon, item):
    try:
        icon.stop()
    except Exception:
        pass
    os._exit(0) 

def run_tray():
    global tray_icon
    tray_icon = pystray.Icon(
        "tft_assistant_tray",
        build_tray_image(),
        APP_TITLE,
        pystray.Menu(
            pystray.MenuItem("显示主面板", on_tray_show),
            pystray.MenuItem("退出程序", on_tray_exit),
        ),
    )
    tray_icon.run()

# =========================
# Eel API
# =========================
@eel.expose
def get_client_info():
    info = detect_lcu()
    if info:
        return {"status": "success", "riot_id": info["riot_id"], "puuid": info.get("puuid", "")}
    else:
        return {"status": "error", "msg": "未检测到运行中的英雄联盟客户端"}

@eel.expose
def login(name):
    name = (name or "").strip()
    if not name:
        return -1
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE username=?", (name,))
    row = c.fetchone()
    if row:
        uid = row["id"]
    else:
        c.execute(
            "INSERT INTO accounts(username, created_at) VALUES(?, ?)",
            (name, safe_now_str())
        )
        conn.commit()
        uid = c.lastrowid
    conn.close()
    return int(uid)

@eel.expose
def get_account_list():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username FROM accounts ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

@eel.expose
def delete_account(account_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM matches WHERE user_id=?", (int(account_id),))
    c.execute("DELETE FROM accounts WHERE id=?", (int(account_id),))
    conn.commit()
    conn.close()
    return {"status": "success"}

@eel.expose
def add_match(user_id, placement, tier, division, lp, comp, t, season):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matches(user_id, placement, tier, division, lp, comp, time, season, created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        int(user_id),
        int(placement),
        str(tier or ""),
        str(division or "-"),
        int(lp or 0),
        str(comp or ""),
        normalize_time(t),
        str(season or "S18"),
        safe_now_str()
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@eel.expose
def update_match(match_id, placement, tier, division, lp, comp, t, season):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE matches
        SET placement=?, tier=?, division=?, lp=?, comp=?, time=?, season=?
        WHERE id=?
    """, (
        int(placement),
        str(tier or ""),
        str(division or "-"),
        int(lp or 0),
        str(comp or ""),
        normalize_time(t),
        str(season or "S18"),
        int(match_id)
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@eel.expose
def delete_match(match_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM matches WHERE id=?", (int(match_id),))
    conn.commit()
    conn.close()
    return {"status": "success"}

@eel.expose
def sync_lcu_matches(user_id, season):
    return {"status": "error", "msg": "当前版本未接入 LCU 自动同步，请手动录入"}

@eel.expose
def get_stats(user_id, season):
    user_id = int(user_id)
    season = str(season or "S18")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id, placement, tier, division, lp, comp, time, season
        FROM matches
        WHERE user_id=? AND season=?
        ORDER BY datetime(time) DESC, id DESC
    """, (user_id, season))
    rows = c.fetchall()
    history = [dict(r) for r in rows]

    total = len(history)
    if total == 0:
        conn.close()
        return {
            "total": 0,
            "avg_placement": "0.0",
            "win_rate": "0%",
            "top4_rate": "0%",
            "distribution": {i: 0 for i in range(1, 9)},
            "history": [],
            "daily_stats": [],
            "highest_season": "无记录"
        }

    placements = [int(r["placement"]) for r in history]
    avg_p = sum(placements) / total
    win = sum(1 for p in placements if p == 1) / total * 100
    top4 = sum(1 for p in placements if p <= 4) / total * 100

    dist = {i: 0 for i in range(1, 9)}
    for p in placements:
        if 1 <= p <= 8:
            dist[p] += 1

    daily_map = {}
    for r in history:
        day = str(r["time"])[:10]
        if day not in daily_map:
            daily_map[day] = []
        daily_map[day].append(r)

    daily_stats = []
    for day, items in sorted(daily_map.items()):
        cnt = len(items)
        ap = round(sum(int(x["placement"]) for x in items) / cnt, 2)
        last_item = sorted(items, key=lambda x: (x["time"], x["id"]))[-1]
        ts = tier_score(last_item["tier"], last_item["division"], last_item["lp"])
        label = f'{last_item["tier"] or "未知"} {last_item["division"] or "-"} {last_item["lp"] or 0} LP'
        daily_stats.append({
            "day": day,
            "full_day": day,
            "games_count": cnt,
            "avg_placement": ap,
            "tier_score": ts,
            "tier_label": label
        })

    highest = highest_season_label(history)

    conn.close()
    return {
        "total": total,
        "avg_placement": f"{avg_p:.1f}",
        "win_rate": to_percent(win),
        "top4_rate": to_percent(top4),
        "distribution": dist,
        "history": history,
        "daily_stats": daily_stats,
        "highest_season": highest
    }

# =========================
# 启动
# =========================
def main():
    init_db()
    eel.init(WEB_DIR)

    t = threading.Thread(target=run_tray, daemon=True)
    t.start()
    time.sleep(0.3)

    start_kwargs = {
        "size": (1280, 850),
        "position": (220, 100),
        "block": False,
        "close_callback": on_window_close
    }

    try:
        eel.start(START_PAGE, mode="chrome", **start_kwargs)
    except Exception:
        eel.start(START_PAGE, mode="edge", **start_kwargs)

    while True:
        while len(ACTION_QUEUE) > 0:
            action = ACTION_QUEUE.pop(0)
            if action == "SHOW":
                _do_show_window()
        eel.sleep(0.1)

if __name__ == "__main__":
    main()