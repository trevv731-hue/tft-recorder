# -*- coding: utf-8 -*-
"""
海克斯强化评级悬浮窗
- 透明全屏窗口, 在海克斯卡片上方显示 S/A/B/C/D 评级
"""
import tkinter as tk
import threading
import time
import os
import sys

from augment_ocr import AugmentDetector
from augments import TIER_COLORS, TIER_DESC


def _log(msg):
    try:
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, "augment_overlay.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except:
        pass


class AugmentOverlayWindow:
    def __init__(self):
        self.visible = False
        self._stage = None
        self._detector = AugmentDetector()
        self._badge_widgets = {}
        self._last_results = {}
        self._build_ui()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("TFT Augment Rating")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0)
        self.root.configure(bg="black")
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.attributes("-transparentcolor", "black")

        self.info_frame = tk.Frame(self.root, bg="#1c1c1e")
        self.info_frame.place(x=10, y=10)
        self.title_lbl = tk.Label(self.info_frame, text="海克斯评级", fg="#fff", bg="#1c1c1e",
                                   font=("Arial", 10, "bold"), padx=8, pady=4)
        self.title_lbl.pack(side="left")
        self.stage_lbl = tk.Label(self.info_frame, text="", fg="#ffd60a", bg="#1c1c1e",
                                   font=("Arial", 9), padx=4, pady=4)
        self.stage_lbl.pack(side="left")
        self.status_lbl = tk.Label(self.info_frame, text="待机", fg="#8e8e93", bg="#1c1c1e",
                                   font=("Arial", 9), padx=8, pady=4)
        self.status_lbl.pack(side="left")
        self.close_btn = tk.Label(self.info_frame, text="X", fg="#ff453a", bg="#1c1c1e",
                                  font=("Arial", 10, "bold"), cursor="hand2", padx=6)
        self.close_btn.pack(side="right")
        self.close_btn.bind("<Button-1>", lambda e: self.hide())

        for w in [self.info_frame, self.title_lbl, self.stage_lbl, self.status_lbl]:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)

        self._drag_data = {"x": 0, "y": 0}
        _log("AugmentOverlayWindow built")

    def _drag_start(self, e):
        self._drag_data["x"] = e.x_root
        self._drag_data["y"] = e.y_root

    def _drag(self, e):
        dx = e.x_root - self._drag_data["x"]
        dy = e.y_root - self._drag_data["y"]
        x = self.info_frame.winfo_x() + dx
        y = self.info_frame.winfo_y() + dy
        self.info_frame.place(x=x, y=y)
        self._drag_data["x"] = e.x_root
        self._drag_data["y"] = e.y_root

    def _poll(self):
        pass  # 已移除无用的轮询, 扫描结果通过回调更新

    def show(self, stage=None):
        self._stage = stage
        self.visible = True
        self.root.attributes("-alpha", 0.95)
        self.root.attributes("-topmost", True)
        self.root.lift()
        if stage:
            self.stage_lbl.config(text=f"{stage}-{'1' if stage==2 else '2'}")
        self.status_lbl.config(text="扫描中...", fg="#30d158")
        self._detector.start_continuous_scan(callback=self._on_scan_result, stage=stage)
        _log(f"show, stage={stage}")

    def hide(self):
        self.visible = False
        self.root.attributes("-alpha", 0)
        self._detector.stop_continuous_scan()
        self._clear_badges()
        self.status_lbl.config(text="待机", fg="#8e8e93")
        _log("hide")

    def toggle(self, stage=None):
        if self.visible:
            self.hide()
        else:
            self.show(stage)

    def _on_scan_result(self, results):
        if not self.visible:
            return
        self.root.after(0, lambda: self._update_badges(results))

    def _update_badges(self, results):
        """增量更新: 只在tier/name变化时修改标签, 复用控件避免频繁销毁重建"""
        badge_positions = self._detector.get_badge_positions_px()
        recognized = 0
        active_indices = set()

        for r in results:
            idx = r["index"]
            if idx >= len(badge_positions):
                continue
            active_indices.add(idx)
            bx, by = badge_positions[idx]
            tier = r["tier"]
            color = r["color"]
            name = r["name"]
            if tier != "?":
                recognized += 1

            # 检查是否需要更新 (tier或name变化才重绘)
            last = self._last_results.get(idx)
            if last and last.get("tier") == tier and last.get("name") == name and last.get("bx") == bx:
                continue  # 无变化, 跳过

            # 复用或创建标签控件
            if idx in self._badge_widgets:
                tier_lbl, name_lbl = self._badge_widgets[idx]
                tier_lbl.config(text=tier, bg=color)
                tier_lbl.place(x=bx - 30, y=by)
                name_lbl.config(text=name[:20])
                name_lbl.place(x=bx - 60, y=by + 55)
            else:
                tier_lbl = tk.Label(self.root, text=tier, fg="white", bg=color,
                                    font=("Arial", 28, "bold"), padx=16, pady=4)
                tier_lbl.place(x=bx - 30, y=by)
                name_lbl = tk.Label(self.root, text=name[:20], fg="#fff", bg="#1c1c1e",
                                     font=("Arial", 9), padx=6, pady=2)
                name_lbl.place(x=bx - 60, y=by + 55)
                self._badge_widgets[idx] = (tier_lbl, name_lbl)

            self._last_results[idx] = {"tier": tier, "name": name, "bx": bx}

        # 隐藏不再活跃的标签
        for idx in list(self._badge_widgets.keys()):
            if idx not in active_indices:
                tier_lbl, name_lbl = self._badge_widgets[idx]
                tier_lbl.place_forget()
                name_lbl.place_forget()

        self.status_lbl.config(text=f"识别 {recognized}/3", fg="#30d158" if recognized >= 2 else "#ff9f0a")

    def _clear_badges(self):
        for tier_lbl, name_lbl in self._badge_widgets.values():
            tier_lbl.destroy()
            name_lbl.destroy()
        self._badge_widgets.clear()
        self._last_results.clear()

    def run(self):
        self.root.mainloop()

    def destroy(self):
        self._detector.stop_continuous_scan()
        self.root.destroy()


_overlay = None
_thread = None


def init_augment_overlay():
    global _overlay, _thread
    if _overlay:
        return _overlay
    _overlay = AugmentOverlayWindow()
    _thread = threading.Thread(target=_overlay.run, daemon=True, name="AugmentOverlayThread")
    _thread.start()
    time.sleep(0.3)
    return _overlay


def show_augment_overlay(stage=None):
    if not _overlay:
        init_augment_overlay()
    _overlay.show(stage)


def hide_augment_overlay():
    if _overlay:
        _overlay.hide()


def toggle_augment_overlay(stage=None):
    if not _overlay:
        init_augment_overlay()
    _overlay.toggle(stage)


def is_augment_overlay_visible():
    return _overlay.visible if _overlay else False


if __name__ == "__main__":
    ov = AugmentOverlayWindow()
    ov.show(stage=3)
    ov.run()
