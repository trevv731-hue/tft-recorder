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
else:
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

def detect_lcu():
    port, token = get_lcu_credentials()
    if not port or not token:
        return None
    return fetch_current_summoner(port, token)

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

def get_tft_ranked(port, token):
    """获取当前云顶排位段位"""
    try:
        resp = lcu_get(port, token, "/lol-ranked/v1/ranked-stats", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        queue_map = data.get("queueMap", {})
        for key, q in queue_map.items():
            qtype = (q.get("queueType", "") or "").upper()
            if "TFT" in qtype or "TFT" in key.upper():
                tier_en = q.get("tier", "") or ""
                return {
                    "tier": TIER_EN_TO_CN.get(tier_en.upper(), tier_en),
                    "division": q.get("division", "-") or "-",
                    "lp": q.get("leaguePoints", 0) or 0,
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
_sgp_token_cache = {"port": 0, "token": "", "time": 0}
_platform_cache = {"port": 0, "platform": None, "time": 0}

def _sgp_base_url(platform):
    """根据大区构建 SGP base URL"""
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
    return game

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

    new_count = 0
    skip_count = 0
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

        # 构建 participantId → puuid 映射（召唤师峡谷风格数据需要）
        pid_to_puuid = {}
        for ident in game.get("participantIdentities", []) or []:
            pid = ident.get("participantId")
            player = ident.get("player", {}) if isinstance(ident, dict) else {}
            p_puuid = player.get("puuid") or player.get("currentPuuid")
            if pid and p_puuid:
                pid_to_puuid[pid] = p_puuid

        # 找到自己的 participant
        my_p = None
        for p in game.get("participants", []) or []:
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
        if existing:
            c.execute("UPDATE matches SET comp=?, units=? WHERE id=?", (comp, units_json, existing["id"]))
            skip_count += 1
            continue

        c.execute("""
            INSERT INTO matches(user_id, placement, tier, division, lp, comp, time, season, game_id, units, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(user_id), placement, tier, division, int(lp),
            comp, game_time, game_season, int(game_id), units_json, safe_now_str()
        ))
        new_count += 1

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
    """获取单条对局详情"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE id=?", (int(match_id),))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"status": "error", "msg": "对局不存在"}
    return {"status": "success", "data": dict(row)}

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
        SELECT id, placement, tier, division, lp, comp, time, season, units
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
    conn.close()
    return {
        "total": total, "avg_placement": f"{avg_p:.1f}",
        "win_rate": to_percent(win), "top4_rate": to_percent(top4),
        "net_lp": net_lp,
        "distribution": dist, "history": history,
        "daily_stats": daily_stats, "highest_season": highest
    }

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
