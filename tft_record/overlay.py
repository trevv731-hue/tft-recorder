"""
TFT 独立悬浮窗 - 头像+数量卡片式
子线程中创建tkinter并运行mainloop，用队列通信避免COM线程问题
"""
import tkinter as tk
import os
import threading
import time
import urllib.request
import sys
import queue

# ========== 颜色主题 ==========
C = {
    "bg": "#1c1c1e", "bg2": "#2c2c2e", "card": "#3a3a3c",
    "text": "#ffffff", "text2": "#aeaeb2", "muted": "#636366",
    "green": "#30d158", "red": "#ff453a", "yellow": "#ffd60a",
    "blue": "#0a84ff", "purple": "#bf5af2", "orange": "#ff9f0a",
}

CHAMPS_BY_COST = {
    1: ["Akali","Camille","Cinderling","Karma","Kobuko","Leona","Ornn","Pebbles","Rakan","RekSai","Varus","Veigar","Xayah","Yorick"],
    2: ["Alistar","Caitlyn","Elise","Gromp","Kayle","LeBlanc","Murkwolf","Scuttlecrab","Sejuani","Shen","Teemo","Warwick","Yunara"],
    3: ["Azir","Cassiopeia","Diana","Fiddlesticks","Hecarim","KhaZix","KogMaw","Krug","MasterYi","Rammus","Raptor","Rengar","Tristana","Vi"],
    4: ["Ahri","Amumu","AncientSentinel","Aphelios","Brambleback","Ezreal","Lillia","Malphite","Morgana","Nidalee","Sett","Sivir","Soraka","Zyra"],
    5: ["Alune","Ashe","Draven","ElderDragon","Gnar","Ivern","Kennen","Lux","Maokai","Taric"],
}
PER_CHAMP = {1:29, 2:22, 3:18, 4:10, 5:9}
COST_COLOR = {1:"#9ca3af", 2:"#22c55e", 3:"#3b82f6", 4:"#a855f7", 5:"#f59e0b"}

def _log(msg):
    try:
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, "overlay_debug.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} [{threading.current_thread().name}] {msg}\n")
    except:
        pass

def get_icon_dir():
    if getattr(sys, 'frozen', False):
        d = os.path.join(sys._MEIPASS, "icons")
    else:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    os.makedirs(d, exist_ok=True)
    return d

def download_champ_icons():
    icon_dir = get_icon_dir()
    all_champs = []
    for cl in CHAMPS_BY_COST.values():
        all_champs.extend(cl)
    for champ in all_champs:
        path = os.path.join(icon_dir, f"{champ}.png")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            continue
        try:
            url = f"https://ddragon.leagueoflegends.com/cdn/14.20.1/img/champion/{champ}.png"
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) > 1000:
                    with open(path, "wb") as f:
                        f.write(data)
        except:
            pass
        time.sleep(0.1)

class _OverlayWindow:
    """在子线程中运行的tkinter窗口"""
    def __init__(self, cmd_queue):
        self.cmd_queue = cmd_queue
        self.visible = False
        self._collapsed = False
        self._drag_data = {"x":0, "y":0}
        self._state = {}
        self._photo_cache = {}
        self._build_ui()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("TFT")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0)  # 初始透明
        self.root.configure(bg=C["bg"])
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"340x560+{sw-360}+40")

        self.hdr = tk.Frame(self.root, bg=C["bg2"], height=32)
        self.hdr.pack(fill="x", side="top")
        self.hdr.pack_propagate(False)

        self.dot = tk.Label(self.hdr, text="●", fg=C["muted"], bg=C["bg2"], font=("Arial",10))
        self.dot.pack(side="left", padx=(8,2), pady=6)
        self.title = tk.Label(self.hdr, text="TFT", fg=C["text"], bg=C["bg2"], font=("Arial",11,"bold"))
        self.title.pack(side="left", pady=6)
        self.phase_lbl = tk.Label(self.hdr, text="", fg=C["text2"], bg=C["bg2"], font=("Arial",9))
        self.phase_lbl.pack(side="left", padx=6, pady=6)

        self.col_btn = tk.Label(self.hdr, text="—", fg=C["text2"], bg=C["bg2"], font=("Arial",12,"bold"), cursor="hand2")
        self.col_btn.pack(side="right", padx=(0,6), pady=4)
        self.col_btn.bind("<Button-1>", lambda e: self._toggle_collapse())
        self.close_btn = tk.Label(self.hdr, text="✕", fg=C["text2"], bg=C["bg2"], font=("Arial",10), cursor="hand2")
        self.close_btn.pack(side="right", padx=(0,4), pady=4)
        self.close_btn.bind("<Button-1>", lambda e: self._do_hide())

        self.canvas = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0)
        self.scroll_frame = tk.Frame(self.canvas, bg=C["bg"])
        self.vsb = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw", tags="frame")
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        for w in [self.hdr, self.dot, self.title, self.phase_lbl]:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<Double-Button-1>", lambda e: self._toggle_collapse())
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.root.after(100, self._poll_queue)
        _log("OverlayWindow built")

    def _poll_queue(self):
        try:
            while not self.cmd_queue.empty():
                cmd = self.cmd_queue.get_nowait()
                if cmd["action"] == "show":
                    self._do_show()
                elif cmd["action"] == "hide":
                    self._do_hide()
                elif cmd["action"] == "toggle":
                    if self.visible:
                        self._do_hide()
                    else:
                        self._do_show()
                elif cmd["action"] == "state":
                    self._state = cmd["data"]
                    self._update_ui()
        except Exception as e:
            _log(f"poll_queue error: {e}")
        self.root.after(200, self._poll_queue)

    def _do_show(self):
        self.visible = True
        try:
            self.root.attributes("-alpha", 0.92)
            self.root.attributes("-topmost", True)
            self.root.lift()
            _log("shown")
        except Exception as e:
            _log(f"show error: {e}")

    def _do_hide(self):
        self.visible = False
        try:
            self.root.attributes("-alpha", 0)
            _log("hidden")
        except Exception as e:
            _log(f"hide error: {e}")

    def _update_ui(self):
        try:
            state = self._state
            in_game = state.get("in_game", False)
            phase = state.get("phase", "")
            self.dot.config(fg=C["green"] if in_game else C["muted"])
            pt = phase or "等待"
            if state.get("is_pbe"):
                pt = f"🧪{pt}"
            self.phase_lbl.config(text=pt)
            if in_game and not self._collapsed:
                self._build_pool_grid()
        except Exception as e:
            _log(f"update_ui error: {e}")

    def _build_pool_grid(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        pool_taken = self._state.get("pool_taken", {})
        my_units = self._state.get("my_units", [])
        my_count = {}
        for u in my_units:
            cid = u.get("id","")
            star = u.get("star",1)
            cnt = 9 if star==3 else 3 if star==2 else 1
            my_count[cid] = my_count.get(cid,0)+cnt
        y = 0
        for cost in range(1,6):
            tk.Label(self.scroll_frame, text=f"  {cost}费", fg=COST_COLOR[cost], bg=C["bg"],
                    font=("Arial",9,"bold"), anchor="w").grid(row=y,column=0,columnspan=7,sticky="w",pady=(6,2),padx=4)
            y += 1
            champs = CHAMPS_BY_COST.get(cost,[])
            for i, champ in enumerate(champs):
                col = i % 7
                if col==0 and i>0: y += 1
                row = y
                total = PER_CHAMP[cost]
                taken = pool_taken.get(champ,0)
                remaining = max(0, total-taken)
                owned = my_count.get(champ,0)
                card = tk.Frame(self.scroll_frame, bg=C["card"], padx=2, pady=2)
                card.grid(row=row, column=col, padx=2, pady=2)
                photo = self._load_photo(champ, 32)
                if photo:
                    lbl = tk.Label(card, image=photo, bg=C["card"])
                    lbl.image = photo
                    lbl.pack()
                else:
                    tk.Label(card, text=champ[:2], bg=C["card"], fg=C["text"], font=("Arial",7), width=4, height=2).pack()
                color = C["green"] if remaining>total*0.5 else C["yellow"] if remaining>total*0.2 else C["red"]
                num = f"{remaining}"
                if owned>0: num += f" (+{owned})"
                tk.Label(card, text=num, bg=C["card"], fg=color, font=("Arial",8,"bold")).pack()
            y += 1
        alerts = self._state.get("three_star_alerts",[])
        if alerts:
            tk.Label(self.scroll_frame, text="  ⚠ 三星预警", fg=C["yellow"], bg=C["bg"], font=("Arial",9,"bold")).grid(row=y,column=0,columnspan=7,sticky="w",pady=(8,2),padx=4)
            y += 1
            for a in alerts[:5]:
                name = a.get("name",a.get("champ_id","?"))
                text = f"  {name}: 有{a.get('owned',0)} 差{a.get('needed',0)} 剩{a.get('remaining',0)}"
                tk.Label(self.scroll_frame, text=text, fg=C["text2"], bg=C["bg"], font=("Arial",8)).grid(row=y,column=0,columnspan=7,sticky="w",padx=4)
                y += 1

    def _load_photo(self, champ, size=36):
        key = f"{champ}_{size}"
        if key in self._photo_cache:
            return self._photo_cache[key]
        path = os.path.join(get_icon_dir(), f"{champ}.png")
        try:
            from PIL import Image, ImageTk
            if os.path.exists(path):
                img = Image.open(path).convert("RGBA").resize((size,size), Image.LANCZOS)
            else:
                for c, champs in CHAMPS_BY_COST.items():
                    if champ in champs:
                        img = Image.new("RGBA",(size,size),COST_COLOR.get(c,"#666"))
                        break
                else:
                    img = Image.new("RGBA",(size,size),"#666")
            photo = ImageTk.PhotoImage(img)
            self._photo_cache[key] = photo
            return photo
        except:
            return None

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _drag_start(self, e):
        self._drag_data["x"] = e.x_root
        self._drag_data["y"] = e.y_root

    def _drag(self, e):
        dx = e.x_root - self._drag_data["x"]
        dy = e.y_root - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self._drag_data["x"] = e.x_root
        self._drag_data["y"] = e.y_root

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.canvas.pack_forget()
            self.vsb.pack_forget()
            self.root.geometry("340x32")
            self.col_btn.config(text="□")
        else:
            self.vsb.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.root.geometry("340x560")
            self.col_btn.config(text="—")

    def run(self):
        _log("mainloop starting")
        self.root.mainloop()
        _log("mainloop ended")

# ========== 全局接口 ==========
_cmd_queue = queue.Queue()
_overlay_thread = None
_overlay_window = None
_state_getter = None

def _overlay_worker():
    global _overlay_window
    try:
        _overlay_window = _OverlayWindow(_cmd_queue)
        _overlay_window.run()
    except Exception as e:
        _log(f"worker fatal: {e}")

def init_overlay(state_getter=None):
    global _overlay_thread, _state_getter
    if _overlay_thread and _overlay_thread.is_alive():
        return
    _state_getter = state_getter
    _overlay_thread = threading.Thread(target=_overlay_worker, daemon=True, name="OverlayThread")
    _overlay_thread.start()
    _log("init_overlay: thread started")
    threading.Thread(target=download_champ_icons, daemon=True).start()
    # 启动状态推送线程
    threading.Thread(target=_state_pusher, daemon=True).start()

def _state_pusher():
    while True:
        try:
            if _state_getter and _overlay_window:
                state = _state_getter()
                if state:
                    _cmd_queue.put({"action":"state", "data":state})
        except Exception as e:
            _log(f"state_pusher error: {e}")
        time.sleep(2)

def show_overlay():
    _cmd_queue.put({"action":"show"})
    _log("show requested")

def hide_overlay():
    _cmd_queue.put({"action":"hide"})
    _log("hide requested")

def toggle_overlay():
    _cmd_queue.put({"action":"toggle"})

def is_overlay_visible():
    return _overlay_window.visible if _overlay_window else False

def update_overlay_state(state):
    _cmd_queue.put({"action":"state", "data":state})

if __name__ == "__main__":
    init_overlay()
    show_overlay()
    time.sleep(30)
