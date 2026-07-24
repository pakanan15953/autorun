import os
# Limit CPU threads for PyTorch, NumPy, OpenMP, etc.
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

import cv2
import numpy as np
import time
import random
import ctypes
import win32gui
import win32con
import win32ui
import onnxruntime as ort

# Monkeypatch ONNX Runtime to limit threads to 2 and force sequential execution
_original_InferenceSession = ort.InferenceSession
def _custom_InferenceSession(path_or_bytes, sess_options=None, *args, **kwargs):
    if sess_options is None:
        sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 2
    sess_options.inter_op_num_threads = 1
    sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return _original_InferenceSession(path_or_bytes, sess_options, *args, **kwargs)
ort.InferenceSession = _custom_InferenceSession

from ultralytics import YOLO
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import traceback


from gameplay_controller import GameplayController
from window_manager import find_render_hwnd

class CookieRunAIApp(GameplayController):
    def __init__(self):
        super().__init__()
        self.create_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.update_loop)
    def create_layout(self):
        # === Color Palette (GitHub Dark Inspired) ===
        self.C_BG = "#0d1117"        # Window background
        self.C_CARD = "#161b22"      # Card/section background
        self.C_BORDER = "#30363d"    # Borders and dividers
        self.C_TEXT = "#e6edf3"      # Primary text
        self.C_TEXT2 = "#8b949e"     # Secondary text
        self.C_ACCENT = "#58a6ff"    # Accent blue
        self.C_GREEN = "#3fb950"     # Success green
        self.C_RED = "#f85149"       # Error red
        self.C_YELLOW = "#d29922"    # Warning yellow
        self.C_PURPLE = "#bc8cff"    # Purple accent
        self.C_TROUGH = "#21262d"    # Slider trough

        self.configure(bg=self.C_BG)
        self.geometry("370x640")

        # Scrollable main container
        main = tk.Frame(self, bg=self.C_BG)
        main.pack(fill="both", expand=True, padx=12, pady=10)

        # ─── HEADER ───
        header = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="🍪", font=("Segoe UI Emoji", 20), bg=self.C_CARD).pack(side="left", padx=(12, 4), pady=8)
        title_frame = tk.Frame(header, bg=self.C_CARD)
        title_frame.pack(side="left", fill="x", expand=True, pady=8)
        tk.Label(title_frame, text="Cookie Run AI Bot", font=("Segoe UI", 14, "bold"), fg=self.C_TEXT, bg=self.C_CARD).pack(anchor="w")

        status_text = "● Connected" if self.hwnd else "● Disconnected"
        status_color = self.C_GREEN if self.hwnd else self.C_RED
        self.status_label = tk.Label(title_frame, text=status_text, font=("Segoe UI", 9), fg=status_color, bg=self.C_CARD)
        self.status_label.pack(anchor="w")

        # ─── PROFILE CARD ───
        profile_card = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        profile_card.pack(fill="x", pady=(0, 6))
        profile_inner = tk.Frame(profile_card, bg=self.C_CARD)
        profile_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(profile_inner, text="▸ Farm Profile", font=("Segoe UI", 9, "bold"), fg=self.C_ACCENT, bg=self.C_CARD).pack(anchor="w", pady=(0, 4))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dark.TCombobox", fieldbackground=self.C_TROUGH, background=self.C_CARD, foreground=self.C_TEXT, arrowcolor=self.C_TEXT, borderwidth=0)

        self.profile_combo = ttk.Combobox(
            profile_inner,
            values=["Stage 1 (ฟาร์มเงิน/เหรียญ)", "Stage 3 (วิ่งทำระยะ)", "Stage 6 (Auto Run / ฟาร์มกล่อง AFK)", "Stage 7 (Pure AFK / วิ่งอัตโนมัติไม่กดปุ่ม)"],
            state="readonly", font=("Segoe UI", 9), style="Dark.TCombobox"
        )
        self.profile_combo.set("Stage 1 (ฟาร์มเงิน/เหรียญ)")
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)
        self.profile_combo.pack(fill="x")

        # ─── FEATURES CARD ───
        feat_card = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        feat_card.pack(fill="x", pady=(0, 6))
        feat_inner = tk.Frame(feat_card, bg=self.C_CARD)
        feat_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(feat_inner, text="▸ Features", font=("Segoe UI", 9, "bold"), fg=self.C_ACCENT, bg=self.C_CARD).pack(anchor="w", pady=(0, 4))

        # Tkinter variables for Checkbuttons
        self.autostart_var = tk.IntVar(value=1 if self.autostart_enabled else 0)
        self.rest_var = tk.IntVar(value=1 if self.rest_breaks_enabled else 0)
        self.eco_var = tk.IntVar(value=1 if self.eco_mode_enabled else 0)
        self.boost_start_var = tk.IntVar(value=0)
        self.buy_random_boost_var = tk.IntVar(value=1 if self.buy_random_boost else 0)
        self.use_relay_var = tk.IntVar(value=1 if self.use_relay else 0)

        toggle_opts = dict(
            font=("Segoe UI", 9), bg=self.C_CARD, fg=self.C_TEXT,
            selectcolor=self.C_TROUGH, activebackground=self.C_CARD,
            activeforeground=self.C_TEXT, bd=0, highlightthickness=0, anchor="w"
        )

        toggles = [
            ("Auto Start Game", self.autostart_var, self.on_toggle_autostart),
            ("Auto-Rest Breaks", self.rest_var, self.on_toggle_rest),
            ("Eco Mode (20 FPS)", self.eco_var, self.on_toggle_eco),
            ("Boost Start (Stage 3)", self.boost_start_var, self.on_toggle_boost_start),
            ("Buy Random Boost", self.buy_random_boost_var, self.on_toggle_buy_random_boost),
            ("Use Relay Cookie (ผลัดสอง)", self.use_relay_var, self.on_toggle_relay),
        ]
        for text, var, cmd in toggles:
            tk.Checkbutton(feat_inner, text=text, variable=var, command=cmd, **toggle_opts).pack(fill="x", pady=1)

        # ─── SESSION CARD ───
        sess_card = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        sess_card.pack(fill="x", pady=(0, 6))
        sess_inner = tk.Frame(sess_card, bg=self.C_CARD)
        sess_inner.pack(fill="x", padx=12, pady=8)

        sess_header = tk.Frame(sess_inner, bg=self.C_CARD)
        sess_header.pack(fill="x", pady=(0, 5))
        tk.Label(sess_header, text="▸ Session", font=("Segoe UI", 9, "bold"), fg=self.C_ACCENT, bg=self.C_CARD).pack(side="left")
        self.session_runs_label = tk.Label(sess_header, text=f"{self.current_session_runs}/{self.target_session_runs} games", font=("Segoe UI", 9, "bold"), fg=self.C_PURPLE, bg=self.C_CARD)
        self.session_runs_label.pack(side="right")

        # Canvas Progress Bar
        self.progress_canvas = tk.Canvas(sess_inner, height=8, bg=self.C_TROUGH, highlightthickness=0, bd=0)
        self.progress_canvas.pack(fill="x", pady=(0, 2))
        self.progress_bar_id = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill=self.C_PURPLE, outline="")
        self._update_progress_bar()

        # ─── TUNING CARD ───
        tune_card = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        tune_card.pack(fill="x", pady=(0, 6))
        tune_inner = tk.Frame(tune_card, bg=self.C_CARD)
        tune_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(tune_inner, text="▸ Tuning", font=("Segoe UI", 9, "bold"), fg=self.C_ACCENT, bg=self.C_CARD).pack(anchor="w", pady=(0, 4))

        slider_opts = dict(
            orient=tk.HORIZONTAL, bg=self.C_CARD, fg=self.C_TEXT,
            troughcolor=self.C_TROUGH, activebackground=self.C_ACCENT,
            bd=0, highlightthickness=0, showvalue=False, sliderrelief="flat"
        )

        # Slider: Max Games/Session
        self.session_limit_title = tk.Label(tune_inner, text=f"Max Games/Session: {self.max_session_runs_limit}", font=("Segoe UI", 8), fg=self.C_TEXT2, bg=self.C_CARD)
        self.session_limit_title.pack(anchor="w")
        self.session_limit_slider = tk.Scale(tune_inner, from_=5, to=30, command=self.on_session_limit_change, **slider_opts)
        self.session_limit_slider.set(self.max_session_runs_limit)
        self.session_limit_slider.pack(fill="x", pady=(0, 4))

        # Slider: Trigger Distance
        self.dist_title = tk.Label(tune_inner, text=f"Trigger Distance: {self.trigger_dist} px", font=("Segoe UI", 8), fg=self.C_TEXT2, bg=self.C_CARD)
        self.dist_title.pack(anchor="w")
        self.dist_slider = tk.Scale(tune_inner, from_=50, to=300, command=self.on_dist_change, **slider_opts)
        self.dist_slider.set(self.trigger_dist)
        self.dist_slider.pack(fill="x", pady=(0, 4))

        # Slider: Slide Hold
        self.slide_title = tk.Label(tune_inner, text=f"Slide Hold: {self.slide_hold_ms} ms", font=("Segoe UI", 8), fg=self.C_TEXT2, bg=self.C_CARD)
        self.slide_title.pack(anchor="w")
        self.slide_slider = tk.Scale(tune_inner, from_=100, to=1500, command=self.on_slide_change, **slider_opts)
        self.slide_slider.set(self.slide_hold_ms)
        self.slide_slider.pack(fill="x", pady=(0, 4))

        # Slider: YOLO Confidence
        self.conf_title = tk.Label(tune_inner, text=f"YOLO Threshold: {int(self.conf_val * 100)}%", font=("Segoe UI", 8), fg=self.C_TEXT2, bg=self.C_CARD)
        self.conf_title.pack(anchor="w")
        self.conf_slider = tk.Scale(tune_inner, from_=0.10, to=0.85, resolution=0.01, command=self.on_conf_change, **slider_opts)
        self.conf_slider.set(self.conf_val)
        self.conf_slider.pack(fill="x", pady=(0, 4))

        # Slider: AFK Run Time (Stage 6)
        m = self.afk_delay_sec // 60
        s = self.afk_delay_sec % 60
        self.afk_delay_title = tk.Label(tune_inner, text=f"AFK Run Time: {self.afk_delay_sec}s ({m}:{s:02d})", font=("Segoe UI", 8), fg=self.C_TEXT2, bg=self.C_CARD)
        self.afk_delay_title.pack(anchor="w")
        self.afk_delay_slider = tk.Scale(tune_inner, from_=10, to=300, command=self.on_afk_delay_change, **slider_opts)
        self.afk_delay_slider.set(self.afk_delay_sec)
        self.afk_delay_slider.pack(fill="x")

        # ─── LIVE STATS CARD ───
        stats_card = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        stats_card.pack(fill="x", pady=(0, 6))
        stats_inner = tk.Frame(stats_card, bg=self.C_CARD)
        stats_inner.pack(fill="x", padx=12, pady=6)

        tk.Label(stats_inner, text="▸ Live Stats", font=("Segoe UI", 9, "bold"), fg=self.C_ACCENT, bg=self.C_CARD).pack(anchor="w", pady=(0, 2))
        self.speed_label = tk.Label(stats_inner, text="Speed: --- px/s  |  TTC: ---s", font=("Consolas", 9), fg=self.C_TEXT2, bg=self.C_CARD)
        self.speed_label.pack(anchor="w")

        # ─── STATUS BAR ───
        status_bar = tk.Frame(main, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1)
        status_bar.pack(fill="x")
        self.bot_status_label = tk.Label(status_bar, text="STATUS: RUNNING", font=("Segoe UI", 12, "bold"), fg=self.C_GREEN, bg=self.C_CARD)
        self.bot_status_label.pack(pady=10)

    def _update_progress_bar(self):
        """อัปเดต Canvas progress bar ตามจำนวนรอบที่เล่น"""
        self.progress_canvas.update_idletasks()
        canvas_w = self.progress_canvas.winfo_width()
        if canvas_w <= 1:
            canvas_w = 300  # fallback ก่อน widget render
        if self.target_session_runs > 0:
            ratio = min(self.current_session_runs / self.target_session_runs, 1.0)
        else:
            ratio = 0
        fill_w = int(canvas_w * ratio)
        self.progress_canvas.coords(self.progress_bar_id, 0, 0, fill_w, 8)
        


    def on_profile_change(self, event=None):
        selected = self.profile_combo.get()
        print(f"⚙️ Profile Changed: {selected}")
        
        if "Stage 1" in selected:
            # Stage 1 Settings
            self.buy_random_boost_var.set(1)
            self.boost_start_var.set(0)
            self.use_relay_var.set(1)
            
            self.buy_random_boost = True
            self.use_boost_start = False
            self.use_relay = True
            self.no_action_mode = False
            self.afk_delay_sec = 0
            
            self.trigger_dist = 130
            self.dist_slider.set(130)
            self.dist_title.configure(text="Trigger Distance: 130 px")
            
            print("   - Auto-configured for Stage 1: Buy Buff=ON, Boost Start=OFF, Relay=ON, Trigger Dist=130px")
        elif "Stage 3" in selected:
            # Stage 3 Settings
            self.buy_random_boost_var.set(0)
            self.boost_start_var.set(1)
            self.use_relay_var.set(0)
            
            self.buy_random_boost = False
            self.use_boost_start = True
            self.use_relay = False
            self.no_action_mode = False
            self.afk_delay_sec = 0
            
            self.trigger_dist = 165
            self.dist_slider.set(165)
            self.dist_title.configure(text="Trigger Distance: 165 px")
            
            print("   - Auto-configured for Stage 3: Buy Buff=OFF, Boost Start=ON, Relay=OFF, Trigger Dist=165px")
        elif "Stage 6" in selected:
            # Stage 6 Settings (AFK Auto Run - No jump/slide for 2:05 mins, then normal play)
            self.buy_random_boost_var.set(0)
            self.boost_start_var.set(0)
            self.use_relay_var.set(0)
            
            self.buy_random_boost = False
            self.use_boost_start = False
            self.use_relay = False
            self.no_action_mode = True
            self.afk_delay_sec = 125
            
            if hasattr(self, "afk_delay_slider"):
                self.afk_delay_slider.set(125)
                m = 125 // 60
                s = 125 % 60
                self.afk_delay_title.configure(text=f"AFK Run Time: 125s ({m}:{s:02d})")
            
            print("   - Auto-configured for Stage 6: AFK Auto Run (125s AFK -> Normal Dodge, Auto Restart=ON)")
        elif "Stage 7" in selected:
            # Stage 7 Settings (Pure AFK - No actions at all, just restart loop)
            self.buy_random_boost_var.set(0)
            self.boost_start_var.set(0)
            self.use_relay_var.set(0)
            
            self.buy_random_boost = False
            self.use_boost_start = False
            self.use_relay = False
            self.no_action_mode = True
            self.afk_delay_sec = 999999
            
            if hasattr(self, "afk_delay_slider"):
                self.afk_delay_slider.set(300)
                self.afk_delay_title.configure(text="AFK Run Time: Infinite (Pure AFK)")
            
            print("   - Auto-configured for Stage 7: Pure AFK (No Jump/Slide, Auto Restart=ON)")
            
        self.update_session_label()

    # --- UI Callbacks ---
    def on_toggle_autostart(self):
        self.autostart_enabled = self.autostart_var.get() == 1
        print(f"⚙️ Auto Start Toggled: {self.autostart_enabled}")

    def update_session_label(self):
        if self.rest_breaks_enabled:
            if self.current_state == self.STATE_RESTING:
                self.session_runs_label.configure(text=f"{self.current_session_runs}/{self.target_session_runs} (Resting)")
            else:
                self.session_runs_label.configure(text=f"{self.current_session_runs}/{self.target_session_runs} games")
        else:
            self.session_runs_label.configure(text=f"{self.current_session_runs} games (No Rest)")
        self._update_progress_bar()

    def on_toggle_rest(self):
        self.rest_breaks_enabled = self.rest_var.get() == 1
        print(f"⚙️ Auto-Rest Breaks Toggled: {self.rest_breaks_enabled}")
        self.update_session_label()

    def on_toggle_eco(self):
        self.eco_mode_enabled = self.eco_var.get() == 1
        print(f"⚙️ Eco Mode Toggled: {self.eco_mode_enabled}")

    def on_toggle_boost_start(self):
        self.use_boost_start = self.boost_start_var.get() == 1
        print(f"⚙️ Boost Start Clicker Toggled: {self.use_boost_start}")

    def on_toggle_buy_random_boost(self):
        self.buy_random_boost = self.buy_random_boost_var.get() == 1
        print(f"⚙️ Buy Random Boost Toggled: {self.buy_random_boost}")

    def on_toggle_relay(self):
        self.use_relay = self.use_relay_var.get() == 1
        print(f"⚙️ Use Relay Toggled: {self.use_relay}")

    def on_session_limit_change(self, val):
        self.max_session_runs_limit = int(val)
        self.session_limit_title.configure(text=f"Max Games/Session: {self.max_session_runs_limit} runs")
        
        # ปรับจูนค่าเป้าหมายปัจจุบันให้เหมาะสมกับลิมิตใหม่ทันทีหากมันมากเกินไป
        if self.target_session_runs > self.max_session_runs_limit:
            self.target_session_runs = self.max_session_runs_limit
            self.update_session_label()

    def on_dist_change(self, val):
        self.trigger_dist = int(val)
        self.dist_title.configure(text=f"Trigger Distance: {self.trigger_dist} px")

    def on_slide_change(self, val):
        self.slide_hold_ms = int(val)
        self.slide_title.configure(text=f"Slide Hold: {self.slide_hold_ms} ms")

    def on_conf_change(self, val):
        self.conf_val = float(val)
        self.conf_title.configure(text=f"YOLO Threshold: {int(self.conf_val * 100)}%")

    def on_afk_delay_change(self, val):
        self.afk_delay_sec = int(val)
        m = self.afk_delay_sec // 60
        s = self.afk_delay_sec % 60
        self.afk_delay_title.configure(text=f"AFK Run Time: {self.afk_delay_sec}s ({m}:{s:02d})")

    def on_closing(self):
        self.destroy()
        print("=== ปิดการทำงานบอทเรียบร้อย ===")

if __name__ == "__main__":
    app = CookieRunAIApp()
    app.mainloop()
