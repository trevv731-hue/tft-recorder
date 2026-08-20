# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import sqlite3
import threading
import subprocess
import ctypes
from datetime import datetime
import requests
import eel
import pystray
import pygetwindow as gw
from PIL import Image, ImageDraw
import overlay
import augment_overlay

# ========== Riot 官方 API 配置 ==========
RIOT_API_KEY = ""  # 用户可在设置中填写
RIOT_REGIONS = {
    "na": "na1", "euw": "euw1", "eune": "eun1", "kr": "kr",
    "br": "br1", "jp": "jp1", "lan": "la1", "las": "la2",
    "oc": "oc1", "tr": "tr1", "ru": "ru", "pbe": "pbe1"
}
# 国服大区映射（腾讯SGP已单独处理，这里用Riot API查外服/PBE）
TFT_QUEUE_ID = 1090  # TFT排位

# ========== 配置文件管理 (自动保存/加载 API Key 等) ==========
import json as _json
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json") if not getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(sys.executable), "config.json")

def load_config():
    """从 config.json 加载配置"""
    global RIOT_API_KEY
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            if cfg.get("riot_api_key"):
                RIOT_API_KEY = cfg["riot_api_key"].strip()
                print(f"[Config] 已加载 Riot API Key: {RIOT_API_KEY[:8]}...")
    except Exception as e:
        print(f"[Config] 加载配置失败: {e}")

def save_config(key=None):
    """保存配置到 config.json"""
    try:
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
        if key is not None:
            cfg["riot_api_key"] = key.strip()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Config] 保存配置失败: {e}")
        return False

# 启动时自动加载配置
load_config()

def riot_api_request(region, endpoint, params=None):
    """调用Riot官方API"""
    if not RIOT_API_KEY:
        return None
    base = f"https://{region}.api.riotgames.com"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        resp = requests.get(f"{base}{endpoint}", headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def riot_get_summoner(region, name):
    """通过名字获取召唤师信息"""
    return riot_api_request(RIOT_REGIONS.get(region, region), f"/tft/summoner/v1/summoners/by-name/{name}")

def riot_get_match_history(region, puuid, count=20):
    """获取对局历史ID列表"""
    return riot_api_request(f"https://{region}.api.riotgames.com".replace("https://","").split(".")[0],
                           f"/tft/match/v1/matches/by-puuid/{puuid}/ids", {"count": count})

def riot_get_match_detail(region, match_id):
    """获取对局详情（含阵容）"""
    # match endpoint用区域路由（americas/europe/asia）
    region_map = {"na":"americas","br":"americas","lan":"americas","las":"americas",
                  "euw":"europe","eune":"europe","tr":"europe","ru":"europe",
                  "kr":"asia","jp":"asia","oc":"asia","pbe":"americas"}
    routing = region_map.get(region, "americas")
    return riot_api_request(routing, f"/tft/match/v1/matches/{match_id}")

def riot_get_tft_rank(region, summoner_id):
    """获取TFT段位信息"""
    return riot_api_request(RIOT_REGIONS.get(region, region), f"/tft/league/v1/entries/by-summoner/{summoner_id}")

@eel.expose
def set_riot_api_key(key):
    """设置Riot API Key并保存到配置文件"""
    global RIOT_API_KEY
    RIOT_API_KEY = key.strip()
    save_config(RIOT_API_KEY)
    return {"status": "success", "has_key": bool(RIOT_API_KEY), "key_preview": RIOT_API_KEY[:8] + "..." if RIOT_API_KEY else ""}

@eel.expose
def get_riot_api_status():
    """获取当前 Riot API Key 状态"""
    return {
        "has_key": bool(RIOT_API_KEY),
        "key_preview": RIOT_API_KEY[:8] + "..." if RIOT_API_KEY else "",
        "config_path": CONFIG_PATH
    }

@eel.expose
def test_riot_api(region, summoner_name):
    """测试Riot API连接"""
    if not RIOT_API_KEY:
        return {"status": "error", "msg": "请先设置API Key"}
    result = riot_get_summoner(region, summoner_name)
    if result:
        return {"status": "success", "summoner": result}
    return {"status": "error", "msg": "API调用失败，请检查Key和大区"}

# psutil 优先（国服推荐），没有则回退 wmic
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# =========================
# 基础配置
# =========================
APP_TITLE = "战绩统计"
# 打包兼容：web资源从临时目录读，数据库和用户数据放exe同级目录
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)  # exe所在目录
    WEB_DIR = os.path.join(sys._MEIPASS, "web")  # PyInstaller临时目录
    ICON_DIR = os.path.join(sys._MEIPASS, "icons")  # 打包的icons在临时目录
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WEB_DIR = os.path.join(BASE_DIR, "web")
    ICON_DIR = os.path.join(BASE_DIR, "icons")
START_PAGE = "index.html"
DB_PATH = os.path.join(BASE_DIR, "tft_assistant.db")
os.makedirs(ICON_DIR, exist_ok=True)
tray_icon = None

# =========================
# 牌池配置 (S17 星神赛季)
# =========================
POOL_SIZE = {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}  # 各费用单英雄总数
THREE_STAR_REQUIRED = 9
THREE_STAR_ALERT_THRESHOLD = 3  # 差3张时预警

# 对局内实时状态
_live_state = {
    "in_game": False,
    "phase": "",
    "players": [],       # [{puuid, name, placement}]
    "my_board": {},      # 自己的棋盘
    "pool_taken": {},    # 已被拿的牌 {champ_id: count}
    "opponent_info": {}, # 对手情报 {puuid: {tier, wins, recent_comps}}
    "last_update": 0,
}
_live_lock = threading.Lock()
_debug_gameflow_saved = False

# =========================
# 对局内实时模块配置
# =========================
# S17 牌池总数（每费用每个英雄的张数）
POOL_SIZE = {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}
# 三星需要9张
THREE_STAR_NEED = 9
# 三星预警阈值：差N张时预警
THREE_STAR_ALERT_THRESHOLD = 3
# 对局内实时状态
live_state = {
    "in_game": False,
    "phase": "",
    "players": [],       # [{puuid, name, is_self}]
    "my_board": {},      # 自己的棋盘
    "pool_taken": {},    # 已被拿的牌 {champ_id: count}
    "opponent_info": {}, # 对手情报 {puuid: {tier, wins, recent_comps}}
    "three_star_alerts": [], # 三星预警
    "last_update": 0,
}
live_lock = threading.Lock()

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
    # 对手牌数据持久化
    c.execute("""
    CREATE TABLE IF NOT EXISTS opponent_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        puuid TEXT,
        champ_id TEXT NOT NULL,
        count INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    # 迁移：添加 game_id 列用于自动同步去重（幂等）
    try:
        c.execute("ALTER TABLE matches ADD COLUMN game_id INTEGER")
    except sqlite3.OperationalError:
        pass
    # 迁移：添加 units 列存储英雄列表（JSON）
    try:
        c.execute("ALTER TABLE matches ADD COLUMN units TEXT")
    except sqlite3.OperationalError:
        pass
    # 迁移：添加 rank 列存储全区排名（大师以上才有）
    try:
        c.execute("ALTER TABLE matches ADD COLUMN rank INTEGER")
    except sqlite3.OperationalError:
        pass
    # 对局玩家表：存每局8个玩家的信息
    c.execute("""
    CREATE TABLE IF NOT EXISTS match_players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        puuid TEXT,
        summoner_name TEXT,
        placement INTEGER,
        tier TEXT,
        division TEXT,
        lp INTEGER,
        comp TEXT,
        units TEXT,
        is_self INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    # 索引：加速查询
    c.execute("CREATE INDEX IF NOT EXISTS idx_match_players_game_id ON match_players(game_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_match_players_puuid ON match_players(puuid)")
    # 索引：加速查询
    c.execute("CREATE INDEX IF NOT EXISTS idx_matches_user_season ON matches(user_id, season)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_matches_game_id ON matches(game_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_matches_time ON matches(time)")
    conn.commit()
    conn.close()

# =========================
# LCU 连接核心（国服兼容 —— 进程命令行方式）
# 参考 LeagueCustomLobby：国服不再生成 lockfile，
# 需要从 LeagueClientUx.exe 进程命令行参数中提取
# --remoting-auth-token 和 --app-port
# =========================

def _get_lcu_from_psutil():
    """通过 psutil 遍历进程，提取 LCU 凭证（psutil>=5.7 可能 AccessDenied）"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            info = proc.info
            pname = (info.get('name') or '') if info else ''
            if 'LeagueClientUx.exe' not in pname:
                continue
            cmdline = info.get('cmdline') or []
            port = token = None
            for arg in cmdline:
                if arg.startswith('--app-port='):
                    port = arg.split('=', 1)[1]
                elif arg.startswith('--remoting-auth-token='):
                    token = arg.split('=', 1)[1]
            if port and token:
                return int(port), token
        except Exception:
            # psutil>=5.7 在 Windows 上可能抛 AccessDenied / Error 等，统一跳过
            continue
    return None, None

def _get_lcu_from_wmic():
    """备选：通过 wmic 命令提取（可能需要管理员权限）"""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        result = subprocess.run(
            ['wmic', 'process', 'where', "name='LeagueClientUx.exe'", 'get', 'commandline'],
            capture_output=True, text=True, timeout=10, startupinfo=si
        )
        port = token = None
        for line in result.stdout.splitlines():
            if '--app-port=' not in line:
                continue
            for part in line.split():
                if part.startswith('--app-port='):
                    port = part.split('=', 1)[1]
                elif part.startswith('--remoting-auth-token='):
                    token = part.split('=', 1)[1]
        if port and token:
            return int(port), token
    except Exception:
        pass
    return None, None

def _get_lcu_from_lockfile():
    """lockfile 方式：优先 Riot Client 新路径，再搜游戏安装目录（外服/旧版本国服）"""
    # 1. Riot Client 新启动器 lockfile（国服新版优先）
    riot_lock = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Riot Games", "Riot Client", "Config", "lockfile"
    )
    if os.path.exists(riot_lock):
        try:
            with open(riot_lock, "r", encoding="utf-8") as f:
                parts = f.read().strip().split(":")
            if len(parts) >= 5:
                return int(parts[2]), parts[3]
        except Exception:
            pass

    # 2. 游戏安装目录下的传统 lockfile（外服/旧版本）
    drives = ["C:", "D:", "E:", "F:"]
    sub_paths = [
        r"Riot Games\League of Legends\lockfile",
        r"Program Files\Tencent\英雄联盟\LeagueClient\lockfile",
        r"WeGameApps\英雄联盟\LeagueClient\lockfile",
        r"WeGame\英雄联盟\LeagueClient\lockfile",
        r"英雄联盟\LeagueClient\lockfile",
    ]
    for drive in drives:
        for sub in sub_paths:
            path = os.path.join(drive, sub)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        parts = f.read().strip().split(":")
                    if len(parts) >= 5:
                        return int(parts[2]), parts[3]
                except Exception:
                    pass
    return None, None

def get_lcu_credentials():
    """
    获取 LCU 连接凭证（国服兼容）。
    优先级：psutil进程命令行 → Riot Client lockfile → wmic → 游戏目录lockfile
    返回 (port, token) 或 (None, None)。
    """
    # 1. psutil 遍历进程（最快，无需管理员，但 psutil>=5.7 可能 AccessDenied）
    if HAS_PSUTIL:
        port, token = _get_lcu_from_psutil()
        if port and token:
            return port, token
    # 2. Riot Client 新路径 lockfile（国服新版，游戏运行时一定存在）
    port, token = _get_lcu_from_lockfile()
    if port and token:
        return port, token
    # 3. wmic 备选（需要管理员权限才能看到完整命令行）
    port, token = _get_lcu_from_wmic()
    if port and token:
        return port, token
    return None, None

def _disable_ssl_warnings():
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

def lcu_get(port, token, path, timeout=10):
    """统一 LCU GET 请求封装"""
    _disable_ssl_warnings()
    url = f"https://127.0.0.1:{port}{path}"
    auth = requests.auth.HTTPBasicAuth("riot", token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return requests.get(url, auth=auth, headers=headers, verify=False, timeout=timeout)

# =========================
# Live Client Data API (port 2999)
# 英雄联盟/TFT 游戏内实时数据API，无需认证
# =========================
LIVE_API_BASE = "https://127.0.0.1:2999"

def live_api_get(path, timeout=5):
    """请求 Live Client Data API (port 2999)"""
    _disable_ssl_warnings()
    try:
        resp = requests.get(f"{LIVE_API_BASE}{path}", verify=False, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def is_live_api_available():
    """检查 Live Client Data API 是否可用（游戏中）"""
    data = live_api_get("/liveclientdata/gamestats", timeout=3)
    return data is not None

def get_live_all_game_data():
    """获取所有游戏数据（包括玩家、棋盘等）"""
    return live_api_get("/liveclientdata/allgamedata", timeout=5)

def get_live_player_list():
    """获取玩家列表"""
    return live_api_get("/liveclientdata/playerlist", timeout=5)

def get_live_active_player():
    """获取当前玩家信息"""
    return live_api_get("/liveclientdata/activeplayer", timeout=5)

def get_live_game_stats():
    """获取游戏统计（游戏时间、模式等）"""
    return live_api_get("/liveclientdata/gamestats", timeout=5)

def fetch_current_summoner(port, token):
    """获取当前登录召唤师信息"""
    try:
        resp = lcu_get(port, token, "/lol-summoner/v1/current-summoner", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            game_name = data.get("gameName", "")
            tag_line = data.get("tagLine", "")
            if game_name:
                display_name = f"{game_name}#{tag_line}" if tag_line else game_name
            else:
                display_name = data.get("displayName", "") or data.get("summonerName", "")
            if display_name:
                return {"riot_id": display_name, "puuid": data.get("puuid", "")}
    except Exception:
        pass
    return None

def fetch_summoners_by_puuids(port, token, puuids):
    """通过 puuid 列表批量查询召唤师名字，返回 {puuid: name}"""
    if not port or not token or not puuids:
        return {}
    result = {}
    unique_puuids = list(set(p for p in puuids if p))
    if not unique_puuids:
        return {}

    # 方式1：POST 批量查询
    try:
        resp = requests.post(
            f"https://127.0.0.1:{port}/lol-summoner/v2/summoners",
            headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
            json=unique_puuids[:40], verify=False, timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for s in data:
                    puuid = s.get("puuid", "")
                    name = s.get("gameName") or s.get("summonerName") or s.get("displayName") or ""
                    tag = s.get("tagLine") or ""
                    if puuid and name:
                        result[puuid] = f"{name}#{tag}" if tag else name
    except Exception:
        pass

    # 方式2：GET 批量（逗号分隔）
    if not result:
        try:
            resp = lcu_get(port, token, "/lol-summoner/v2/summoners",
                          params={"puuid": ",".join(unique_puuids[:40])}, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for s in data:
                        puuid = s.get("puuid", "")
                        name = s.get("gameName") or s.get("summonerName") or s.get("displayName") or ""
                        tag = s.get("tagLine") or ""
                        if puuid and name:
                            result[puuid] = f"{name}#{tag}" if tag else name
        except Exception:
            pass

    # 方式3：逐个查询（兜底）
    if len(result) < len(unique_puuids):
        for puuid in unique_puuids[:20]:
            if puuid in result and result[puuid]:
                continue
            try:
                resp = lcu_get(port, token, f"/lol-summoner/v1/summoners/{puuid}", timeout=5)
                if resp.status_code == 200:
                    s = resp.json()
                    name = s.get("gameName") or s.get("summonerName") or s.get("displayName") or ""
                    tag = s.get("tagLine") or ""
                    if name:
                        result[puuid] = f"{name}#{tag}" if tag else name
            except Exception:
                pass

    return result

def detect_lcu():
    port, token = get_lcu_credentials()
    if not port or not token:
        return None
    return fetch_current_summoner(port, token)

# =========================
# 对局内实时 LCU
# =========================
def get_gameflow_phase(port, token):
    """获取游戏阶段: None/Lobby/ChampSelect/GameStart/InProgress/WaitingForStats/EndOfGame"""
    try:
        resp = lcu_get(port, token, "/lol-gameflow/v1/gameflow-phase", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def get_current_game_players(port, token):
    """获取当前对局玩家列表（TFT），兼容多种数据结构"""
    try:
        resp = lcu_get(port, token, "/lol-gameflow/v1/session", timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        players = []
        seen_puuids = set()

        # 方式1: gameData.teamOne / teamTwo（TFT常用）
        game_data = data.get("gameData", {})
        team = game_data.get("teamOne", []) + game_data.get("teamTwo", [])
        # 方式2: gameData.participants
        if not team:
            team = game_data.get("participants", [])
        # 方式3: 顶层 participants
        if not team:
            team = data.get("participants", [])
        # 方式4: gameData.customTeamOne / customTeamTwo
        if not team:
            team = game_data.get("customTeamOne", []) + game_data.get("customTeamTwo", [])

        for p in team:
            if not isinstance(p, dict):
                continue
            puuid = p.get("puuid", "") or p.get("currentPuuid", "")
            if not puuid or puuid in seen_puuids:
                continue
            seen_puuids.add(puuid)
            name = p.get("gameName", "") or p.get("summonerName", "") or p.get("displayName", "") or p.get("riotIdGameName", "")
            tag = p.get("tagLine", "") or p.get("riotIdTagline", "")
            players.append({
                "puuid": puuid,
                "name": f"{name}#{tag}" if tag else (name or "未知"),
                "summoner_id": p.get("summonerId", ""),
            })

        # 调试：保存第一次的gameflow数据结构
        global _debug_gameflow_saved
        if not _debug_gameflow_saved and players:
            try:
                debug_path = os.path.join(BASE_DIR, "debug_gameflow.json")
                with open(debug_path, "w", encoding="utf-8") as f:
                    json.dump({"game_keys": list(data.keys()), "gameData_keys": list(game_data.keys()), "player_sample": players[:2], "team_count": len(team)}, f, ensure_ascii=False, indent=2)
                _debug_gameflow_saved = True
            except Exception:
                pass
        return players
    except Exception:
        pass
    return []

def get_tft_board(port, token):
    """获取自己的TFT棋盘（场上+板凳的棋子）"""
    # 尝试多个端点
    endpoints = ["/lol-tft/v1/board", "/tft/v1/board", "/lol-tft/v1/board/"]
    for ep in endpoints:
        try:
            resp = lcu_get(port, token, ep, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # 调试：保存原始棋盘数据
                try:
                    import json as _json
                    with open(os.path.join(os.path.dirname(__file__), "debug_board.json"), "w", encoding="utf-8") as f:
                        _json.dump({"endpoint": ep, "data": data}, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return data
            else:
                # 记录非200状态
                try:
                    with open(os.path.join(os.path.dirname(__file__), "debug_board_error.txt"), "a", encoding="utf-8") as f:
                        f.write(f"{ep} -> HTTP {resp.status_code}\n")
                except Exception:
                    pass
        except Exception as e:
            try:
                with open(os.path.join(os.path.dirname(__file__), "debug_board_error.txt"), "a", encoding="utf-8") as f:
                    f.write(f"{ep} -> ERROR {e}\n")
            except Exception:
                pass
    return None

def probe_tft_endpoints(port, token):
    """探测所有可能的TFT LCU端点，保存结果到调试文件"""
    endpoints = [
        "/lol-tft/v1/board", "/tft/v1/board",
        "/lol-tft/v1/store", "/lol-tft/v1/shop", "/lol-tft/v1/current-store",
        "/lol-tft/v1/bench", "/lol-tft/v1/bench-units",
        "/lol-tft/v1/level", "/lol-tft/v1/gold",
        "/lol-tft/v1/players", "/lol-tft/v1/matchmaking",
        "/lol-tft/v1/game", "/lol-tft/v1/session",
        "/lol-tft/v1/active-game", "/lol-tft/v1/current-game",
        "/lol-summoner/v1/current-summoner",
        "/lol-gameflow/v1/gameflow-phase",
        "/lol-gameflow/v1/session",
    ]
    results = {}
    for ep in endpoints:
        try:
            resp = lcu_get(port, token, ep, timeout=3)
            results[ep] = {"status": resp.status_code, "body": resp.text[:500]}
        except Exception as e:
            results[ep] = {"error": str(e)[:100]}
    try:
        import json as _json
        with open(os.path.join(os.path.dirname(__file__), "debug_tft_endpoints.json"), "w", encoding="utf-8") as f:
            _json.dump(results, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return results

def parse_board_units(board_data):
    """从棋盘数据解析英雄列表 [{id, star, location}]"""
    units = []
    if not board_data:
        return units
    # units 字段包含所有棋子（场上+板凳）
    for u in board_data.get("units", []):
        champ_id = u.get("character_id", "")
        if not champ_id:
            continue
        # 去掉 TFT17_ / TFT18_ / TFT19_ 等赛季前缀
        import re
        champ_id = re.sub(r'^TFT\d+_', '', champ_id)
        star = u.get("tier", 1)  # 1/2/3
        units.append({"id": champ_id, "star": star})
    return units

def get_champ_cost(champ_id):
    """获取英雄费用（S18 魔法森林）"""
    cost_map = {
        # 1费 (14)
        "Akali": 1, "Camille": 1, "Cinderling": 1, "Karma": 1, "Kobuko": 1,
        "Leona": 1, "Ornn": 1, "Pebbles": 1, "Rakan": 1, "RekSai": 1,
        "Varus": 1, "Veigar": 1, "Xayah": 1, "Yorick": 1,
        # 2费 (13)
        "Alistar": 2, "Caitlyn": 2, "Elise": 2, "Gromp": 2, "Kayle": 2,
        "LeBlanc": 2, "Murkwolf": 2, "Scuttlecrab": 2, "Sejuani": 2, "Shen": 2,
        "Teemo": 2, "Warwick": 2, "Yunara": 2,
        # 3费 (14)
        "Azir": 3, "Cassiopeia": 3, "Diana": 3, "Fiddlesticks": 3, "Hecarim": 3,
        "KhaZix": 3, "KogMaw": 3, "Krug": 3, "MasterYi": 3, "Rammus": 3,
        "Raptor": 3, "Rengar": 3, "Tristana": 3, "Vi": 3,
        # 4费 (14)
        "Ahri": 4, "Amumu": 4, "AncientSentinel": 4, "Aphelios": 4, "Brambleback": 4,
        "Ezreal": 4, "Lillia": 4, "Malphite": 4, "Morgana": 4, "Nidalee": 4,
        "Sett": 4, "Sivir": 4, "Soraka": 4, "Zyra": 4,
        # 5费 (10)
        "Alune": 5, "Ashe": 5, "Draven": 5, "ElderDragon": 5, "Gnar": 5,
        "Ivern": 5, "Kennen": 5, "Lux": 5, "Maokai": 5, "Taric": 5,
    }
    return cost_map.get(champ_id, 2)

# =========================
# TFT 战绩拉取与解析
# =========================

# 英文段位 → 中文段位
TIER_EN_TO_CN = {
    "IRON": "黑铁", "BRONZE": "青铜", "SILVER": "白银",
    "GOLD": "黄金", "PLATINUM": "铂金", "EMERALD": "翡翠",
    "DIAMOND": "钻石", "MASTER": "大师", "GRANDMASTER": "宗师",
    "CHALLENGER": "王者",
}
TIER_ORDER = {
    "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4,
    "PLATINUM": 5, "EMERALD": 6, "DIAMOND": 7,
    "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10,
}

def get_tft_ranked(port, token):
    """获取当前云顶排位段位和排名"""
    try:
        resp = lcu_get(port, token, "/lol-ranked/v1/ranked-stats", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        # 方式1：从queueMap找TFT队列
        queue_map = data.get("queueMap", {})
        for key, q in queue_map.items():
            if not isinstance(q, dict):
                continue
            qtype = (q.get("queueType", "") or "").upper()
            if "TFT" in qtype or "TFT" in key.upper() or "云顶" in key:
                tier_en = q.get("tier", "") or ""
                rank = q.get("rank") or q.get("topRankedLp") or q.get("previousRank") or data.get("rank")
                try:
                    rank = int(rank) if rank else None
                except Exception:
                    rank = None
                lp = q.get("leaguePoints", 0) or q.get("lp", 0) or 0
                if tier_en or lp > 0:
                    return {
                        "tier": TIER_EN_TO_CN.get(tier_en.upper(), tier_en),
                        "division": q.get("division", "-") or "-",
                        "lp": int(lp),
                        "rank": rank,
                    }
        # 方式2：直接从顶层找TFT字段
        for key in ["tft", "TFT", "cloud", "rankedTft"]:
            if key in data and isinstance(data[key], dict):
                q = data[key]
                tier_en = q.get("tier", "") or ""
                if tier_en:
                    return {
                        "tier": TIER_EN_TO_CN.get(tier_en.upper(), tier_en),
                        "division": q.get("division", "-") or "-",
                        "lp": int(q.get("leaguePoints", 0) or q.get("lp", 0) or 0),
                        "rank": None,
                    }
        # 方式3：取最高段位的队列作为近似
        best = None
        for key, q in queue_map.items():
            if isinstance(q, dict) and q.get("tier"):
                tier_val = TIER_ORDER.get(q.get("tier", "").upper(), 0)
                if best is None or tier_val > best[0]:
                    best = (tier_val, q)
        if best and best[1].get("tier"):
            q = best[1]
            tier_en = q.get("tier", "")
            return {
                "tier": TIER_EN_TO_CN.get(tier_en.upper(), tier_en),
                "division": q.get("division", "-") or "-",
                "lp": int(q.get("leaguePoints", 0) or 0),
                "rank": None,
            }
    except Exception:
        pass
    return None

# 羁绊中英文映射（常见羁绊 + 英雄专属羁绊）
_TRAIT_CN_MAP = {
    # 普通羁绊
    "Arcanist": "奥术师", "Astronaut": "宇航员", "Bastion": "堡垒", "Bruiser": "斗士",
    "Challenger": "挑战者", "Deadeye": "神射手", "Emissary": "使者", "Fighter": "格斗家",
    "Guardian": "守护者", "Gunner": "炮手", "Invoker": "召唤使", "Mage": "法师",
    "Multicaster": "多重施法", "Oracle": "先知", "Pilot": "飞行员", "Redeemer": "救赎者",
    "Sage": "圣贤", "Sentinel": "哨兵", "Sniper": "狙击手", "Sorcerer": "魔法师",
    "Spearhead": "先锋", "Technogenius": "科技天才", "Timebreaker": "时间破坏者",
    "Vanquisher": "征服者", "Verve": "活力", "Warden": "护卫", "Wildcard": "百搭",
    "Cannoneer": "炮手", "Dazzler": "耀光使", "Duelist": "决斗大师", "Exalted": "至尊",
    "Flower": "花仙", "Fortune": "福星", "Heart": "心之钢", "Honeymancy": "甜蜜法师",
    "Hyperpop": "超粉", "Jazz": "爵士", "K/DA": "K/DA", "Mosher": "搏击手",
    "Pentakill": "五杀摇滚", "Poacher": "盗猎者", "Rapidfire": "迅射", "Remix": "混音",
    "Scroll": "卷轴", "Shadow": "暗影", "Silent": "静谧", "Stargazer": "星界",
    "Storyweaver": "织梦者", "Superfan": "超级粉丝", "Trap": "陷阱", "TrueDamage": "真实伤害",
    "Umbral": "幽影", "Vapor": "蒸汽", "Wild": "狂野", "Youth": "青春",
    # 英雄专属羁绊（去掉UniqueTrait后映射英雄名）
    "Aatrox": "亚托克斯", "Ahri": "阿狸", "Akali": "阿卡丽", "Akshan": "阿克尚",
    "Alistar": "阿利斯塔", "Amumu": "阿木木", "Annie": "安妮", "Aphelios": "厄斐琉斯",
    "Ashe": "艾希", "AurelionSol": "奥瑞利安索尔", "Azir": "阿兹尔", "Bard": "巴德",
    "Blitzcrank": "布里茨", "Brand": "布兰德", "Braum": "布隆", "Caitlyn": "凯特琳",
    "Camille": "卡蜜尔", "Cassiopeia": "卡西奥佩娅", "ChoGath": "科加斯", "Corki": "库奇",
    "Darius": "德莱厄斯", "Diana": "黛安娜", "DrMundo": "蒙多", "Draven": "德莱文",
    "Ekko": "艾克", "Elise": "伊莉丝", "Evelynn": "伊芙琳", "Ezreal": "伊泽瑞尔",
    "Fiora": "菲奥娜", "Fizz": "菲兹", "Galio": "加里奥", "Gangplank": "普朗克",
    "Garen": "盖伦", "Gnar": "纳尔", "Gragas": "古拉加斯", "Graves": "格雷福斯",
    "Gwen": "格温", "Hecarim": "赫卡里姆", "Heimerdinger": "黑默丁格", "Illaoi": "俄洛伊",
    "Irelia": "艾瑞莉娅", "Ivern": "艾翁", "Janna": "迦娜", "JarvanIV": "嘉文四世",
    "Jax": "贾克斯", "Jayce": "杰斯", "Jhin": "烬", "Jinx": "金克丝",
    "KaiSa": "卡莎", "Kalista": "卡莉斯塔", "Karma": "卡尔玛", "Kassadin": "卡萨丁",
    "Katarina": "卡特琳娜", "Kayle": "凯尔", "Kennen": "凯南", "Kindred": "千珏",
    "Kled": "克烈", "KogMaw": "克格莫", "LeBlanc": "乐芙兰", "LeeSin": "李青",
    "Leona": "蕾欧娜", "Lillia": "莉莉娅", "Lissandra": "丽桑卓", "Lucian": "卢锡安",
    "Lulu": "璐璐", "Lux": "拉克丝", "Malphite": "墨菲特", "Maokai": "茂凯",
    "MasterYi": "易大师", "MissFortune": "厄运小姐", "Mordekaiser": "莫德凯撒", "Morgana": "莫甘娜",
    "Nami": "娜美", "Nasus": "内瑟斯", "Nautilus": "诺提勒斯", "Neeko": "妮蔻",
    "Nidalee": "奈德丽", "Nocturne": "魔腾", "Nunu": "努努", "Olaf": "奥拉夫",
    "Orianna": "奥莉安娜", "Ornn": "奥恩", "Pantheon": "潘森", "Poppy": "波比",
    "Pyke": "派克", "Qiyana": "奇亚娜", "Quinn": "奎因", "Rakan": "洛",
    "Rammus": "拉莫斯", "RekSai": "雷克塞", "Rell": "芮尔", "Renata": "蕾娜塔",
    "Renekton": "雷克顿", "Rengar": "雷恩加尔", "Riven": "锐雯", "Rumble": "兰博",
    "Ryze": "瑞兹", "Samira": "莎弥拉", "Sejuani": "瑟庄妮", "Senna": "赛娜",
    "Seraphine": "萨勒芬妮", "Sett": "瑟提", "Shen": "慎", "Shyvana": "希瓦娜",
    "Singed": "辛吉德", "Sion": "赛恩", "Sivir": "希维尔", "Skarner": "斯卡纳",
    "Sona": "娑娜", "Soraka": "索拉卡", "Swain": "斯维因", "Syndra": "辛德拉",
    "TahmKench": "塔姆", "Taliyah": "塔莉垭", "Talon": "泰隆", "Taric": "塔里克",
    "Thresh": "锤石", "Tristana": "崔丝塔娜", "Trundle": "特朗德尔", "Tryndamere": "泰达米尔",
    "TwistedFate": "崔斯特", "Twitch": "图奇", "Udyr": "乌迪尔", "Urgot": "厄加特",
    "Varus": "韦鲁斯", "Vayne": "薇恩", "Veigar": "维迦", "Velkoz": "维克兹",
    "Vi": "蔚", "Viego": "佛耶戈", "Viktor": "维克托", "Vladimir": "弗拉基米尔",
    "Volibear": "沃利贝尔", "Warwick": "沃里克", "Wukong": "孙悟空", "Xayah": "霞",
    "Xerath": "泽拉斯", "XinZhao": "赵信", "Yasuo": "亚索", "Yone": "永恩",
    "Yorick": "约里克", "Yuumi": "悠米", "Zac": "扎克", "Zed": "劫",
    "Zeri": "泽丽", "Ziggs": "吉格斯", "Zilean": "基兰", "Zoe": "佐伊", "Zyra": "婕拉",
    # S18 新英雄 & 野怪
    "Cinderling": "炎魔", "Kobuko": "小库布", "Pebbles": "佩布尔斯",
    "Gromp": "魔沼蛙", "Murkwolf": "暗影狼", "Scuttlecrab": "迅捷蟹",
    "Krug": "石甲虫", "Raptor": "锋喙鸟", "AncientSentinel": "远古哨兵",
    "Brambleback": "红BUFF", "Alune": "阿萝拉", "ElderDragon": "远古巨龙",
    "Yunara": "云娜拉",
}

def _trait_to_cn(name):
    """羁绊英文名转中文"""
    if not name:
        return name
    raw = name
    # 去掉 SetXX_ 前缀
    if '_' in raw:
        raw = raw.split('_', 1)[-1]
    # 去掉 UniqueTrait 或 Trait 后缀
    if raw.endswith("UniqueTrait"):
        raw = raw[:-len("UniqueTrait")]
    elif raw.endswith("Trait"):
        raw = raw[:-len("Trait")]
    # 查映射表
    if raw in _TRAIT_CN_MAP:
        return _TRAIT_CN_MAP[raw]
    return raw

def _champ_to_cn(name):
    """英雄英文名转中文（复用羁绊映射表中的英雄名）"""
    if not name:
        return name
    raw = name
    # 去掉 TFTxx_ 前缀
    if "_" in raw and raw.upper().startswith("TFT"):
        raw = raw.split("_", 1)[-1]
    if raw in _TRAIT_CN_MAP:
        return _TRAIT_CN_MAP[raw]
    return raw

def build_comp_name(traits):
    """
    从羁绊列表构建简易阵容名（中文）。
    取激活度最高的前 3 个羁绊。
    """
    if not traits:
        return ""
    active = [t for t in traits if (t.get("style", 0) or 0) > 0]
    active.sort(key=lambda x: ((x.get("style", 0) or 0), (x.get("num_units", 0) or 0)), reverse=True)
    names = []
    for t in active[:3]:
        raw = t.get("name", "") or ""
        cn = _trait_to_cn(raw)
        if cn:
            names.append(cn)
    return " / ".join(names)

def tft_set_to_season(set_number):
    """TFT set 编号 → 赛季标签（如 11 → S11）"""
    try:
        n = int(set_number)
        if n > 0:
            return f"S{n}"
    except Exception:
        pass
    return "S18"

# ─── SGP（腾讯国服服务端 API）支持 ───
# 国服大区白名单
_TENCENT_SERVERS = {"hn1", "hn10", "bgp2", "tj100", "cq100", "gz100", "nj100", "tj101"}
_K8S_SGP_SERVERS = {"hn1", "hn10", "bgp2"}
_PBE_SERVERS = {"pbe", "pbe1"}  # 美测服
_sgp_token_cache = {"port": 0, "token": "", "time": 0}
_platform_cache = {"port": 0, "platform": None, "time": 0}

def is_tencent_server(platform):
    """判断是否为腾讯国服（支持SGP）"""
    return (platform or "").lower() in _TENCENT_SERVERS

def is_pbe_server(platform):
    """判断是否为美测服"""
    return (platform or "").lower() in _PBE_SERVERS

def _sgp_base_url(platform):
    """根据大区构建 SGP base URL（仅腾讯国服有效）"""
    p = (platform or "").lower()
    if p in _K8S_SGP_SERVERS:
        return f"https://{p}-k8s-sgp.lol.qq.com:21019"
    return f"https://{p}-sgp.lol.qq.com:21019"

def get_sgp_token(port, token):
    """获取 SGP accessToken（/entitlements/v1/token），缓存30分钟"""
    global _sgp_token_cache
    now = time.time()
    if _sgp_token_cache["port"] == port and now - _sgp_token_cache["time"] < 1800 and _sgp_token_cache["token"]:
        return _sgp_token_cache["token"]
    try:
        resp = lcu_get(port, token, "/entitlements/v1/token", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("accessToken", "")
            if access_token:
                _sgp_token_cache = {"port": port, "token": access_token, "time": now}
                return access_token
    except Exception:
        pass
    return None

def get_current_platform(port, token):
    """获取当前大区（如 HN1、BGP2），尝试多个端点；国服但拿不到具体大区时返回 'tencent'。缓存5分钟"""
    global _platform_cache
    now = time.time()
    if _platform_cache["port"] == port and now - _platform_cache["time"] < 300 and _platform_cache["platform"] is not None:
        return _platform_cache["platform"]
    result = None
    # 端点1: platformId 纯文本
    try:
        resp = lcu_get(port, token, "/lol-platform-config/v1/namespaces/LoginDataPacket/platformId", timeout=5)
        if resp.status_code == 200:
            p = resp.text.strip().strip('"').lower()
            if p and p != "null" and len(p) <= 6:
                result = p
    except Exception:
        pass
    # 端点2: login session（含 platformId）
    if not result:
        try:
            resp = lcu_get(port, token, "/lol-login/v1/session", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                p = (data.get("platformId") or data.get("platform_id") or "").lower()
                if p and p != "null":
                    result = p
        except Exception:
            pass
    # 端点3: 判断是否国服
    if not result:
        try:
            resp = lcu_get(port, token, "/riotclient/get_region_locale", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if (data.get("region") or "").upper() == "TENCENT":
                    result = "tencent"  # 国服但具体大区未知
        except Exception:
            pass
    _platform_cache = {"port": port, "platform": result, "time": now}
    return result

def fetch_tft_matches_sgp(puuid, platform, sgp_token, count=100):
    """通过 SGP API 获取云顶战绩（支持分页，可拉历史）"""
    if not platform or not sgp_token:
        return None, "SGP参数缺失"
    base = _sgp_base_url(platform)
    url = f"{base}/match-history-query/v1/products/tft/player/{puuid}/SUMMARY"
    headers = {
        "Authorization": f"Bearer {sgp_token}",
        "Accept": "application/json",
        "User-Agent": "RiotClient/78.0.1.1352 (Windows;10;co;red)",
    }
    all_games = []
    page_size = 20
    start = 0
    try:
        while start < count:
            resp = requests.get(url, headers=headers, params={"startIndex": start, "count": page_size},
                                verify=False, timeout=15)
            if resp.status_code != 200:
                if all_games:
                    break  # 已有数据就返回，否则报错
                return None, f"SGP HTTP {resp.status_code}: {resp.text[:100]}"
            data = resp.json()
            games = []
            if isinstance(data, list):
                games = data
            elif isinstance(data, dict):
                g = data.get("games", [])
                if isinstance(g, list):
                    games = g
                elif isinstance(g, dict):
                    games = g.get("games", [])
            if not games:
                break  # 没有更多数据
            all_games.extend(games)
            if len(games) < page_size:
                break  # 最后一页
            start += page_size
        return all_games[:count], None
    except Exception as e:
        if all_games:
            return all_games[:count], None
        return None, f"SGP异常: {str(e)[:100]}"

def fetch_tft_match_detail_sgp(game_id, platform, sgp_token):
    """通过 SGP API 获取单个对局的详细信息（含8个玩家完整数据）"""
    if not platform or not sgp_token or not game_id:
        return None
    base = _sgp_base_url(platform)
    url = f"{base}/match-history-query/v1/products/tft/{game_id}/DETAILS"
    headers = {
        "Authorization": f"Bearer {sgp_token}",
        "Accept": "application/json",
        "User-Agent": "RiotClient/78.0.1.1352 (Windows;10;co;red)",
    }
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                # 解包 json 字段（SGP风格）
                if "json" in data and isinstance(data["json"], str):
                    try:
                        return json.loads(data["json"])
                    except Exception:
                        pass
                return data
        return None
    except Exception:
        return None

def fetch_tft_matches(port, token, puuid, count=20, source="auto", platform=None):
    """
    获取云顶战绩。
    source: auto(优先SGP回退本地) / sgp(仅SGP) / local(仅本地)
    platform: 手动指定大区（如 hn1），为None时自动检测
    """
    debug_info = []

    # SGP 模式（auto 或 sgp 时尝试）
    if source in ("auto", "sgp"):
        # 优先用手动指定的大区，否则自动检测
        plat = platform or get_current_platform(port, token)
        if plat and plat in _TENCENT_SERVERS:
            sgp_token = get_sgp_token(port, token)
            if sgp_token:
                games, err = fetch_tft_matches_sgp(puuid, plat, sgp_token, count=100)
                debug_info.append(f"SGP({plat}): {'成功'+str(len(games))+'场' if games else err}")
                if games:
                    return games, None
                if source == "sgp":
                    return None, " | ".join(debug_info)
            else:
                debug_info.append("SGP: token获取失败")
                if source == "sgp":
                    return None, " | ".join(debug_info)
        else:
            debug_info.append(f"SGP: 大区不可用({plat})")
            if source == "sgp":
                return None, " | ".join(debug_info)

    # 本地 LCU 模式（auto 或 local 时）
    if source in ("auto", "local"):
        # 1. TFT 专用端点（无参数）
        tft_ep = f"/lol-match-history/v1/products/tft/{puuid}/matches"
    try:
        resp = lcu_get(port, token, tft_ep, timeout=15)
        debug_info.append(f"TFT端点: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # 兼容三种返回结构：直接列表 / {"games":[...]} / {"games":{"games":[...]}}
            games = []
            if isinstance(data, list):
                games = data
                debug_info.append(f"TFT返回直接列表，共{len(games)}场")
            elif isinstance(data, dict):
                g = data.get("games", [])
                if isinstance(g, list):
                    games = g
                elif isinstance(g, dict):
                    games = g.get("games", [])
                debug_info.append(f"TFT返回字典，共{len(games)}场")
            if games:
                return games[:count], None
            debug_info.append("TFT返回空")
        else:
            debug_info.append(f"TFT响应: {resp.text[:100]}")
    except Exception as e:
        debug_info.append(f"TFT异常: {str(e)[:80]}")

    # 2. TFT current-summoner 端点
    tft_cs_ep = "/lol-match-history/v1/products/tft/current-summoner/matches"
    try:
        resp = lcu_get(port, token, tft_cs_ep, timeout=15)
        debug_info.append(f"TFT-CS端点: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            games = []
            if isinstance(data, list):
                games = data
            elif isinstance(data, dict):
                g = data.get("games", [])
                if isinstance(g, list):
                    games = g
                elif isinstance(g, dict):
                    games = g.get("games", [])
            debug_info.append(f"TFT-CS返回{len(games)}场")
            if games:
                return games[:count], None
        else:
            debug_info.append(f"TFT-CS响应: {resp.text[:100]}")
    except Exception as e:
        debug_info.append(f"TFT-CS异常: {str(e)[:80]}")

    # 3. lol 通用端点（支持 begIndex/endIndex），过滤 TFT
    tft_queue_ids = {1090, 1100, 1130, 1160, 1170, 1180}
    lol_ep = f"/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex={count * 3}"
    try:
        resp = lcu_get(port, token, lol_ep, timeout=15)
        debug_info.append(f"LOL端点: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            all_games = data.get("games", {}).get("games", []) if isinstance(data, dict) else []
            tft_games = [g for g in all_games if g.get("queueId", 0) in tft_queue_ids
                         or (g.get("gameMode", "") or "").upper() == "TFT"]
            debug_info.append(f"LOL返回{len(all_games)}场，其中TFT {len(tft_games)}场")
            if tft_games:
                return tft_games[:count], None
        else:
            debug_info.append(f"LOL响应: {resp.text[:100]}")
    except Exception as e:
        debug_info.append(f"LOL异常: {str(e)[:80]}")

    return None, " | ".join(debug_info) or "未获取到对局数据"

def _unwrap_game_json(game):
    """TFT 对局可能嵌套在 json 字段中（SGP 风格），解包返回实际 game 对象"""
    if isinstance(game, dict) and "json" in game:
        j = game["json"]
        if isinstance(j, str):
            try:
                return json.loads(j)
            except Exception:
                return game
        if isinstance(j, dict):
            return j
    # SGP 风格：数据可能在 info 字段里
    if isinstance(game, dict) and "info" in game and isinstance(game["info"], dict):
        info = game["info"]
        # 把 info 里的字段提升到顶层，保留 metadata
        result = dict(game)
        result.update(info)
        return result
    return game

def _get_participants(game):
    """从 TFT 对局数据中获取所有参与者列表，兼容多种数据结构"""
    if not isinstance(game, dict):
        return []
    # 直接在顶层
    parts = game.get("participants", [])
    if isinstance(parts, list) and parts:
        return parts
    # 在 info 里（Riot API 风格）
    info = game.get("info", {})
    if isinstance(info, dict):
        parts = info.get("participants", [])
        if isinstance(parts, list) and parts:
            return parts
    # 在 json 里（SGP 风格）
    j = game.get("json", {})
    if isinstance(j, dict):
        parts = j.get("participants", [])
        if isinstance(parts, list) and parts:
            return parts
        info = j.get("info", {})
        if isinstance(info, dict):
            parts = info.get("participants", [])
            if isinstance(parts, list) and parts:
                return parts
    return []

def _get_participant_identities(game):
    """获取参与者身份信息，兼容多种数据结构"""
    if not isinstance(game, dict):
        return []
    identities = game.get("participantIdentities", [])
    if isinstance(identities, list) and identities:
        return identities
    info = game.get("info", {})
    if isinstance(info, dict):
        identities = info.get("participantIdentities", [])
        if isinstance(identities, list) and identities:
            return identities
    # metadata.participants 是 puuid 列表
    meta = game.get("metadata", {})
    if isinstance(meta, dict):
        puuids = meta.get("participants", [])
        if isinstance(puuids, list) and puuids:
            return [{"player": {"puuid": p, "gameName": "", "summonerName": ""}} for p in puuids]
    return []

def _get_p_stat(p, key, default=None):
    """从 participant 或其 stats 子对象中获取字段（TFT 数据常放在 stats 里）"""
    if not isinstance(p, dict):
        return default
    if key in p:
        return p[key]
    stats = p.get("stats", {})
    if isinstance(stats, dict) and key in stats:
        return stats[key]
    return default

def sync_lcu_matches_impl(user_id, season_filter=None, source="auto", platform=None):
    """
    核心同步逻辑：拉取最近云顶对局，去重后入库。
    返回 (new_count, skip_count, message)
    """
    port, token = get_lcu_credentials()
    if not port or not token:
        return 0, 0, "未检测到运行中的英雄联盟客户端，请先启动游戏"

    summoner = fetch_current_summoner(port, token)
    if not summoner or not summoner.get("puuid"):
        return 0, 0, "无法获取当前召唤师信息，请确认已登录客户端"
    puuid = summoner["puuid"]

    games, err = fetch_tft_matches(port, token, puuid, count=20, source=source, platform=platform)
    if err:
        return 0, 0, f"获取战绩失败: {err}"
    if not games:
        return 0, 0, "近期没有云顶对局记录"

    ranked = get_tft_ranked(port, token)

    # 获取SGP token，用于补全对局详情
    sgp_token = None
    sgp_platform = platform or get_current_platform(port, token)
    if sgp_platform and sgp_platform in _TENCENT_SERVERS:
        sgp_token = get_sgp_token(port, token)

    new_count = 0
    skip_count = 0
    debug_saved = False
    conn = get_conn()
    c = conn.cursor()

    for raw_game in games:
        game = _unwrap_game_json(raw_game)
        if not isinstance(game, dict):
            skip_count += 1
            continue

        game_id = game.get("gameId") or game.get("game_id")
        if not game_id:
            skip_count += 1
            continue

        # 如果对局没有participants，用SGP DETAILS补全
        if not _get_participants(game) and sgp_token and sgp_platform:
            detail = fetch_tft_match_detail_sgp(game_id, sgp_platform, sgp_token)
            if detail and isinstance(detail, dict):
                # 合并详情数据到game中
                detail_unwrapped = _unwrap_game_json(detail)
                if _get_participants(detail_unwrapped):
                    game.update(detail_unwrapped)
                elif _get_participants(detail):
                    game.update(detail)

        # 调试：保存第一个对局的参与者数据结构
        if not debug_saved:
            try:
                debug_data = {
                    "game_keys": list(game.keys()),
                    "participants_sample": [],
                    "participantIdentities": _get_participant_identities(game)[:2] if _get_participant_identities(game) else [],
                }
                parts = _get_participants(game)
                if parts:
                    debug_data["participants_sample"] = [
                        {k: (str(v)[:100] if not isinstance(v, (dict, list)) else type(v).__name__)
                         for k, v in parts[0].items()}
                    ]
                    if len(parts) > 0 and "stats" in parts[0] and isinstance(parts[0]["stats"], dict):
                        debug_data["stats_keys"] = list(parts[0]["stats"].keys())
                import os
                debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_participants.json")
                with open(debug_path, "w", encoding="utf-8") as f:
                    json.dump(debug_data, f, ensure_ascii=False, indent=2)
                debug_saved = True
            except Exception:
                pass

        # 构建 participantId → puuid 映射（召唤师峡谷风格数据需要）
        pid_to_puuid = {}
        for ident in _get_participant_identities(game):
            if isinstance(ident, dict):
                pid = ident.get("participantId")
                player = ident.get("player", {}) if isinstance(ident.get("player"), dict) else {}
                p_puuid = player.get("puuid") or player.get("currentPuuid")
                if pid and p_puuid:
                    pid_to_puuid[pid] = p_puuid

        # 找到自己的 participant
        my_p = None
        for p in _get_participants(game):
            if not isinstance(p, dict):
                continue
            p_puuid = p.get("puuid") or _get_p_stat(p, "puuid")
            if not p_puuid:
                pid = p.get("participantId")
                p_puuid = pid_to_puuid.get(pid)
            if p_puuid == puuid:
                my_p = p
                break
        if not my_p:
            skip_count += 1
            continue

        # 名次：TFT 中 placement 可能在 stats 里，也可能叫 rank
        placement = _get_p_stat(my_p, "placement") or _get_p_stat(my_p, "rank") or 0
        try:
            placement = int(placement)
        except Exception:
            placement = 0
        if placement < 1 or placement > 8:
            skip_count += 1
            continue

        # 对局时间：TFT 用 gameCreation，召唤师峡谷用 gameCreationDate
        creation_ms = game.get("gameCreation") or game.get("gameCreationDate") or 0
        try:
            game_time = datetime.fromtimestamp(int(creation_ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            game_time = safe_now_str()

        # 赛季：优先用游戏内的 set 编号
        tft_set = game.get("tftSetNumber") or game.get("tft_set_number") or 0
        game_season = tft_set_to_season(tft_set) if tft_set else (season_filter or "S18")

        # 段位（用当前段位作为近似，用户可后续编辑）
        tier = ranked["tier"] if ranked else ""
        division = ranked["division"] if ranked else "-"
        lp = ranked["lp"] if ranked else 0

        # 阵容名：traits 可能在 stats 里
        traits = _get_p_stat(my_p, "traits", []) or []
        comp = build_comp_name(traits)

        # 英雄列表：units 可能在 stats 里
        units = _get_p_stat(my_p, "units", []) or []
        unit_names = []
        for u in units:
            if not isinstance(u, dict):
                continue
            name = u.get("name") or u.get("character_id") or u.get("characterId") or ""
            if name:
                # 去掉 TFTxx_ 前缀，如 TFT11_Ahri → Ahri
                if "_" in name and name.upper().startswith("TFT"):
                    name = name.split("_", 1)[-1]
                # 转中文
                name = _champ_to_cn(name)
                unit_names.append(name)
        units_json = json.dumps(unit_names, ensure_ascii=False) if unit_names else ""

        # 按 game_id 去重；已有记录则更新羁绊名和英雄名（中文转换）
        c.execute("SELECT id FROM matches WHERE game_id=?", (game_id,))
        existing = c.fetchone()

        # 保存这局所有玩家的信息（每次都删旧数据重新保存，确保名字能更新）
        c.execute("DELETE FROM match_players WHERE game_id=?", (game_id,))
        all_participants = _get_participants(game)
        # 构建 puuid → 游戏名 映射
        name_map = {}
        for ident in _get_participant_identities(game):
            if isinstance(ident, dict):
                player = ident.get("player", {}) if isinstance(ident.get("player"), dict) else {}
                p_puuid = player.get("puuid") or player.get("currentPuuid")
                p_name = player.get("gameName") or player.get("summonerName") or player.get("riotId") or ""
                if p_puuid and p_name:
                    name_map[p_puuid] = p_name
        for p in all_participants:
            if not isinstance(p, dict):
                continue
            p_puuid = p.get("puuid") or _get_p_stat(p, "puuid")
            if not p_puuid:
                pid = p.get("participantId")
                p_puuid = pid_to_puuid.get(pid, "")
            p_name = name_map.get(p_puuid, "")
            if not p_name:
                riot_name = p.get("riotIdGameName") or _get_p_stat(p, "riotIdGameName") or ""
                riot_tag = p.get("riotIdTagline") or _get_p_stat(p, "riotIdTagline") or ""
                if riot_name:
                    p_name = f"{riot_name}#{riot_tag}" if riot_tag else riot_name
            if not p_name:
                p_name = _get_p_stat(p, "summonerName") or _get_p_stat(p, "gameName") or _get_p_stat(p, "displayName") or _get_p_stat(p, "name") or ""
            if not p_name:
                pid = p.get("participantId") or 0
                p_name = f"玩家{pid}" if pid else "召唤师"
            p_placement = _get_p_stat(p, "placement") or _get_p_stat(p, "rank") or 0
            try:
                p_placement = int(p_placement)
            except Exception:
                p_placement = 0
            p_traits = _get_p_stat(p, "traits", []) or []
            p_comp = build_comp_name(p_traits)
            p_units = _get_p_stat(p, "units", []) or []
            p_unit_names = []
            for u in p_units:
                if isinstance(u, dict):
                    uname = u.get("name") or u.get("character_id") or ""
                    if uname:
                        if "_" in uname and uname.upper().startswith("TFT"):
                            uname = uname.split("_", 1)[-1]
                        uname = _champ_to_cn(uname)
                        p_unit_names.append(uname)
            p_units_json = json.dumps(p_unit_names, ensure_ascii=False) if p_unit_names else ""
            is_self = 1 if p_puuid == puuid else 0
            c.execute("""
                INSERT INTO match_players(game_id, puuid, summoner_name, placement, tier, division, lp, comp, units, is_self, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                int(game_id), p_puuid, p_name, p_placement,
                tier if is_self else "", division if is_self else "-", lp if is_self else 0,
                p_comp, p_units_json, is_self, safe_now_str()
            ))

        if existing:
            c.execute("UPDATE matches SET comp=?, units=? WHERE id=?", (comp, units_json, existing["id"]))
            skip_count += 1
            continue

        c.execute("""
            INSERT INTO matches(user_id, placement, tier, division, lp, comp, time, season, game_id, units, rank, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(user_id), placement, tier, division, int(lp),
            comp, game_time, game_season, int(game_id), units_json,
            ranked.get("rank") if ranked else None,
            safe_now_str()
        ))
        new_count += 1

    # 补全玩家名字：查询所有名字为空的玩家，通过puuid批量查询
    c.execute("SELECT DISTINCT puuid FROM match_players WHERE (summoner_name = '' OR summoner_name IS NULL) AND puuid != ''")
    empty_puuids = [row[0] for row in c.fetchall()]
    if empty_puuids:
        name_map = fetch_summoners_by_puuids(port, token, empty_puuids)
        for puuid, name in name_map.items():
            if name:
                c.execute("UPDATE match_players SET summoner_name = ? WHERE puuid = ? AND (summoner_name = '' OR summoner_name IS NULL)", (name, puuid))

    conn.commit()
    conn.close()
    return new_count, skip_count, None

# =========================
# 自动同步监控（后台线程）
# =========================
AUTO_SYNC_ENABLED = True
_last_gameflow_phase = None
_auto_sync_user_id = None
_auto_sync_lock = threading.Lock()
_auto_sync_cooldown = 0  # 时间戳，避免短时间重复触发

def set_auto_sync_user(user_id):
    global _auto_sync_user_id
    _auto_sync_user_id = int(user_id) if user_id else None

def _auto_sync_worker():
    """
    后台轮询 gameflow 阶段。
    检测到从 InProgress → PreEndOfGame/EndOfGame 时，等待几秒后自动同步。
    """
    global _last_gameflow_phase, _auto_sync_cooldown
    while True:
        try:
            if not AUTO_SYNC_ENABLED:
                time.sleep(5)
                continue

            port, token = get_lcu_credentials()
            if not port or not token:
                _last_gameflow_phase = None
                time.sleep(10)
                continue

            resp = lcu_get(port, token, "/lol-gameflow/v1/gameflow-phase", timeout=5)
            if resp.status_code != 200:
                time.sleep(5)
                continue

            phase = (resp.json().get("phase", "") or "").strip()
            now = time.time()

            # 对局结束判定：上一阶段在游戏中，当前阶段进入结算
            in_game_phases = ("InProgress", "Reconnect", "WaitingForStats")
            end_phases = ("PreEndOfGame", "EndOfGame")

            if (_last_gameflow_phase in in_game_phases and phase in end_phases
                    and _auto_sync_user_id and now > _auto_sync_cooldown):
                _auto_sync_cooldown = now + 60  # 60 秒冷却
                time.sleep(10)  # 等结算数据落库
                with _auto_sync_lock:
                    new_cnt, skip_cnt, err = sync_lcu_matches_impl(_auto_sync_user_id)
                if err:
                    try:
                        eel.on_auto_sync(f"自动同步: {err}", "error")()
                    except Exception:
                        pass
                elif new_cnt > 0:
                    try:
                        eel.on_auto_sync(f"自动同步: 新增 {new_cnt} 条对局", "success")()
                        eel.trigger_refresh()()
                    except Exception:
                        pass

            _last_gameflow_phase = phase
        except Exception:
            pass
        time.sleep(5)

# =========================
# 段位与统计（原有逻辑不变）
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
# 托盘与窗口控制（原有逻辑不变）
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
    global FRONTEND_ALIVE
    w = find_app_window()
    if FRONTEND_ALIVE and w is not None:
        try:
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

def on_tray_augment(icon, item, stage):
    try:
        augment_overlay.show_augment_overlay(stage)
    except:
        pass

def on_tray_augment_off(icon, item):
    try:
        augment_overlay.hide_augment_overlay()
    except:
        pass

def run_tray():
    global tray_icon
    tray_icon = pystray.Icon(
        "tft_assistant_tray",
        build_tray_image(),
        APP_TITLE,
        pystray.Menu(
            pystray.MenuItem("显示主面板", on_tray_show),
            pystray.MenuItem("海克斯评级", pystray.Menu(
                pystray.MenuItem("2-1 阶段", lambda icon,item: on_tray_augment(icon,item,2)),
                pystray.MenuItem("3-2 阶段", lambda icon,item: on_tray_augment(icon,item,3)),
                pystray.MenuItem("4-2 阶段", lambda icon,item: on_tray_augment(icon,item,4)),
                pystray.MenuItem("关闭评级", on_tray_augment_off),
            )),
            pystray.MenuItem("退出程序", on_tray_exit),
        ),
    )
    tray_icon.run()

# =========================
# 对局内：牌池追踪 & 对手情报
# =========================
def calc_pool_taken(my_units, opponent_units_list=None, opponent_units_dict=None):
    """计算已被拿的牌数 {champ_id: count}
    my_units: [{id, star}]
    opponent_units_list: [[{id, star}], ...]  可选
    opponent_units_dict: {champ_id: count}  可选（更高效）
    """
    taken = {}
    star_to_count = {1: 1, 2: 3, 3: 9}
    for u in my_units:
        cid = u["id"]
        cnt = star_to_count.get(u.get("star", 1), 1)
        taken[cid] = taken.get(cid, 0) + cnt
    if opponent_units_list:
        for opp_units in opponent_units_list:
            for u in opp_units:
                cid = u["id"]
                cnt = star_to_count.get(u.get("star", 1), 1)
                taken[cid] = taken.get(cid, 0) + cnt
    if opponent_units_dict:
        for cid, cnt in opponent_units_dict.items():
            taken[cid] = taken.get(cid, 0) + cnt
    return taken

def get_pool_remaining(champ_id, cost, taken):
    """获取某英雄牌池剩余"""
    total = POOL_SIZE.get(cost, 20)
    used = taken.get(champ_id, 0)
    return max(0, total - used)

def check_three_star_alerts(my_units, taken):
    """三星预警：差3张时预警
    返回 [{champ_id, name, owned, needed, remaining, cost, probability}]
    """
    alerts = []
    star_to_count = {1: 1, 2: 3, 3: 9}
    # 统计自己拥有的每个英雄总数
    owned_map = {}
    for u in my_units:
        cid = u["id"]
        cnt = star_to_count.get(u.get("star", 1), 1)
        owned_map[cid] = owned_map.get(cid, 0) + cnt
    for cid, owned in owned_map.items():
        if owned >= THREE_STAR_REQUIRED:
            continue  # 已经三星
        needed = THREE_STAR_REQUIRED - owned
        if needed > THREE_STAR_ALERT_THRESHOLD:
            continue  # 差超过3张，不预警
        cost = get_champ_cost(cid)
        remaining = get_pool_remaining(cid, cost, taken)
        if remaining <= 0:
            probability = "不可能"
        elif remaining >= needed * 2:
            probability = "高"
        elif remaining >= needed:
            probability = "中"
        else:
            probability = "低"
        alerts.append({
            "champ_id": cid,
            "name": _champ_to_cn(cid),
            "owned": owned,
            "needed": needed,
            "remaining": remaining,
            "cost": cost,
            "probability": probability,
        })
    # 按需要的张数升序（越接近三星越靠前）
    alerts.sort(key=lambda x: x["needed"])
    return alerts

def fetch_opponent_recent_info(puuid, platform, sgp_token):
    """查询单个对手的最近战绩信息和段位"""
    info = {"tier": "未知", "wins": 0, "recent_comps": [], "avg_placement": 0, "games": 0}
    try:
        # 1. 查询段位（尝试SGP多个端点）
        tier_info = fetch_summoner_tier_sgp(puuid, platform, sgp_token)
        if tier_info:
            info["tier"] = tier_info

        # 2. 查询最近战绩
        matches = fetch_tft_matches_sgp(puuid, platform, sgp_token, count=10)
        if matches:
            placements = []
            comps = []
            for m in matches[:10]:
                p = m.get("placement", 0)
                if p:
                    placements.append(p)
                comp = m.get("comp", "")
                if comp:
                    comps.append(comp)
            if placements:
                info["avg_placement"] = round(sum(placements) / len(placements), 1)
                info["wins"] = placements.count(1)
                info["games"] = len(placements)
                # 如果段位还是未知，根据场均名次推断
                if info["tier"] == "未知":
                    avg = sum(placements) / len(placements)
                    if avg <= 2.5:
                        info["tier"] = "大师+"
                    elif avg <= 3.5:
                        info["tier"] = "钻石"
                    elif avg <= 4.2:
                        info["tier"] = "翡翠"
                    elif avg <= 4.8:
                        info["tier"] = "铂金"
                    else:
                        info["tier"] = "黄金及以下"
            if comps:
                from collections import Counter
                info["recent_comps"] = [c for c, _ in Counter(comps).most_common(3)]
    except Exception:
        pass
    return info

def fetch_summoner_tier_sgp(puuid, platform, sgp_token):
    """通过SGP查询召唤师段位，尝试多个端点"""
    if not platform or not sgp_token or not puuid:
        return None
    base = _sgp_base_url(platform)
    headers = {
        "Authorization": f"Bearer {sgp_token}",
        "Accept": "application/json",
        "User-Agent": "RiotClient/78.0.1.1352 (Windows;10;co;red)",
    }
    # 尝试多个端点
    endpoints = [
        f"/league/v1/entries/by-puuid/{puuid}",
        f"/ranked/v1/stats/{puuid}",
        f"/summoner/v1/summoners/{puuid}/ranked",
        f"/tft/league/v1/entries/by-puuid/{puuid}",
        f"/match-history-query/v1/products/tft/player/{puuid}/RANKED",
    ]
    for ep in endpoints:
        try:
            url = f"{base}{ep}"
            resp = requests.get(url, headers=headers, verify=False, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                # 解析段位数据
                tier = parse_tier_from_data(data)
                if tier:
                    return tier
        except Exception:
            continue
    return None

def parse_tier_from_data(data):
    """从各种返回数据中解析段位"""
    if not data:
        return None
    # 列表格式：[{queueType, tier, rank, leaguePoints}]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                qtype = (item.get("queueType", "") or "").upper()
                if "TFT" in qtype or "RANKED_TFT" in qtype:
                    tier = item.get("tier", "")
                    if tier:
                        division = item.get("rank", "")
                        lp = item.get("leaguePoints", 0)
                        tier_cn = TIER_EN_TO_CN.get(tier.upper(), tier)
                        return f"{tier_cn} {division} {lp}LP" if division else tier_cn
        # 取第一个
        if data and isinstance(data[0], dict):
            tier = data[0].get("tier", "")
            if tier:
                return TIER_EN_TO_CN.get(tier.upper(), tier)
    # 字典格式
    if isinstance(data, dict):
        # 可能直接有tier字段
        tier = data.get("tier", "") or data.get("rank", "")
        if tier:
            return TIER_EN_TO_CN.get(tier.upper(), tier)
        # 可能有queueMap
        queue_map = data.get("queueMap", {})
        if isinstance(queue_map, dict):
            for key, q in queue_map.items():
                if isinstance(q, dict) and "TFT" in key.upper():
                    tier = q.get("tier", "")
                    if tier:
                        division = q.get("division", "")
                        lp = q.get("leaguePoints", 0)
                        tier_cn = TIER_EN_TO_CN.get(tier.upper(), tier)
                        return f"{tier_cn} {division} {lp}LP" if division else tier_cn
    return None

def batch_fetch_opponents_info(players, platform, sgp_token):
    """批量查询对手情报（排除自己）"""
    result = {}
    my_puuid = ""
    port, token = get_lcu_credentials()
    if port and token:
        me = fetch_current_summoner(port, token)
        if me:
            my_puuid = me.get("puuid", "")
    for p in players:
        puuid = p.get("puuid", "")
        if not puuid or puuid == my_puuid:
            continue
        info = fetch_opponent_recent_info(puuid, platform, sgp_token)
        info["name"] = p.get("name", "未知")
        result[puuid] = info
    return result

# =========================
# 英雄头像 & 截图识别
# =========================
def get_champ_icon_path(champ_id):
    """获取英雄头像本地路径，不存在则下载"""
    if not champ_id:
        return None
    # 清理ID
    cid = champ_id
    if "_" in cid and cid.upper().startswith("TFT"):
        cid = cid.split("_", 1)[-1]
    path = os.path.join(ICON_DIR, f"{cid}.png")
    if os.path.exists(path):
        return path
    # 尝试从 Community Dragon 下载
    urls = [
        f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/tftchampions/{cid}.png",
        f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{cid}.png",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return path
        except Exception:
            continue
    return None

@eel.expose
def get_champ_icon(champ_id):
    """获取英雄头像，返回base64或路径"""
    path = get_champ_icon_path(champ_id)
    if path and os.path.exists(path):
        # 返回文件URL供前端使用
        return f"file:///{path.replace(os.sep, '/')}"
    return None

@eel.expose
def preload_icons(champ_ids):
    """预下载多个英雄头像"""
    count = 0
    for cid in champ_ids:
        if get_champ_icon_path(cid):
            count += 1
    return count

# 截图识别
try:
    import cv2
    import numpy as np
    import mss
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

def capture_screen(region=None):
    """截取屏幕，可指定区域 (left, top, width, height)"""
    if not HAS_CV2:
        return None
    try:
        with mss.mss() as sct:
            if region:
                monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
            else:
                monitor = sct.monitors[1]  # 主显示器
            img = np.array(sct.grab(monitor))
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None

# 模板缓存
_template_cache = {}

def _get_template(champ_id, target_size=64):
    """获取并缓存英雄头像模板"""
    key = f"{champ_id}_{target_size}"
    if key in _template_cache:
        return _template_cache[key]
    icon_path = get_champ_icon_path(champ_id)
    if not icon_path or not os.path.exists(icon_path):
        return None
    try:
        template = cv2.imread(icon_path)
        if template is None:
            return None
        h, w = template.shape[:2]
        scale = target_size / max(h, w)
        template = cv2.resize(template, (int(w*scale), int(h*scale)))
        _template_cache[key] = template
        return template
    except Exception:
        return None

def match_champion_on_screen(screen_img, champ_id, threshold=0.55):
    """在屏幕上匹配某个英雄，返回匹配数量（多尺度）"""
    if not HAS_CV2 or screen_img is None:
        return 0
    # 多尺度匹配 - 更多尺度覆盖不同分辨率
    total_matches = []
    for scale in [0.5, 0.65, 0.8, 0.95, 1.1, 1.25, 1.4, 1.6]:
        template = _get_template(champ_id, int(48 * scale))
        if template is None:
            continue
        th, tw = template.shape[:2]
        if th > screen_img.shape[0] or tw > screen_img.shape[1]:
            continue
        try:
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= threshold)
            points = list(zip(*locations[::-1]))
            total_matches.extend(points)
        except Exception:
            continue
    if not total_matches:
        return 0
    # 去重：合并距离过近的匹配
    unique = []
    for p in total_matches:
        if all(abs(p[0]-u[0]) > 35 or abs(p[1]-u[1]) > 35 for u in unique):
            unique.append(p)
    return len(unique)

@eel.expose
def scan_opponent_board(champ_ids=None):
    """截图识别当前屏幕上的英雄（棋盘+商店）"""
    if not HAS_CV2:
        return {"status": "error", "msg": "未安装opencv"}
    found = {}
    
    # 1. 识别棋盘区域（中间大部分）
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            w, h = monitor["width"], monitor["height"]
            board_region = (int(w*0.05), int(h*0.05), int(w*0.9), int(h*0.75))
            shop_region = (int(w*0.25), int(h*0.82), int(w*0.5), int(h*0.12))
    except Exception:
        board_region = None
        shop_region = None
    
    # 识别棋盘
    board_img = capture_screen(board_region)
    if board_img is not None:
        if champ_ids is None:
            champ_ids = list(S18_CHAMPS.keys())
        for cid in champ_ids:
            count = match_champion_on_screen(board_img, cid)
            if count > 0:
                found[cid] = found.get(cid, 0) + count
    
    # 2. 识别商店（底部5个英雄）
    shop_img = capture_screen(shop_region)
    if shop_img is not None:
        for cid in (champ_ids or list(S18_CHAMPS.keys())):
            count = match_champion_on_screen(shop_img, cid, threshold=0.6)
            if count > 0:
                found[cid] = found.get(cid, 0) + count
    
    # 调试：保存截图
    try:
        if board_img is not None:
            cv2.imwrite(os.path.join(os.path.dirname(__file__), "debug_board_screen.png"), board_img)
        if shop_img is not None:
            cv2.imwrite(os.path.join(os.path.dirname(__file__), "debug_shop_screen.png"), shop_img)
    except Exception:
        pass
    
    return {"status": "success", "found": found, "total": sum(found.values())}

@eel.expose
def add_opponent_units(units_dict):
    """将识别到的对手牌加入全局牌池统计，并持久化到数据库"""
    if not isinstance(units_dict, dict):
        return {"status": "error", "msg": "参数错误"}
    with _live_lock:
        if "opponent_units" not in _live_state:
            _live_state["opponent_units"] = {}
        for cid, count in units_dict.items():
            if cid and count > 0:
                _live_state["opponent_units"][cid] = _live_state["opponent_units"].get(cid, 0) + count
        # 重新计算全局牌池
        my_units = _live_state["my_board"].get("units", [])
        _live_state["pool_taken"] = calc_pool_taken(my_units, opponent_units_dict=_live_state["opponent_units"])
        # 重新计算三星预警
        _live_state["three_star_alerts"] = check_three_star_alerts(my_units, _live_state["pool_taken"])
    # 持久化到数据库
    try:
        conn = get_conn()
        c = conn.cursor()
        game_id = _live_state.get("current_game_id", "")
        for cid, count in units_dict.items():
            if cid and count > 0:
                c.execute("INSERT INTO opponent_units(game_id, puuid, champ_id, count, created_at) VALUES(?,?,?,?,?)",
                          (str(game_id) if game_id else "", "", cid, int(count), safe_now_str()))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"status": "success", "total_opponent_units": sum(_live_state.get("opponent_units", {}).values())}

@eel.expose
def clear_opponent_units():
    """清空已识别的对手牌"""
    with _live_lock:
        _live_state["opponent_units"] = {}
        # 重新计算牌池（只有自己的）
        my_units = _live_state["my_board"].get("units", [])
        _live_state["pool_taken"] = calc_pool_taken(my_units)
        _live_state["three_star_alerts"] = check_three_star_alerts(my_units, _live_state["pool_taken"])
    return {"status": "success"}

# S18 英雄列表（用于截图识别）
S18_CHAMPS = {
    "Akali": 1, "Camille": 1, "Cinderling": 1, "Karma": 1, "Kobuko": 1,
    "Leona": 1, "Ornn": 1, "Pebbles": 1, "Rakan": 1, "RekSai": 1,
    "Varus": 1, "Veigar": 1, "Xayah": 1, "Yorick": 1,
    "Alistar": 2, "Caitlyn": 2, "Elise": 2, "Gromp": 2, "Kayle": 2,
    "LeBlanc": 2, "Murkwolf": 2, "Scuttlecrab": 2, "Sejuani": 2, "Shen": 2,
    "Teemo": 2, "Warwick": 2, "Yunara": 2,
    "Azir": 3, "Cassiopeia": 3, "Diana": 3, "Fiddlesticks": 3, "Hecarim": 3,
    "KhaZix": 3, "KogMaw": 3, "Krug": 3, "MasterYi": 3, "Rammus": 3,
    "Raptor": 3, "Rengar": 3, "Tristana": 3, "Vi": 3,
    "Ahri": 4, "Amumu": 4, "AncientSentinel": 4, "Aphelios": 4, "Brambleback": 4,
    "Ezreal": 4, "Lillia": 4, "Malphite": 4, "Morgana": 4, "Nidalee": 4,
    "Sett": 4, "Sivir": 4, "Soraka": 4, "Zyra": 4,
    "Alune": 5, "Ashe": 5, "Draven": 5, "ElderDragon": 5, "Gnar": 5,
    "Ivern": 5, "Kennen": 5, "Lux": 5, "Maokai": 5, "Taric": 5,
}

# =========================
# Eel API
# =========================
@eel.expose
def get_client_info():
    port, token = get_lcu_credentials()
    if not port or not token:
        # 诊断：检查各方式为何失败
        detail = []
        if HAS_PSUTIL:
            detail.append(f"psutil {psutil.__version__}（>=5.7可能AccessDenied，建议5.6.5）")
        else:
            detail.append("psutil未安装")
        detail.append("lockfile路径已检查")
        detail.append("wmic需管理员权限")
        return {"status": "error", "msg": "未检测到运行中的英雄联盟客户端", "detail": "；".join(detail)}
    info = fetch_current_summoner(port, token)
    if info:
        # 检测 SGP 可用性
        platform = get_current_platform(port, token)
        sgp_available = False
        sgp_msg = "本地模式"
        need_platform = False
        if platform == "tencent":
            sgp_msg = "国服 · 请选择大区"
            need_platform = True
        elif platform and platform in _TENCENT_SERVERS:
            sgp_token = get_sgp_token(port, token)
            if sgp_token:
                sgp_available = True
                sgp_msg = f"SGP · {platform.upper()}"
            else:
                sgp_msg = f"SGP token失败 · {platform.upper()}"
        elif platform:
            sgp_msg = f"非国服大区 · {platform.upper()}"
        return {
            "status": "success",
            "riot_id": info["riot_id"],
            "puuid": info.get("puuid", ""),
            "port": port,
            "sgp_available": sgp_available,
            "sgp_msg": sgp_msg,
            "need_platform": need_platform,
        }
    return {"status": "error", "msg": f"已连接LCU端口{port}，但获取召唤师信息失败（可能未登录）"}

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
    set_auto_sync_user(uid)
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
def add_match(user_id, placement, tier, division, lp, comp, t, season, units=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matches(user_id, placement, tier, division, lp, comp, time, season, units, created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        int(user_id), int(placement), str(tier or ""),
        str(division or "-"), int(lp or 0), str(comp or ""),
        normalize_time(t), str(season or "S18"), str(units or ""), safe_now_str()
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@eel.expose
def update_match(match_id, placement, tier, division, lp, comp, t, season, units=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE matches
        SET placement=?, tier=?, division=?, lp=?, comp=?, time=?, season=?, units=?
        WHERE id=?
    """, (
        int(placement), str(tier or ""), str(division or "-"),
        int(lp or 0), str(comp or ""), normalize_time(t),
        str(season or "S18"), str(units or ""), int(match_id)
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
def export_csv(user_id, season):
    """导出当前赛季战绩为CSV，返回文件路径"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT placement, tier, division, lp, comp, units, time, season
        FROM matches WHERE user_id=? AND season=? ORDER BY datetime(time) DESC
    """, (int(user_id), season))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return {"status": "error", "msg": "没有可导出的数据"}
    import csv
    path = os.path.join(BASE_DIR, f"tft_export_{season}_{int(time.time())}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["名次", "段位", "小段", "LP", "阵容", "英雄", "时间", "赛季"])
        for r in rows:
            units_str = ""
            if r["units"]:
                try:
                    units_str = " ".join(json.loads(r["units"]))
                except Exception:
                    units_str = r["units"]
            writer.writerow([r["placement"], r["tier"], r["division"], r["lp"],
                             r["comp"], units_str, r["time"], r["season"]])
    return {"status": "success", "path": path, "count": len(rows)}

@eel.expose
def get_match_detail(match_id):
    """获取单条对局详情（含所有玩家）"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE id=?", (int(match_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"status": "error", "msg": "对局不存在"}
    # 查询这局所有玩家
    c.execute("SELECT * FROM match_players WHERE game_id=? ORDER BY placement", (row["game_id"],))
    players = [dict(p) for p in c.fetchall()]
    conn.close()
    return {"status": "success", "data": dict(row), "players": players}

@eel.expose
def backup_db():
    """备份数据库到 backup 目录"""
    import shutil
    backup_dir = os.path.join(BASE_DIR, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"tft_backup_{timestamp}.db")
    try:
        shutil.copy2(DB_PATH, backup_path)
        # 只保留最近10个备份
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)
        for old in backups[10:]:
            os.remove(os.path.join(backup_dir, old))
        return {"status": "success", "path": backup_path}
    except Exception as e:
        return {"status": "error", "msg": str(e)[:100]}

@eel.expose
def list_backups():
    """列出所有备份文件"""
    backup_dir = os.path.join(BASE_DIR, "backup")
    if not os.path.exists(backup_dir):
        return {"status": "success", "backups": []}
    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith(".db"):
            path = os.path.join(backup_dir, f)
            size = os.path.getsize(path)
            backups.append({"name": f, "size": size, "path": path})
    return {"status": "success", "backups": backups}

@eel.expose
def sync_lcu_matches(user_id, season, source="auto", platform=None):
    """前端同步按钮调用，source: auto/local/sgp，platform: 手动指定大区"""
    new_cnt, skip_cnt, err = sync_lcu_matches_impl(int(user_id), season, source=source, platform=platform)
    if err:
        return {"status": "error", "msg": err}
    src_label = {"auto": "自动", "local": "本地", "sgp": "SGP"}.get(source, source)
    if new_cnt > 0:
        return {"status": "success", "msg": f"[{src_label}] 同步完成：新增 {new_cnt} 条，跳过 {skip_cnt} 条重复"}
    return {"status": "success", "msg": f"[{src_label}] 没有新对局（跳过 {skip_cnt} 条重复）"}

@eel.expose
def get_stats(user_id, season):
    user_id = int(user_id)
    season = str(season or "S18")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, placement, tier, division, lp, comp, time, season, units, rank
        FROM matches
        WHERE user_id=? AND season=?
        ORDER BY datetime(time) DESC, id DESC
    """, (user_id, season))
    rows = c.fetchall()
    history = [dict(r) for r in rows]
    # 计算每局胜点变化（流量）：用段位总分差值，考虑晋升/降级
    net_lp = 0
    for i in range(len(history)):
        cur = history[i]
        cur_score = tier_score(cur["tier"], cur["division"], cur["lp"])
        if i + 1 < len(history):
            prev = history[i + 1]
            prev_score = tier_score(prev["tier"], prev["division"], prev["lp"])
            cur["lp_delta"] = cur_score - prev_score
            net_lp += cur["lp_delta"]
        else:
            cur["lp_delta"] = None  # 最早一局无前序数据
    total = len(history)
    if total == 0:
        conn.close()
        return {
            "total": 0, "avg_placement": "0.0", "win_rate": "0%",
            "top4_rate": "0%", "distribution": {i: 0 for i in range(1, 9)},
            "history": [], "daily_stats": [], "highest_season": "无记录"
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
            "day": day, "full_day": day, "games_count": cnt,
            "avg_placement": ap, "tier_score": ts, "tier_label": label
        })
    highest = highest_season_label(history)
    # 最高排名（rank越小越高，只取有值的）
    ranks = [int(r["rank"]) for r in history if r.get("rank")]
    highest_rank = min(ranks) if ranks else None
    conn.close()
    return {
        "total": total, "avg_placement": f"{avg_p:.1f}",
        "win_rate": to_percent(win), "top4_rate": to_percent(top4),
        "net_lp": net_lp, "highest_rank": highest_rank,
        "distribution": dist, "history": history,
        "daily_stats": daily_stats, "highest_season": highest
    }

@eel.expose
def get_live_state():
    """获取对局内实时状态"""
    with _live_lock:
        platform = _live_state.get("platform", "")
        return {
            "in_game": _live_state["in_game"],
            "phase": _live_state["phase"],
            "platform": platform,
            "is_pbe": is_pbe_server(platform),
            "sgp_supported": is_tencent_server(platform),
            "live_api_available": _live_state.get("live_api_available", False),
            "players": _live_state["players"],
            "my_units": _live_state["my_board"].get("units", []),
            "pool_taken": _live_state["pool_taken"],
            "opponent_info": _live_state["opponent_info"],
            "opponent_units": _live_state.get("opponent_units", {}),
            "three_star_alerts": _live_state.get("three_star_alerts", []),
            "auto_scan": _auto_scan_config["enabled"],
            "last_scan": _auto_scan_config["last_scan"],
            "last_update": _live_state["last_update"],
        }

@eel.expose
def test_live_api():
    """测试 Live Client Data API (port 2999) 是否可用"""
    available = is_live_api_available()
    result = {"available": available}
    if available:
        result["game_stats"] = get_live_game_stats()
        result["player_count"] = len(get_live_player_list() or [])
    return result

@eel.expose
def show_game_overlay():
    """显示独立游戏悬浮窗"""
    overlay.show_overlay()
    return {"status": "success", "visible": True}

@eel.expose
def hide_game_overlay():
    """隐藏独立游戏悬浮窗"""
    overlay.hide_overlay()
    return {"status": "success", "visible": False}

@eel.expose
def toggle_game_overlay():
    """切换独立游戏悬浮窗显示"""
    overlay.toggle_overlay()
    return {"status": "success", "visible": overlay.is_overlay_visible()}

@eel.expose
def get_overlay_status():
    """获取悬浮窗状态"""
    return {"visible": overlay.is_overlay_visible()}

# ===== 海克斯评级悬浮窗 =====
@eel.expose
def show_augment_overlay(stage=None):
    """显示海克斯评级悬浮窗, stage: 2/3/4"""
    try:
        augment_overlay.show_augment_overlay(stage)
        return {"status": "success", "visible": True}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@eel.expose
def hide_augment_overlay():
    """隐藏海克斯评级悬浮窗"""
    try:
        augment_overlay.hide_augment_overlay()
        return {"status": "success", "visible": False}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@eel.expose
def toggle_augment_overlay(stage=None):
    """切换海克斯评级悬浮窗"""
    try:
        augment_overlay.toggle_augment_overlay(stage)
        return {"status": "success", "visible": augment_overlay.is_augment_overlay_visible()}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@eel.expose
def get_augment_overlay_status():
    return {"visible": augment_overlay.is_augment_overlay_visible()}

@eel.expose
def refresh_live_state(platform=None):
    """手动刷新对局状态"""
    return _update_live_state(platform)

def _update_live_state(platform=None):
    """更新对局内实时状态"""
    port, token = get_lcu_credentials()
    if not port or not token:
        with _live_lock:
            _live_state["in_game"] = False
            _live_state["phase"] = "客户端未运行"
        return {"status": "error", "msg": "未检测到客户端"}

    phase = get_gameflow_phase(port, token)
    in_game = phase in ("InProgress", "GameStart", "WaitingForStats", "EndOfGame")

    # 检测是否新对局开始（从非对局状态进入对局状态）
    was_in_game = _live_state.get("in_game", False)
    if in_game and not was_in_game:
        with _live_lock:
            _live_state["opponent_units"] = {}
            _live_state["opponent_info"] = {}
            _live_state["current_game_id"] = f"game_{int(time.time())}"

    with _live_lock:
        _live_state["phase"] = phase or "未知"
        _live_state["in_game"] = in_game
        # 检测 Live Client Data API (port 2999)
        _live_state["live_api_available"] = is_live_api_available()

    if not in_game:
        return {"status": "idle", "phase": phase}

    # 获取玩家列表
    players = get_current_game_players(port, token)
    # 获取当前大区
    platform = get_current_platform(port, token)
    with _live_lock:
        _live_state["players"] = players
        _live_state["platform"] = platform

    # 获取自己的棋盘
    board = get_tft_board(port, token)
    my_units = parse_board_units(board)
    with _live_lock:
        _live_state["my_board"] = {"units": my_units}
        # 确保opponent_units存在
        if "opponent_units" not in _live_state:
            _live_state["opponent_units"] = {}

    # 计算牌池（自己的 + 已识别的对手牌）
    with _live_lock:
        opp_dict = dict(_live_state.get("opponent_units", {}))
    taken = calc_pool_taken(my_units, opponent_units_dict=opp_dict)
    with _live_lock:
        _live_state["pool_taken"] = taken

    # 三星预警
    alerts = check_three_star_alerts(my_units, taken)
    with _live_lock:
        _live_state["three_star_alerts"] = alerts
        _live_state["last_update"] = time.time()

    # 异步查询对手情报（仅腾讯国服支持SGP，美测服等跳过）
    if platform and is_tencent_server(platform) and players:
        sgp_token = get_sgp_token(port, token)
        if sgp_token:
            threading.Thread(
                target=_async_fetch_opponents,
                args=(players, platform, sgp_token),
                daemon=True
            ).start()

    return {"status": "success", "phase": phase, "players": len(players), "alerts": len(alerts)}

def _async_fetch_opponents(players, platform, sgp_token):
    """异步查询对手情报"""
    try:
        info = batch_fetch_opponents_info(players, platform, sgp_token)
        with _live_lock:
            _live_state["opponent_info"] = info
    except Exception:
        pass

_endpoints_probed = False

def _live_worker():
    """对局内实时监听后台线程"""
    global _endpoints_probed
    while True:
        try:
            port, token = get_lcu_credentials()
            if port and token:
                _update_live_state()
                # 第一次进对局时探测所有TFT端点
                with _live_lock:
                    in_game = _live_state.get("in_game", False)
                if in_game and not _endpoints_probed:
                    _endpoints_probed = True
                    try:
                        probe_tft_endpoints(port, token)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(3)

# 自动扫描配置
_auto_scan_config = {"enabled": True, "interval": 5, "last_scan": 0}

def _auto_scan_worker():
    """自动截图识别棋子的后台线程（自己+对手）"""
    while True:
        try:
            if not _auto_scan_config["enabled"]:
                time.sleep(2)
                continue
            with _live_lock:
                in_game = _live_state.get("in_game", False)
            if not in_game:
                time.sleep(3)
                continue
            now = time.time()
            if now - _auto_scan_config["last_scan"] < _auto_scan_config["interval"]:
                time.sleep(1)
                continue
            # 执行扫描
            result = scan_opponent_board()
            if result.get("status") == "success" and result.get("total", 0) > 0:
                found = result.get("found", {})
                # 更新自己的棋子（截图识别作为LCU的补充）
                with _live_lock:
                    my_units = []
                    for cid, cnt in found.items():
                        for _ in range(cnt):
                            my_units.append({"id": cid, "star": 1})
                    _live_state["my_board"]["units"] = my_units
                    # 重新计算牌池和三星预警
                    opp_dict = dict(_live_state.get("opponent_units", {}))
                    _live_state["pool_taken"] = calc_pool_taken(my_units, opponent_units_dict=opp_dict)
                    _live_state["three_star_alerts"] = check_three_star_alerts(my_units, _live_state["pool_taken"])
                _auto_scan_config["last_scan"] = now
        except Exception:
            pass
        time.sleep(2)

@eel.expose
def set_auto_scan(enabled, interval=8):
    """开启/关闭自动扫描"""
    _auto_scan_config["enabled"] = bool(enabled)
    _auto_scan_config["interval"] = max(3, int(interval))
    return {"status": "success", "enabled": _auto_scan_config["enabled"], "interval": _auto_scan_config["interval"]}

@eel.expose
def get_auto_scan_status():
    """获取自动扫描状态"""
    return {"enabled": _auto_scan_config["enabled"], "interval": _auto_scan_config["interval"]}

# =========================
# 启动
# =========================
def main():
    init_db()
    eel.init(WEB_DIR)

    # 托盘线程
    t_tray = threading.Thread(target=run_tray, daemon=True)
    t_tray.start()

    # 自动同步后台线程
    t_auto = threading.Thread(target=_auto_sync_worker, daemon=True)
    t_auto.start()

    # 对局内实时监听线程
    t_live = threading.Thread(target=_live_worker, daemon=True)
    t_live.start()

    # 自动扫描后台线程
    t_scan = threading.Thread(target=_auto_scan_worker, daemon=True)
    t_scan.start()

    # 独立系统级悬浮窗（覆盖在游戏上）
    overlay.init_overlay(get_live_state)
    # 海克斯评级悬浮窗（预初始化）
    try:
        augment_overlay.init_augment_overlay()
    except Exception as e:
        print(f"Augment overlay init warning: {e}")

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
