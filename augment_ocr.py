# -*- coding: utf-8 -*-
"""
海克斯强化 OCR 识别模块
- 截屏识别 3 个海克斯名称
- 支持手动校准位置
- 自动检测海克斯选择界面
"""
import time
import threading
import os
import sys

# Windows DPI 感知: 让截屏使用真实物理分辨率 (不受125%缩放影响)
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware v2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
    import os as _os
    _tess_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'D:\Program Files\Tesseract-OCR\tesseract.exe',
    ]
    for _tp in _tess_paths:
        if _os.path.exists(_tp):
            pytesseract.pytesseract.tesseract_cmd = _tp
            break
    # 项目本地 tessdata 目录 (含中文包)
    _local_tessdata = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tessdata')
    if _os.path.exists(_local_tessdata):
        _os.environ['TESSDATA_PREFIX'] = _local_tessdata
    # OCR 语言: 中文简体 + 英文
    OCR_LANG = 'chi_sim+eng'
except ImportError:
    HAS_TESSERACT = False
    OCR_LANG = 'eng'

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

from augments import get_augment_tier


def _log(msg):
    try:
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, "augment_debug.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except:
        pass


# 默认海克斯卡片名称区域 (百分比坐标, 基于1920x1080实际截图校准)
# 每个卡片: (x_center_pct, y_name_pct, name_w_pct, name_h_pct)
DEFAULT_AUGMENT_REGIONS = [
    (25.5, 45.4, 11.0, 3.5),   # 左 (金鳞精萃)
    (50.0, 45.4, 11.0, 3.5),   # 中 (珍藏财宝 III)
    (74.5, 45.4, 11.0, 3.5),   # 右 (绝境反击)
]

# 海克斯卡片上方位置 (用于显示评级标签)
DEFAULT_BADGE_POSITIONS = [
    (25.5, 28.0),
    (50.0, 28.0),
    (74.5, 28.0),
]


class AugmentDetector:
    def __init__(self, regions=None, badge_positions=None):
        self.regions = regions or DEFAULT_AUGMENT_REGIONS
        self.badge_positions = badge_positions or DEFAULT_BADGE_POSITIONS
        self._screen_size = self._get_screen_size()
        self._running = False
        self._thread = None
        self._callback = None
        self.last_result = []
        self.scan_interval = 1.5  # 秒
        self._img_cache = {}  # {card_index: (img_hash, result)} 截图缓存, 画面不变时跳过OCR
        self._cache_lock = threading.Lock()

    def _get_screen_size(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except:
            return 1920, 1080

    def _pct_to_px(self, x_pct, y_pct, w_pct=0, h_pct=0):
        sw, sh = self._screen_size
        x = int(sw * x_pct / 100)
        y = int(sh * y_pct / 100)
        w = int(sw * w_pct / 100)
        h = int(sh * h_pct / 100)
        return x, y, w, h

    def capture_region(self, x_pct, y_pct, w_pct, h_pct):
        """截取屏幕指定百分比区域"""
        if not HAS_PIL:
            return None
        x, y, w, h = self._pct_to_px(x_pct - w_pct/2, y_pct - h_pct/2, w_pct, h_pct)
        try:
            if HAS_MSS:
                with mss.mss() as sct:
                    monitor = {"top": y, "left": x, "width": w, "height": h}
                    img = sct.grab(monitor)
                    return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            else:
                return ImageGrab.grab(bbox=(x, y, x+w, y+h))
        except Exception as e:
            _log(f"capture error: {e}")
            return None

    def ocr_image(self, img):
        """OCR识别图片中的文字 (中文+英文) — 优化预处理"""
        if not HAS_TESSERACT or img is None:
            return ""
        try:
            # 预处理: 2x放大、灰度、二值化
            w, h = img.size
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
            img = img.convert('L')
            # 二值化 (阈值140, 游戏UI文字通常较亮)
            img = img.point(lambda p: 255 if p > 140 else 0)
            # psm 7 = 单行文本, TESSDATA_PREFIX 由环境变量自动读取
            text = pytesseract.image_to_string(img, lang=OCR_LANG, config='--psm 7 --oem 3')
            return text.strip()
        except Exception as e:
            _log(f"ocr error: {e}")
            return ""

    def _ocr_worker(self, i, x_pct, y_pct, w_pct, h_pct, stage):
        """单卡OCR工作线程"""
        img = self.capture_region(x_pct, y_pct, w_pct, h_pct)
        # 缓存: 如果截图和上次一样, 直接用缓存结果
        img_hash = None
        if img:
            import hashlib
            img_hash = hashlib.md5(img.tobytes()).hexdigest()
            if i in self._img_cache and self._img_cache[i][0] == img_hash:
                return self._img_cache[i][1]
        name = self.ocr_image(img)
        tier_info = get_augment_tier(name, stage)
        if tier_info:
            tier, color, desc, en_name = tier_info
            result = {"index": i, "name": name, "tier": tier, "color": color, "desc": desc, "en_name": en_name}
        else:
            result = {"index": i, "name": name or "?", "tier": "?", "color": "#888", "desc": "未识别", "en_name": ""}
        if img_hash:
            self._img_cache[i] = (img_hash, result)
        return result

    def scan_augments(self, stage=None):
        """扫描一次海克斯 — 并行OCR 3张卡"""
        from concurrent.futures import ThreadPoolExecutor
        results = [None] * len(self.regions)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i, (x_pct, y_pct, w_pct, h_pct) in enumerate(self.regions):
                futures.append(executor.submit(self._ocr_worker, i, x_pct, y_pct, w_pct, h_pct, stage))
            for i, f in enumerate(futures):
                results[i] = f.result()
        self.last_result = results
        return results

    def start_continuous_scan(self, callback=None, stage=None):
        """开始持续扫描"""
        if self._running:
            return
        self._running = True
        self._callback = callback
        self._thread = threading.Thread(target=self._scan_loop, args=(stage,), daemon=True)
        self._thread.start()
        _log("continuous scan started")

    def stop_continuous_scan(self):
        """停止持续扫描"""
        self._running = False
        _log("continuous scan stopped")

    def _scan_loop(self, stage):
        while self._running:
            try:
                results = self.scan_augments(stage)
                if self._callback:
                    self._callback(results)
            except Exception as e:
                _log(f"scan loop error: {e}")
            time.sleep(self.scan_interval)

    @property
    def is_running(self):
        return self._running

    def get_badge_positions_px(self):
        """获取评级标签的像素位置"""
        positions = []
        for x_pct, y_pct in self.badge_positions:
            x, y, _, _ = self._pct_to_px(x_pct, y_pct)
            positions.append((x, y))
        return positions

    def calibrate_from_screen(self):
        """(预留) 自动校准海克斯卡片位置"""
        # TODO: 通过颜色检测自动找到海克斯卡片
        pass
