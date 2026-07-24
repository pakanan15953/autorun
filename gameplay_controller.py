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


from window_manager import (
    find_render_hwnd, human_click_bg, human_press_bg, capture_window_bg,
    VK_ALT, SCAN_ALT, VK_LSHIFT, SCAN_SHIFT, VK_SPACE, SCAN_SPACE,
    SCAN_ALT, VK_SPACE, VK_LSHIFT
)
from template_matcher import find_template_match

class GameplayController(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Cookie Run AI Bot - Dashboard X")
        self.geometry("350x580")
        self.resizable(False, False)
        self.configure(bg="#121212")
        
        # Bot Core Variables
        self.hwnd = None
        self.model = None
        self.template_btn = None
        
        self.trigger_dist = 140
        self.slide_hold_ms = 850
        self.conf_val = 0.28
        self.autostart_enabled = True
        self.use_boost_start = False
        self.buy_random_boost = True
        self.use_relay = True
        self.no_action_mode = False
        self.afk_delay_sec = 125
        self.gameplay_start_time = 0
        self.has_logged_afk_transition = False
        self.loading_start_time = 0
        self.dismiss_clicks = 0

        self.eco_mode_enabled = False
        
        # Rest Break Configs
        self.rest_breaks_enabled = True
        self.current_session_runs = 0
        self.max_session_runs_limit = 12 # ขีดจำกัดรอบการเล่นสูงสุด (สไลเดอร์)
        self.target_session_runs = random.randint(9, 12)  # สุ่มรอบเป้าหมายในเซสชันแรก
        self.rest_end_time = 0
        
        # Game Flow variables
        self.STATE_PLAYING = "PLAYING"
        self.STATE_WAIT_OK = "WAIT_OK"
        self.STATE_WAIT_OPENALL = "WAIT_OPENALL"
        self.STATE_WAIT_CONFIRM_OPENALL = "WAIT_CONFIRM_OPENALL"
        self.STATE_WAIT_PLAYLOBBY = "WAIT_PLAYLOBBY"
        self.STATE_WAIT_SELECTBUFF_1 = "WAIT_SELECTBUFF_1"
        self.STATE_WAIT_SELECTBUFF_2 = "WAIT_SELECTBUFF_2"
        self.STATE_WAIT_SELECTBUFF_3 = "WAIT_SELECTBUFF_3"
        self.STATE_WAIT_START = "WAIT_START"
        self.STATE_WAIT_LOADING = "WAIT_LOADING"
        self.STATE_WAIT_BUFF_RESULT = "WAIT_BUFF_RESULT"
        self.STATE_RESTING = "RESTING"
        
        self.current_state = self.STATE_WAIT_PLAYLOBBY if self.autostart_enabled else self.STATE_PLAYING
        self.last_action_time = time.time()
        self.last_random_jump_check_time = 0
        self.last_switch_check_time = 0
        self.last_endgame_check_time = 0
        self.action_cooldown = 0.30
        self.scheduled_actions = []
        self.last_jump_time = 0
        self.last_slide_time = 0
        self.last_switch_time = 0
        
        # Switch variables
        self.cached_switch_status = False
        self.cached_switch_rect = None
        self.cached_switch_val = 0.0
        self.FALLBACK_COOKIE_X = 220
        
        # Anti-Detection Variables
        self.current_jitter = 0.0
        self.last_closest_dist = 0
        self.last_junk_input_time = time.time()
        
        # TTC / Speed tracking variables
        self.last_obstacle_x = None
        self.last_obstacle_time = None
        self.estimated_speed = 350.0  # Default fallback speed (pixels/second)
        
        # Autostart templates
        self.autostart_templates = {}
        
        # Load resources and search emulator window
        self.init_resources()
        
        # Construct UI elements
        
        # Bind closing protocol
        
        # Start cooperative loop

    def init_resources(self):
        print("=== บอท Cookie Run (โหมด Dashboard GUI) กำลังเตรียมทรัพยากร ===")
        
        # 1. Search for MuMu Player window
        hwnd = win32gui.FindWindow("Qt5156QWindowIcon", "Android Device-1-1")
        if not hwnd:
            hwnd = win32gui.FindWindow(None, "Android Device-1-1")
        
        if not hwnd:
            found_hwnd = [None]
            def enum_cb(h, extra):
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    c = win32gui.GetClassName(h)
                    if "android device" in t.lower() or "mumuplayer" in t.lower() or "mumu player" in t.lower():
                        if "tool" not in c.lower():
                            found_hwnd[0] = h
                            return False
                return True
            try:
                win32gui.EnumWindows(enum_cb, None)
            except:
                pass
            hwnd = found_hwnd[0]
            
        self.hwnd = hwnd
        if self.hwnd:
            print(f"✅ เชื่อมต่อหน้าต่าง Emulator สำเร็จ! (HWND: {self.hwnd})")
        else:
            print("❌ ไม่พบหน้าต่างโปรแกรมจำลอง MuMu Player! กรุณาเปิดโปรแกรมจำลองขึ้นมาก่อนรันบอท")

        # 2. Load YOLO model
        self.use_gpu = False
        try:
            import torch
            if torch.cuda.is_available():
                self.use_gpu = True
                print("❇️ PyTorch CUDA (GPU) detected and enabled!")
        except Exception:
            pass

        # If GPU is enabled, prioritize PyTorch (.pt) since PyTorch CUDA is already verified working
        # If CPU only, prioritize ONNX (.onnx) for faster CPU execution
        model_loaded = False
        if self.use_gpu:
            if os.path.exists("best.pt"):
                print("📥 กำลังโหลดโมเดล YOLOv8 'best.pt' (PyTorch CUDA)...")
                self.model = YOLO("best.pt")
                print("✅ โหลดโมเดล YOLOv8 (.pt) บน GPU สำเร็จ!")
                model_loaded = True
            elif os.path.exists("best.onnx"):
                print("📥 กำลังโหลดโมเดล YOLOv8 'best.onnx' (ONNX Runtime)...")
                self.model = YOLO("best.onnx")
                print("✅ โหลดโมเดล YOLOv8 (ONNX) สำเร็จ!")
                model_loaded = True
        else:
            if os.path.exists("best.onnx"):
                print("📥 กำลังโหลดโมเดล YOLOv8 'best.onnx' (ONNX CPU)...")
                self.model = YOLO("best.onnx")
                print("✅ โหลดโมเดล YOLOv8 (ONNX) บน CPU สำเร็จ!")
                model_loaded = True
            elif os.path.exists("best.pt"):
                print("📥 กำลังโหลดโมเดล YOLOv8 'best.pt'...")
                self.model = YOLO("best.pt")
                print("✅ โหลดโมเดล YOLOv8 สำเร็จ!")
                model_loaded = True

        if not model_loaded:
            print("❌ ไม่พบโมเดล 'best.onnx' หรือ 'best.pt' ในโฟลเดอร์บอท!")

        # 3. Load switch template
        script_dir = os.path.dirname(os.path.abspath(__file__))
        switch_template_path = os.path.join(script_dir, "autochangeplayer.png")
        if os.path.exists(switch_template_path):
            self.template_btn = cv2.imread(switch_template_path, cv2.IMREAD_GRAYSCALE)
            print("📥 โหลดปุ่มผลัดสองสำรองสำเร็จ!")

        # 4. Load autostart templates
        autostart_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autostart")
        autostart_files = {
            "ok": "ok_1.png",
            "openall": "openall_2.png",
            "confirmafteropenall": "confirmafteropenall_1.png",
            "playlobby": "playlobby_1.png",
            "selectbuff_1": "selectbuff_1.png",
            "selectbuff_2": "selectbuff_2.png",
            "selectbuff_3": "selectbuff_3.png",
            "affterselectbuff": "affterselectbuff_1.png",
            "confirmlevelup": "confirmlevelup1.png",
            "boost_start_btn": "boost_start_btn.png",
            "relic_title": "relic_title.png",
            "relic_claim": "relic_claim.png"
        }
        
        print("📥 เริ่มต้นโหลดปุ่มสำหรับ Autostart...")
        for name, filename in autostart_files.items():
            filepath = os.path.join(autostart_dir, filename)
            if os.path.exists(filepath):
                img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # ปรับขนาดเฉพาะปุ่มตระกูล Open All (เนื่องจากรูปต้นฉบับแคปเจอร์มาคนละสเกลที่ความกว้าง 940px)
                    if name in ["openall", "confirmafteropenall"]:
                        h, w = img.shape[:2]
                        scaled_w = int(w * 0.85)
                        scaled_h = int(h * 0.85)
                        img = cv2.resize(img, (scaled_w, scaled_h))
                        print(f"   - โหลดปุ่ม '{name}' สำเร็จ (ย่อสเกล 0.85 เหลือ: {img.shape})")
                    else:
                        print(f"   - โหลดปุ่ม '{name}' สำเร็จ (ขนาดดั้งเดิม: {img.shape})")
                    
                    self.autostart_templates[name] = img
        print("✅ โหลดปุ่ม Autostart ทั้งหมดสำเร็จ!")
    def schedule_action(self, delay, vk_code, action):
        """จองคิวการทำงานแบบ Non-blocking ไว้ล่วงหน้า"""
        self.scheduled_actions.append((time.time() + delay, vk_code, action))

    def process_scheduled_actions(self):
        """ประมวลผลคำสั่งที่อยู่ในคิวเมื่อถึงเวลา"""
        if not self.hwnd:
            return
        now = time.time()
        remaining_actions = []
        # เรียงลำดับคำสั่งตามเวลาที่จะทำก่อน-หลัง
        self.scheduled_actions.sort(key=lambda x: x[0])
        for exec_time, vk_code, action in self.scheduled_actions:
            if now >= exec_time:
                try:
                    action()
                except Exception as e:
                    print(f"Error running scheduled action: {e}")
            else:
                remaining_actions.append((exec_time, vk_code, action))
        self.scheduled_actions = remaining_actions

    def force_release_key(self, vk_code, scan_code):
        """บังคับปล่อยปุ่มทันทีเพื่อสลับท่าด่วน (เช่น ยกเลิกการสไลด์เพื่อกระโดด)"""
        if not self.hwnd:
            return
        # ส่งสัญญาณปล่อยปุ่มทันที
        lParam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
        win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, vk_code, lParam_up)
        # ลบคำสั่งปล่อยปุ่มเดียวกันที่เคยจองไว้ล่วงหน้าเพื่อไม่ให้รันซ้ำซ้อน
        self.scheduled_actions = [x for x in self.scheduled_actions if x[1] != vk_code]

    # --- Frame Rate Limiter Helper ---
    def schedule_next_loop(self, start_time):
        elapsed_ms = int((time.time() - start_time) * 1000)
        if self.eco_mode_enabled:
            # 20 FPS = 50ms per frame
            delay = max(1, 50 - elapsed_ms)
        else:
            # Max FPS (~60 FPS target delay) = 10ms
            delay = max(1, 10 - elapsed_ms)
        self.after(delay, self.update_loop)

    # --- Cooperative Loop Update ---
    def update_loop(self):
        try:
            self._update_loop_core()
        except Exception as e:
            print(f"❌ Exception in update_loop callback: {e}")
            traceback.print_exc()
            # Try to schedule next iteration despite error
            self.after(50, self.update_loop)

    def _update_loop_core(self):
        if not self.hwnd:
            self.status_label.configure(text="● Disconnected", fg=self.C_RED)
            self.bot_status_label.configure(text="STATUS: OFFLINE", fg=self.C_RED)
            self.init_resources()
            self.after(2000, self.update_loop)
            return

        self.status_label.configure(text="● Connected", fg=self.C_GREEN)
        start_time = time.time()
        now = time.time()

        # ประมวลผลปุ่มกดค้างที่ต้องปล่อยแบบ Non-blocking
        self.process_scheduled_actions()

        # Handle RESTING break state
        if self.current_state == self.STATE_RESTING:
            remaining = self.rest_end_time - now
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                
                # Update status displays
                self.bot_status_label.configure(text=f"RESTING ({mins:02d}:{secs:02d})", fg="#f39c12")
                self.update_session_label()

                # Run rest checks slowly (500ms intervals) to save 99% CPU/GPU resources
                self.after(500, self.update_loop)
                return
            else:
                # Break finished
                print(f"[{time.strftime('%H:%M:%S')}] ☀️ หมดเวลาพักผ่อนแล้ว! กำลังเริ่มเล่นเซสชันถัดไป...")
                self.current_session_runs = 0
                # สุ่มกำหนดเป้าหมายใหม่โดยอิงจากสไลเดอร์บวกการสุ่มลบรอบ
                lower_limit = max(5, self.max_session_runs_limit - 3)
                self.target_session_runs = random.randint(lower_limit, self.max_session_runs_limit)
                self.current_state = self.STATE_WAIT_OK
                self.update_session_label()

        # 1. Capture screen
        frame = capture_window_bg(self.hwnd)
        if frame is None:
            self.after(30, self.update_loop)
            return

        # 2. Check Autostart state machine (Self-correcting with dynamic retries)
        if self.autostart_enabled:
            # Self-healing: if in PLAYING or WAIT_LOADING state but we see the lobby, reset to WAIT_PLAYLOBBY (only after 6s of no action to prevent transition bugs)
            if (self.current_state == self.STATE_PLAYING or self.current_state == self.STATE_WAIT_LOADING) and (now - self.last_action_time > 6.0):
                found_lobby_btn, rx, ry = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None), threshold=0.70)
                if found_lobby_btn and (580 <= rx <= 715):
                    print(f"[{time.strftime('%H:%M:%S')}] 🔄 ตรวจพบปุ่มหน้าหลัก (Lobby) -> ทำการรีเซ็ตสเตทบอทเป็น WAIT_PLAYLOBBY")
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                    self.gameplay_start_time = 0
                    self.last_action_time = 0

        if self.autostart_enabled and self.current_state != self.STATE_PLAYING and self.current_state != self.STATE_WAIT_LOADING:
            self.bot_status_label.configure(text=f"STATUS: {self.current_state}", fg="#f39c12")
            

            # Global Level Up check
            if "confirmlevelup" in self.autostart_templates:
                found_lv, cx_lv, cy_lv = find_template_match(self.hwnd, frame, self.autostart_templates["confirmlevelup"])
                if found_lv:
                    print(f"[{time.strftime('%H:%M:%S')}] ⭐ ตรวจพบป๊อปอัป Level Up! ทำการคลิกปิดเพื่อไปต่อ...")
                    human_click_bg(self.hwnd, cx_lv, cy_lv, "Level Up Close Button")
                    # รอ 2-3.5 วินาทีแบบ non-blocking ให้ animation Level Up เล่นจบก่อนวนลูปถัดไป
                    self.after(int(random.uniform(2000, 3500)), self.update_loop)
                    return

            # Execute state actions
            if self.current_state == self.STATE_WAIT_OK:
                found_openall, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("openall", None), threshold=0.62)
                found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.62)
                found_lobby, rx, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None), threshold=0.70)
                
                if found_openall:
                    self.current_state = self.STATE_WAIT_OPENALL
                elif found_confirm:
                    self.current_state = self.STATE_WAIT_CONFIRM_OPENALL
                elif found_lobby and (580 <= rx <= 715):
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                else:
                    if "ok" in self.autostart_templates:
                        found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["ok"])
                        if found:
                            if now - self.last_action_time > 1.2:
                                human_click_bg(self.hwnd, cx, cy, "OK Button")
                                self.last_action_time = now
                        else:
                            # ถ้าปุ่ม OK หายไปแล้ว (แปลว่ากดติดแล้ว) แต่สแกนหาปุ่มหน้าถัดไปไม่เจอเลยเกิน 3 วินาที
                            # ให้ตั้งสมมติฐานว่าเข้าสู่หน้ากล่องรางวัลแล้ว และสลับสเตทไปรอเปิดกล่องทันที
                            if now - self.last_action_time > 3.0:
                                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ ไม่พบปุ่ม OK และปุ่มอื่นๆ เกิน 3 วินาที -> บังคับเปลี่ยนสเตทเป็น WAIT_OPENALL")
                                self.current_state = self.STATE_WAIT_OPENALL
                                self.last_action_time = now

            elif self.current_state == self.STATE_WAIT_OPENALL:
                found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.62)
                found_lobby, rx, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None), threshold=0.70)
                
                if found_confirm:
                    self.current_state = self.STATE_WAIT_CONFIRM_OPENALL
                elif found_lobby and (580 <= rx <= 715):
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                else:
                    if "openall" in self.autostart_templates:
                        found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["openall"], threshold=0.62)
                        if found:
                            if now - self.last_action_time > 1.2:
                                human_click_bg(self.hwnd, cx, cy, "Open All Button")
                                self.last_action_time = now
                        else:
                            # คลิกสุ่มสำรองหากค้างหน้าต่างกล่องรางวัลเกิน 4 วินาที
                            if now - self.last_action_time > 4.0:
                                human_click_bg(self.hwnd, 400, 410, "Open All Button (Fallback)")
                                self.last_action_time = now

            elif self.current_state == self.STATE_WAIT_CONFIRM_OPENALL:
                found_lobby, rx, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None), threshold=0.70)
                if found_lobby and (580 <= rx <= 715):
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                else:
                    if "confirmafteropenall" in self.autostart_templates:
                        found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["confirmafteropenall"], threshold=0.62)
                        if found:
                            if now - self.last_action_time > 1.2:
                                human_click_bg(self.hwnd, cx, cy, "Confirm After Open All Button")
                                self.last_action_time = now
                        else:
                            # คลิกสุ่มสำรองปิดหน้าต่างรางวัลหากค้างเกิน 4 วินาที
                            if now - self.last_action_time > 4.0:
                                human_click_bg(self.hwnd, 400, 400, "Confirm After Open All Button (Fallback)")
                                self.last_action_time = now

            elif self.current_state == self.STATE_WAIT_PLAYLOBBY:
                if "playlobby" in self.autostart_templates:
                    found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["playlobby"], threshold=0.70)
                    if found and (580 <= cx <= 715):
                        # รอ 20.0 วินาทีหลังจากเปลี่ยนสเตทมาที่ WAIT_PLAYLOBBY
                        # เพื่อให้เกมรีเฟรชและโหลดหน้าล็อบบี้ให้เสร็จสมบูรณ์ก่อนกด Play
                        if now - self.last_action_time > 15.0:
                            print(f"[{time.strftime('%H:%M:%S')}] 🖱️ คลิกปุ่ม Play ล็อบบี้ด้วยพิกัดแสกน ({cx}, {cy})")
                            human_click_bg(self.hwnd, cx, cy, "Play Lobby Button")
                            self.last_action_time = now
                            if self.buy_random_boost:
                                self.current_state = self.STATE_WAIT_SELECTBUFF_1
                            else:
                                self.current_state = self.STATE_WAIT_START
                                self.dismiss_clicks = 0

            elif self.current_state == self.STATE_WAIT_SELECTBUFF_1:
                if not self.buy_random_boost:
                    self.current_state = self.STATE_WAIT_START
                    self.dismiss_clicks = 0
                    self.schedule_next_loop(start_time)
                    return
                # 1. รอจนกว่าช่องสุ่มบัฟ (selectbuff_1) จะปรากฏ (สกรีนช็อตร้านค้าโหลดเสร็จ)
                if "selectbuff_1" in self.autostart_templates:
                    found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["selectbuff_1"])
                    if found:
                        if now - self.last_action_time > 1.2:
                            print(f"[{time.strftime('%H:%M:%S')}] 🖱️ คลิกเลือกสล็อต Random Boost (335, 375)")
                            human_click_bg(self.hwnd, 335, 375, "Select Random Boost Slot")
                            self.last_action_time = now
                            self.current_state = self.STATE_WAIT_SELECTBUFF_2
                    else:
                        # ป้องกันกรณีโหลดนาน: คลิกสุ่มสำรองถ้าค้างในสเตทนี้เกิน 5.5 วินาที
                        if now - self.last_action_time > 5.5:
                            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ ไม่พบปุ่ม Random Boost -> บังคับคลิกพิกัดสำรอง (335, 375)")
                            human_click_bg(self.hwnd, 335, 375, "Select Random Boost Slot (Fallback)")
                            self.last_action_time = now
                            self.current_state = self.STATE_WAIT_SELECTBUFF_2

            elif self.current_state == self.STATE_WAIT_SELECTBUFF_2:
                # 2. คลิกปุ่ม Multi เพื่อเปิดป๊อปอัปสุ่มบัฟ
                if now - self.last_action_time > 1.2:
                    print(f"[{time.strftime('%H:%M:%S')}] 🖱️ คลิกปุ่ม Multi (666, 123)")
                    human_click_bg(self.hwnd, 666, 123, "Multi Random Boost Button")
                    self.last_action_time = now
                    self.current_state = self.STATE_WAIT_SELECTBUFF_3

            elif self.current_state == self.STATE_WAIT_SELECTBUFF_3:
                # 3. คลิกปุ่ม Multi-Buy ด้านในป๊อปอัปเพื่อสั่งสุ่มบัฟจริง
                if now - self.last_action_time > 1.5:
                    print(f"[{time.strftime('%H:%M:%S')}] 🖱️ คลิกปุ่ม Multi-Buy ในป๊อปอัป (397, 367)")
                    human_click_bg(self.hwnd, 397, 367, "Multi-Buy Button")
                    self.last_action_time = now
                    self.current_state = self.STATE_WAIT_BUFF_RESULT
                    self.dismiss_clicks = 0

            elif self.current_state == self.STATE_WAIT_BUFF_RESULT:
                # 1. เช็คว่าสุ่มได้บัฟเหรียญ 2 เท่า (Double Coins) หรือยัง
                found_double_coin = False
                cx_dc, cy_dc = 610, 400
                if "affterselectbuff" in self.autostart_templates:
                    found_dc, tx, ty = find_template_match(self.hwnd, frame, self.autostart_templates["affterselectbuff"], threshold=0.70)
                    if found_dc:
                        found_double_coin = True
                        cx_dc = tx
                        cy_dc = ty + 25 # เล็งพิกัดกดปุ่ม Play ด้านล่างแถบป้าย
                
                if found_double_coin:
                    print(f"[{time.strftime('%H:%M:%S')}] 🎉 สุ่มได้บัฟเหรียญ 2 เท่า (Double Coins) สำเร็จ! กำลังเริ่มเล่นเกม...")
                    human_click_bg(self.hwnd, cx_dc, cy_dc, "Play Buff Button (Double Coins)")
                    
                    self.current_session_runs += 1
                    if self.rest_breaks_enabled:
                        print(f"[{time.strftime('%H:%M:%S')}] 🎮 เริ่มต้นเกมใหม่สำเร็จ! (นับรอบสะสม: {self.current_session_runs}/{self.target_session_runs})")
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] 🎮 เริ่มต้นเกมใหม่สำเร็จ! (รอบสะสม: {self.current_session_runs} - ไม่มีพักเบรก)")
                    self.update_session_label()
                    
                    self.current_state = self.STATE_WAIT_LOADING
                    self.loading_start_time = now
                    self.last_action_time = now
                    self.schedule_next_loop(start_time)
                    return
                
                # 2. เช็คว่ามีปุ่มตกลงสีเหลืองสำหรับสุ่มใหม่หรือไม่ (กรณีสุ่มได้บัฟอื่น)
                if "ok" in self.autostart_templates:
                    found_ok, cx_ok, cy_ok = find_template_match(self.hwnd, frame, self.autostart_templates["ok"], threshold=0.75)
                    if found_ok:
                        if now - self.last_action_time > 1.2:
                            print(f"[{time.strftime('%H:%M:%S')}] ❌ ไม่ใช่บัฟเหรียญ 2 เท่า -> คลิกตกลงเพื่อสุ่มใหม่...")
                            human_click_bg(self.hwnd, cx_ok, cy_ok, "Close Result Popup (Retry)")
                            self.last_action_time = now
                            self.current_state = self.STATE_WAIT_SELECTBUFF_2
                            self.schedule_next_loop(start_time)
                            return
                
                # ป้องกันกรณีสปินสุ่มนานเกินไปหรือค้างแบบอื่น (ขยายเวลาสูงสุดเป็น 45 วินาที)
                if now - self.last_action_time > 45.0:
                    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ สุ่มบัฟนานเกิน 45 วินาที -> บังคับเคลียร์ปิดร้านค้า")
                    human_click_bg(self.hwnd, 607, 60, "Close Shop Popup X Button")
                    self.last_action_time = now
                    self.current_state = self.STATE_WAIT_START
                    self.schedule_next_loop(start_time)
                    return

            elif self.current_state == self.STATE_WAIT_START:
                # เช็คว่าปุ่มเริ่มวิ่งสีเขียว (ใช้รูป playlobby เป็นตัวแทน) ปรากฏขึ้นบนจอหรือยัง
                found_start = False
                cx_s, cy_s = 670, 390
                if "playlobby" in self.autostart_templates:
                    found, tx, ty = find_template_match(self.hwnd, frame, self.autostart_templates["playlobby"], threshold=0.70)
                    if found:
                        found_start = True
                        cx_s = tx
                        cy_s = ty
                
                # หากเจอปุ่มเริ่มวิ่ง (แสดงว่าหน้าจอเตรียมตัวโหลดเสร็จแล้วและไม่มีป๊อปอัปบัง)
                if found_start:
                    if now - self.last_action_time > 1.2:
                        print(f"[{time.strftime('%H:%M:%S')}] 🎮 ตรวจพบปุ่มเริ่มวิ่งสีเขียว (พิกัด: {cx_s}, {cy_s}) -> คลิกเพื่อเริ่มเกม")
                        human_click_bg(self.hwnd, cx_s, cy_s, "Start Game Button")
                        
                        self.current_session_runs += 1
                        if self.rest_breaks_enabled:
                            print(f"[{time.strftime('%H:%M:%S')}] 🎮 เริ่มต้นเกมใหม่สำเร็จ! (นับรอบสะสม: {self.current_session_runs}/{self.target_session_runs})")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] 🎮 เริ่มต้นเกมใหม่สำเร็จ! (รอบสะสม: {self.current_session_runs} - ไม่มีพักเบรก)")
                        self.update_session_label()
                        
                        self.current_state = self.STATE_WAIT_LOADING
                        self.loading_start_time = now
                        self.last_action_time = now
                else:
                    # ป้องกันกรณีค้างทั่วไปในโหมดไม่สุ่มบัฟ
                    if now - self.last_action_time > 15.0:
                        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ ค้างที่หน้าเตรียมตัวนานเกิน 15 วินาที -> ส่งคลิกปิดหน้าต่างสำรอง (607, 60)")
                        human_click_bg(self.hwnd, 607, 60, "Close Shop Popup X Button")
                        self.last_action_time = now

            self.schedule_next_loop(start_time)
            return

        # --- NORMAL GAMEPLAY: YOLO Run Controls ---
        self.bot_status_label.configure(text="STATUS: RUNNING", fg=self.C_GREEN)
        self.update_session_label()
        
        # Check if game ended (Anti-ban check before OK click)
        if self.autostart_enabled:
            if now - self.last_endgame_check_time > 1.5:
                self.last_endgame_check_time = now
                
                # สเตทที่กำลังอยู่ระหว่างโหลดหน้าร้านค้า/สุ่มบัฟ ไม่ควรให้ Sync Check แทรกแซง
                # และไม่ควรเรียกใช้ Sync Check ระหว่างที่คุกกี้กำลังวิ่งในเกม (STATE_PLAYING) เพื่อป้องกันการแสกนจับเจอปุ่มบนฉากแล้วเอ๋อ
                if self.current_state != self.STATE_PLAYING:
                    _transitioning = self.current_state in (
                        self.STATE_WAIT_SELECTBUFF_1,
                        self.STATE_WAIT_SELECTBUFF_2,
                        self.STATE_WAIT_SELECTBUFF_3,
                        self.STATE_WAIT_START,
                        self.STATE_WAIT_LOADING,
                    )
                    
                    # เช็คปุ่มอื่นๆ เพื่อกู้คืนสเตทเผื่อบอทรันกลางคันหรือสเตทไม่ตรงกับหน้าจอ
                    found_openall, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("openall", None), threshold=0.62)
                    found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.62)
                    
                    # ใช้ปุ่ม playlobby ในการระบุหน้าจอล็อบบี้โดยอ้างอิงช่วงพิกัด X
                    found_lobby = False
                    found_start = False
                    found_play_btn, rx, ry = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None), threshold=0.70)
                    if found_play_btn and (580 <= rx <= 715):
                        found_lobby = True  # อยู่หน้าล็อบบี้ (Center X ~661)
                    
                    found_relic, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("relic_title", None), threshold=0.75)
                    if found_relic:
                        found_claim, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates.get("relic_claim", None), threshold=0.70)
                        if found_claim:
                            if now - self.last_action_time > 1.2:
                                print(f"[{time.strftime('%H:%M:%S')}] 🏆 พบป๊อปอัป Relic -> คลิกปุ่ม Claim เพื่อกดรับ ({cx}, {cy})")
                                human_click_bg(self.hwnd, cx, cy, "Claim Relic Button")
                                self.last_action_time = now
                        else:
                            if now - self.last_action_time > 3.0:
                                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ ไม่พบปุ่ม Claim บนป๊อปอัป Relic -> คลิกพิกัดสำรอง (500, 360)")
                                human_click_bg(self.hwnd, 500, 360, "Claim Relic Button (Fallback)")
                                self.last_action_time = now
                        self.schedule_next_loop(start_time)
                        return

                    found_buff1, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("selectbuff_1", None), threshold=0.75)
                    
                    if found_openall:
                        print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าจอกล่องรางวัล (Open All) -> สลับสเตทเป็น WAIT_OPENALL")
                        self.current_state = self.STATE_WAIT_OPENALL
                        self.schedule_next_loop(start_time)
                        return
                    elif found_confirm:
                        print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าจอกดรับรางวัล (Confirm) -> สลับสเตทเป็น WAIT_CONFIRM_OPENALL")
                        self.current_state = self.STATE_WAIT_CONFIRM_OPENALL
                        self.schedule_next_loop(start_time)
                        return
                    elif found_lobby and not _transitioning:
                        # ป้องกันการวนซ้ำกดปุ่ม Play ล็อบบี้ระหว่างที่หน้าจอกำลังเปลี่ยนผ่านอยู่
                        print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าล็อบบี้ (Play Lobby) -> สลับสเตทเป็น WAIT_PLAYLOBBY")
                        self.current_state = self.STATE_WAIT_PLAYLOBBY
                        self.last_action_time = 0
                        self.schedule_next_loop(start_time)
                        return
                    elif found_buff1 or found_start:
                        if not _transitioning:
                            if self.buy_random_boost:
                                print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าจอซื้อบัฟ/เตรียมเริ่มเกม -> สลับสเตทเป็น WAIT_SELECTBUFF_1")
                                self.current_state = self.STATE_WAIT_SELECTBUFF_1
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าเตรียมเริ่มเกม -> สลับสเตทเป็น WAIT_START")
                                self.current_state = self.STATE_WAIT_START
                                self.dismiss_clicks = 0
                        self.schedule_next_loop(start_time)
                        return

                if "ok" in self.autostart_templates:
                    found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["ok"])
                    if found:
                        # Check if session runs limit is hit to trigger rest break
                        if self.rest_breaks_enabled and self.current_session_runs >= self.target_session_runs:
                            self.current_state = self.STATE_RESTING
                            rest_duration = random.uniform(480, 1080)  # สุ่มพัก 8 ถึง 18 นาที
                            self.rest_end_time = time.time() + rest_duration
                            
                            print(f"[{time.strftime('%H:%M:%S')}] 💤 ครบเซสชันการเล่น ({self.current_session_runs}/{self.target_session_runs} รอบ) -> สลับเข้าโหมดพักเบรกจำลองมนุษย์เป็นเวลา {rest_duration/60:.1f} นาที")
                            self.update_session_label()
                            self.bot_status_label.configure(text="RESTING", fg="#f39c12")
                            
                            self.schedule_next_loop(start_time)
                            return
                        else:
                            # Proceed with normal restart flow
                            self.current_state = self.STATE_WAIT_OK
                            self.last_action_time = now
                            print(f"[{time.strftime('%H:%M:%S')}] 🏁 พบหน้าจอจบเกม (ปุ่ม OK)! สลับเข้าสู่โหมดกดเริ่มใหม่อัตโนมัติ...")
                            
                            self.bot_status_label.configure(text=f"STATUS: {self.current_state}", fg="#f39c12")
                            # รอ 1.5-3.0 วินาทีแบบ non-blocking จำลองมนุษย์ดูหน้าจอก่อนกดต่อ
                            self.after(int(random.uniform(1500, 3000)), self.update_loop)
                            return

        # Check AFK Run Time timer if in Stage 6 AFK mode
        if self.no_action_mode and self.current_state == self.STATE_PLAYING:
            if self.gameplay_start_time == 0:
                self.gameplay_start_time = now

            elapsed_gameplay = now - self.gameplay_start_time

            if elapsed_gameplay < self.afk_delay_sec:
                cur_m = int(elapsed_gameplay) // 60
                cur_s = int(elapsed_gameplay) % 60
                if self.afk_delay_sec > 10000:
                    status_text = f"STATUS: PURE AFK ({cur_m}:{cur_s:02d})"
                else:
                    max_m = self.afk_delay_sec // 60
                    max_s = self.afk_delay_sec % 60
                    status_text = f"STATUS: AFK RUNNING ({cur_m}:{cur_s:02d} / {max_m}:{max_s:02d})"
                
                self.bot_status_label.configure(
                    text=status_text,
                    fg=self.C_ACCENT
                )
                self.schedule_next_loop(start_time)
                return
            else:
                if not self.has_logged_afk_transition:
                    self.has_logged_afk_transition = True
                    print(f"[{time.strftime('%H:%M:%S')}] 📦 ครบเวลา AFK {self.afk_delay_sec} วินาที (เก็บกล่องเรียบร้อย) -> สลับเข้าสู่โหมดหลบสิ่งกีดขวางตามปกติ!")

        # YOLO inference
        if self.model is None:
            self.after(30, self.update_loop)
            return

        if hasattr(self, "use_gpu") and self.use_gpu:
            results = self.model(frame, conf=self.conf_val, verbose=False, device="cuda")
        else:
            results = self.model(frame, conf=self.conf_val, verbose=False)

        found_jump_obstacle = False
        found_double_jump_obstacle = False
        found_slide_obstacle = False
        found_switch = False
        
        cookie_box = None
        detected_objects = []

        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                score = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                class_name = self.model.names[cls].lower()
                
                detected_objects.append((int(x1), int(y1), int(x2), int(y2), class_name, score))
                if class_name == "cookie":
                    cookie_box = (int(x1), int(y1), int(x2), int(y2))

        # หากเปิดบอทกลางเกมหรืออยู่สถานะอื่นนอกจากการเล่น/พัก แต่ตรวจเจอตัวคุกกี้และแผ่นดินใต้เท้า (ground)
        # ให้ซิงค์สเตทเข้าสู่การควบคุมการเล่น (STATE_PLAYING) ทันทีโดยไม่ต้องรอจบรอบ
        if self.autostart_enabled and self.current_state not in (self.STATE_PLAYING, self.STATE_RESTING):
            has_cookie = any(obj[4] == "cookie" for obj in detected_objects)
            has_ground = any(obj[4] == "ground" for obj in detected_objects)
            if has_cookie and has_ground:
                print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: ตรวจพบตัวละครคุกกี้และพื้นฉากเกมเพลย์ -> สลับเข้าสู่โหมดควบคุมการเล่น (STATE_PLAYING) ทันที!")
                self.current_state = self.STATE_PLAYING
                self.gameplay_start_time = now
                self.last_action_time = now

        # หากอยู่ในสถานะรอโหลดเข้าเกมแบบไดนามิก
        if self.current_state == self.STATE_WAIT_LOADING:
            # 1. เช็คว่ามีปุ่มวงกลมสีเขียวสำหรับกดใช้ Boost Start ปรากฏกลางจอแล้วหรือยัง (ใช้ Template Matching เพื่อความชัวร์ 100%)
            found_btn = False
            cx_btn, cy_btn = 410, 220
            
            if "boost_start_btn" in self.autostart_templates:
                # ครอปแสกนหาปุ่มเฉพาะแถบกึ่งกลางจอเพื่อลดภาระของ CPU (ROI X: 300-500, Y: 130-300)
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                roi_gray = gray_frame[130:300, 300:500]
                
                res = cv2.matchTemplate(roi_gray, self.autostart_templates["boost_start_btn"], cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                
                # ลดเกณฑ์เหลือ 0.65 เพื่อดึงปุ่มได้ไวขึ้นตอนเริ่มสว่าง
                if max_val >= 0.65:
                    found_btn = True
                    cx_btn = 300 + max_loc[0] + self.autostart_templates["boost_start_btn"].shape[1] // 2
                    cy_btn = 130 + max_loc[1] + self.autostart_templates["boost_start_btn"].shape[0] // 2
                    print(f"[{time.strftime('%H:%M:%S')}] 🚀 ตรวจพบปุ่ม Boost Start บนจอด้วย Template Match (Score: {max_val:.3f})")

            # 2. เช็คตัวประกอบว่าโหลดผ่านหน้าจอดำเข้าสู่เกมแล้วหรือยังผ่าน YOLO
            found_gameplay = False
            for x1, y1, x2, y2, c_name, conf in detected_objects:
                if c_name in ["cookie", "ground", "jump_obs", "slide_obs", "raised_floor"]:
                    found_gameplay = True
                    break
            
            # คำนวณเวลาที่ใช้โหลดด่านไปแล้ว
            elapsed_loading = now - self.loading_start_time
            
            should_activate = False
            if self.use_boost_start:
                # กรณีเปิดใช้ Boost: จะต้องพบปุ่ม Boost Start จริงๆ หรือถ้าหมดเวลา 2.5 วินาทีแล้วก็ให้ยอมปล่อยผ่านเมื่อเจอเกมเพลย์ หรือหมดเวลา 6 วินาทีป้องกันค้าง
                if found_btn or (elapsed_loading > 2.5 and found_gameplay) or elapsed_loading > 6.0:
                    should_activate = True
            else:
                # กรณีไม่ใช้ Boost: ตรวจเจอฉากเกมเพลย์ปกติก็เริ่มเล่นได้ทันที หรือถ้าหมดเวลา 5 วินาทีแล้วยังหาไม่เจอให้ข้ามไปเล่นเลย
                if found_gameplay or elapsed_loading > 5.0:
                    should_activate = True
            
            if not hasattr(self, "last_loading_print_time"):
                self.last_loading_print_time = 0
            if now - self.last_loading_print_time > 1.0:
                self.last_loading_print_time = now
                print(f"[DEBUG Loading] state=WAIT_LOADING, elapsed={elapsed_loading:.1f}s, found_gameplay={found_gameplay}, should_activate={should_activate}")
            
            if should_activate:
                print(f"[{time.strftime('%H:%M:%S')}] 🎮 โหลดเข้าสู่เกมเรียบร้อย! (ปุ่ม Boost={found_btn}, ออบเจกต์ในเกม={found_gameplay}, โหลดด่าน={elapsed_loading:.1f}s)")
                if self.use_boost_start and found_btn:
                    print(f"[{time.strftime('%H:%M:%S')}] 🚀 ส่งคีย์ Alt + คลิกเมาส์ที่พิกัด ({cx_btn}, {cy_btn}) เพื่อใช้ Boost Start (สแปม 3 ครั้งแบบ non-blocking)")
                    # ครั้งแรกส่งทันที
                    human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08)
                    human_click_bg(self.hwnd, cx_btn, cy_btn, "Activate Boost Start #1")
                    # ครั้งที่ 2 และ 3 จองคิวด้วย self.after() แทน time.sleep()
                    self.after(150, lambda: (
                        human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08),
                        human_click_bg(self.hwnd, cx_btn, cy_btn, "Activate Boost Start #2")
                    ))
                    self.after(300, lambda: (
                        human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08),
                        human_click_bg(self.hwnd, cx_btn, cy_btn, "Activate Boost Start #3")
                    ))
                
                self.current_state = self.STATE_PLAYING
                self.gameplay_start_time = now
                self.has_logged_afk_transition = False
                self.last_action_time = now
            else:
                # ยังโหลดไม่เสร็จ หรือกำลังรอให้ปุ่มปีกนกเด้งขึ้นมาฉายเดี่ยว
                self.schedule_next_loop(start_time)
                return

        # Check character switch player template (ผลัดสอง)
        if self.use_relay and self.template_btn is not None:
            if now - self.last_switch_check_time > 0.4:
                self.last_switch_check_time = now
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                max_val = -1
                max_loc = None
                tw, th = 0, 0
                
                # Check template match (scale 1)
                try:
                    res1 = cv2.matchTemplate(gray_frame, self.template_btn, cv2.TM_CCOEFF_NORMED)
                    _, max_val1, _, max_loc1 = cv2.minMaxLoc(res1)
                    max_val = max_val1
                    max_loc = max_loc1
                    th, tw = self.template_btn.shape[:2]
                except Exception as e:
                    pass
                
                # Check template match (scale 2)
                try:
                    left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
                    W_client = right - left - 16
                    if W_client > 100:
                        scale_factor = 800.0 / W_client
                        scaled_w = int(self.template_btn.shape[1] * scale_factor)
                        scaled_h = int(self.template_btn.shape[0] * scale_factor)
                        if scaled_w > 10 and scaled_h > 10:
                            template_scaled = cv2.resize(self.template_btn, (scaled_w, scaled_h))
                            res2 = cv2.matchTemplate(gray_frame, template_scaled, cv2.TM_CCOEFF_NORMED)
                            _, max_val2, _, max_loc2 = cv2.minMaxLoc(res2)
                            
                            if max_val2 > max_val:
                                max_val = max_val2
                                max_loc = max_loc2
                                tw, th = scaled_w, scaled_h
                except Exception as e:
                    pass
                
                if max_val > 0.65:
                    self.cached_switch_status = True
                    self.cached_switch_rect = (max_loc, tw, th)
                    self.cached_switch_val = max_val
                    print(f"[{time.strftime('%H:%M:%S')}] 🔍 ตรวจพบปุ่มผลัดสอง! Match Score: {max_val:.3f} (เกณฑ์: 0.65)")
                else:
                    self.cached_switch_status = False

            if self.cached_switch_status and self.cached_switch_rect is not None:
                found_switch = True


        if not hasattr(self, "smoothed_cookie_x"):
            self.smoothed_cookie_x = self.FALLBACK_COOKIE_X

        if cookie_box is not None:
            # เกลี่ยตำแหน่งคุกกี้ด้วย EMA เพื่อลดการสั่นไหวของกรอบ YOLO
            self.smoothed_cookie_x = self.smoothed_cookie_x * 0.8 + cookie_box[2] * 0.2
        else:
            # หากไม่พบ ค่อยๆ ขยับสไลด์กลับมาพิกัดสำรองช้าๆ ป้องกันจังหวะกระตุก
            self.smoothed_cookie_x = self.smoothed_cookie_x * 0.95 + self.FALLBACK_COOKIE_X * 0.05

        cookie_front_x = self.smoothed_cookie_x

        # Distance calculations
        jump_obstacles = []
        slide_obstacles = []
        closest_obstacle_info = None
        closest_obstacle_distance = 9999

        for x1, y1, x2, y2, c_name, conf in detected_objects:
            if x1 > cookie_front_x:
                distance = x1 - cookie_front_x
                if distance < 400:
                    if c_name in ["jump_obs", "jump_potato", "double_jump_obs", "raised_floor", "coin"]:
                        jump_obstacles.append((int(x1), int(x2), int(y1), int(y2), c_name, distance))
                    elif c_name == "slide_obs":
                        slide_obstacles.append((int(x1), int(x2), int(y1), int(y2), c_name, distance))
                    
                    if distance < closest_obstacle_distance:
                        closest_obstacle_distance = distance
                        closest_obstacle_info = (int(x1), int(y1), int(x2), int(y2), c_name, distance)

        jump_obstacles.sort(key=lambda o: o[5])
        slide_obstacles.sort(key=lambda o: o[5])

        # คำนวณหาความเร็วของสิ่งกีดขวางแบบไดนามิกข้ามเฟรมเพื่อวัดค่าความเร็วในการเลื่อนหน้าจอ
        if closest_obstacle_info is not None:
            obs_x1, obs_y1, obs_x2, obs_y2, obs_name, dist = closest_obstacle_info
            
            # Anti-Detection: สุ่มความคลาดเคลื่อนจังหวะกด (Jitter) ล่าสุดแบบรายอุปสรรค
            # หากระยะทางเพิ่มขึ้น (เช็ค dist > self.last_closest_dist + 50) แสดงว่าเป็นอุปสรรคชิ้นใหม่ ให้สุ่ม Jitter ใหม่
            if self.last_closest_dist == 0 or dist > self.last_closest_dist + 50:
                self.current_jitter = random.uniform(-0.04, 0.04) # สุ่ม +/- 40ms เพื่อไม่ให้จังหวะทริกเกอร์คงที่
            self.last_closest_dist = dist
            
            if self.last_obstacle_x is not None and self.last_obstacle_time is not None:
                dt = now - self.last_obstacle_time
                dx = self.last_obstacle_x - obs_x1
                # ตรวจเช็คว่าน่าจะเป็นสิ่งกีดขวางชิ้นเดียวกันเคลื่อนที่มาทางซ้าย
                if 0.015 < dt < 0.200 and 0 < dx < 200:
                    measured_speed = dx / dt
                    # กรองความเร็วด้วยสูตร Exponential Moving Average (EMA) ป้องกันค่ากระชาก
                    self.estimated_speed = self.estimated_speed * 0.85 + measured_speed * 0.15
                    # จำกัดความเร็วให้อยู่ในช่วงที่เหมาะสม (150.0 ถึง 900.0 px/s)
                    self.estimated_speed = max(150.0, min(self.estimated_speed, 900.0))
            
            self.last_obstacle_x = obs_x1
            self.last_obstacle_time = now
        else:
            self.last_obstacle_x = None
            self.last_obstacle_time = None
            self.last_closest_dist = 0
            self.current_jitter = 0.0

        # คำนวณ TTC (Time-To-Collision) threshold จาก trigger_dist และความเร็วปัจจุบัน
        # แปลงระยะ trigger_dist (px) เป็นเวลา (วินาที) — ทำให้ timing คงที่ไม่ว่าจะวิ่งเร็วแค่ไหน
        normal_speed = 350.0
        speed_factor = self.estimated_speed / normal_speed
        
        # Anti-Detection: คำนวณความล้าสะสม (Fatigue) ยิ่งเล่นไปหลายรอบการตัดสินใจยิ่งช้าลงเล็กน้อย (ลด TTC ลง)
        max_runs = max(1, self.target_session_runs)
        fatigue_ratio = min(self.current_session_runs / max_runs, 1.0)
        fatigue_delay = fatigue_ratio * random.uniform(0.02, 0.06) # หน่วงปฏิกิริยาช้าลง 20-60ms ตามรอบเซสชัน
        
        trigger_ttc = (self.trigger_dist / max(self.estimated_speed, 1.0)) + self.current_jitter - fatigue_delay
        # จำกัด TTC ให้อยู่ในช่วงปลอดภัย (0.12 ถึง 0.80 วินาที)
        trigger_ttc = max(0.12, min(trigger_ttc, 0.80))

        # ดีบักความเร็วทุกๆ 1 วินาที
        if not hasattr(self, "last_speed_print_time"):
            self.last_speed_print_time = 0
        if now - self.last_speed_print_time > 1.0:
            self.last_speed_print_time = now
            print(f"📊 Speed: {self.estimated_speed:.1f} px/s | TTC Trigger: {trigger_ttc:.3f}s (Base Dist: {self.trigger_dist}px)")
            self.speed_label.configure(text=f"Speed: {self.estimated_speed:.0f} px/s  |  TTC: {trigger_ttc:.3f}s")

        if closest_obstacle_info is not None:
            obs_x1, obs_y1, obs_x2, obs_y2, obs_name, dist = closest_obstacle_info
            
            cookie_center_y = cookie_box[1] + int((cookie_box[3]-cookie_box[1])/2) if cookie_box else 250
            obs_center_y = obs_y1 + int((obs_y2-obs_y1)/2)

            # คำนวณ TTC ของสิ่งกีดขวางที่ใกล้ที่สุด (เวลาที่เหลือก่อนชน)
            obs_ttc = dist / max(self.estimated_speed, 1.0)

            if obs_ttc <= trigger_ttc:
                if obs_name in ["jump_obs", "jump_potato", "double_jump_obs", "raised_floor", "coin"]:
                    is_double_jump = False
                    if obs_name == "double_jump_obs":
                        is_double_jump = True
                    elif len(jump_obstacles) >= 2:
                        first_obs = jump_obstacles[0]
                        second_obs = jump_obstacles[1]
                        gap_px = second_obs[0] - first_obs[1]
                        # แปลง gap เป็นเวลา — ถ้าห่างกันไม่ถึง 0.35 วินาที ถือว่าต้อง double jump
                        gap_time = gap_px / max(self.estimated_speed, 1.0)
                        if gap_time < 0.35:
                            is_double_jump = True
                            
                    if is_double_jump:
                        found_double_jump_obstacle = True
                    else:
                        found_jump_obstacle = True
                        
                elif obs_name == "slide_obs":
                    found_slide_obstacle = True

        # Anti-Detection: จำลอง Junk Inputs (กดปุ่มกระโดด/สไลด์เล่นแก้เบื่อ เลียนแบบมนุษย์)
        # เงื่อนไข: ไม่เจอสิ่งกีดขวางระยะประชิด (dist > 280px) หรือไม่มีอุปสรรคอยู่เลย และไม่ได้กดค้างปุ่มใดๆ
        if not (found_jump_obstacle or found_double_jump_obstacle or found_slide_obstacle):
            if closest_obstacle_info is None or closest_obstacle_distance > 280:
                # สุ่มแตะจังหวะว่างทุกๆ 12 ถึง 25 วินาที
                if now - self.last_junk_input_time > random.uniform(12.0, 25.0):
                    self.last_junk_input_time = now
                    junk_type = random.choice(["JUMP", "DOUBLE_JUMP", "SLIDE"])
                    
                    if junk_type == "JUMP" and now - self.last_jump_time > 1.5:
                        found_jump_obstacle = True
                        print(f"[{time.strftime('%H:%M:%S')}] 🤪 Anti-Detection: แอบกดกระโดดเปล่าเลียนแบบผู้เล่นจริง")
                    elif junk_type == "DOUBLE_JUMP" and now - self.last_jump_time > 1.8:
                        found_double_jump_obstacle = True
                        print(f"[{time.strftime('%H:%M:%S')}] 🤪 Anti-Detection: แอบกดดับเบิ้ลจัมพ์เล่นเลียนแบบผู้เล่นจริง")
                    elif junk_type == "SLIDE" and now - self.last_slide_time > 1.5:
                        found_slide_obstacle = True
                        print(f"[{time.strftime('%H:%M:%S')}] 🤪 Anti-Detection: แอบกดหมอบสไลด์สั้นเลียนแบบผู้เล่นจริง")

        # Cliff detection (ระบบแสกนขอบเหว)
        ground_boxes = []
        for x1, y1, x2, y2, c_name, conf in detected_objects:
            if c_name == "ground":
                ground_boxes.append((x1, x2, y1, y2))

        for x1, x2, y1, y2 in ground_boxes:
            # เช็คตำแหน่งแผ่นดินใต้เท้าด้วยพิกัดล็อกหน้าจอคงที่ (180 ถึง 220) เพื่อความเสถียรสูงสุด
            if x1 <= 220 and x2 >= 180:
                # คำนวณระยะห่างเหวโดยอิงจากตำแหน่งจุดเริ่มกระโดด 220 ป้องกันพิกัดเหวแกว่งตอนคุกกี้ลอยตัว
                dist_to_cliff = x2 - 220
                # แปลงระยะเหวเป็น TTC เพื่อให้สอดคล้องกับระบบทริกเกอร์หลัก
                cliff_ttc = dist_to_cliff / max(self.estimated_speed, 1.0)
                # ทริกเกอร์กระโดดเมื่อเหวเหลือ 0.03 ถึง 0.45 วินาที
                if 0.03 < cliff_ttc <= 0.45:
                    has_continuation = False
                    for nx1, nx2, ny1, ny2 in ground_boxes:
                        if 0 <= (nx1 - x2) < 45:
                            has_continuation = True
                            break
                    for rx1, ry1, rx2, ry2, rc_name, rconf in detected_objects:
                        if rc_name == "raised_floor":
                            if 0 <= (rx1 - x2) < 45:
                                has_continuation = True
                                break
                    if not has_continuation:
                        found_jump_obstacle = True
                        # print(f"[{time.strftime('%H:%M:%S')}] เรดาร์เตือน: ตรวจพบขอบเหวห่างออกไป {int(dist_to_cliff)}px -> สั่งกระโดดหลบเหว!")
                        break

        # Background keyboard control inputs
        current_status = "RUNNING"
        
        lParam_shift_down = 1 | (SCAN_SHIFT << 16)
        lParam_shift_up = 1 | (SCAN_SHIFT << 16) | (1 << 30) | (1 << 31)
        lParam_space_down = 1 | (SCAN_SPACE << 16)
        lParam_space_up = 1 | (SCAN_SPACE << 16) | (1 << 30) | (1 << 31)
        lParam_alt_down = 1 | (SCAN_ALT << 16)
        lParam_alt_up = 1 | (SCAN_ALT << 16) | (1 << 30) | (1 << 31)

        if found_switch and now - self.last_switch_time > 5.0:
            current_status = "SWITCH_COOKIE"
            print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> เปลี่ยนตัว Alt")
            
            # 1. ส่งสัญญาณคีย์บอร์ด Alt ครั้งแรกทันที ครั้งที่ 2 จองคิวแบบ non-blocking
            human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08)
            delay_ms = int(random.uniform(60, 100))
            self.after(delay_ms, lambda: human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08))
            
            # 2. ส่งสัญญาณคลิกเมาส์เสมือนตรงไปที่ปุ่มบนจอ
            if self.cached_switch_rect is not None:
                max_loc, tw, th = self.cached_switch_rect
                cx = max_loc[0] + int(tw / 2)
                cy = max_loc[1] + int(th / 2)
                print(f"   - ส่งคลิกเมาส์จำลองไปที่พิกัดปุ่มผลัดสอง: ({cx}, {cy})")
                human_click_bg(self.hwnd, cx, cy, "Relay Switch Button")
                
            self.last_switch_time = now
        
        elif found_double_jump_obstacle and now - self.last_jump_time > 0.50:
            current_status = "DOUBLE_JUMP"
            # print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> ดับเบิ้ลจัมพ์ (Non-Blocking)")
            self.force_release_key(VK_SPACE, SCAN_SPACE)
            
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, lParam_shift_down)
            r1_shift = random.uniform(0.05, 0.08)
            self.schedule_action(r1_shift, VK_LSHIFT, lambda lp=lParam_shift_up: win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_LSHIFT, lp))
            p2_shift = r1_shift + random.uniform(0.16, 0.22)
            self.schedule_action(p2_shift, VK_LSHIFT, lambda lp=lParam_shift_down: win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, lp))
            r2_shift = p2_shift + random.uniform(0.05, 0.08)
            self.schedule_action(r2_shift, VK_LSHIFT, lambda lp=lParam_shift_up: win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_LSHIFT, lp))
            
            self.last_jump_time = now
            self.last_action_time = now
            
        elif found_jump_obstacle and now - self.last_jump_time > 0.40:
            current_status = "JUMPING"
            # print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> กระโดด (Non-Blocking)")
            self.force_release_key(VK_SPACE, SCAN_SPACE)
            
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, lParam_shift_down)
            jump_duration = random.uniform(0.06, 0.10)
            self.schedule_action(jump_duration, VK_LSHIFT, lambda lp=lParam_shift_up: win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_LSHIFT, lp))
            
            self.last_jump_time = now
            self.last_action_time = now
            
        elif found_slide_obstacle and now - self.last_slide_time > 0.35:
            current_status = "SLIDING"
            # print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> หมอบสไลด์ (Non-Blocking)")
            self.force_release_key(VK_LSHIFT, SCAN_SHIFT)
            
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_SPACE, lParam_space_down)
            slide_duration = (self.slide_hold_ms / 1000.0) * random.uniform(0.95, 1.05)
            self.schedule_action(slide_duration, VK_SPACE, lambda lp=lParam_space_up: win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_SPACE, lp))
            
            self.last_slide_time = now
            self.last_action_time = now

        # Update bot status UI labels
        if current_status == "RUNNING":
            self.bot_status_label.configure(text=f"STATUS: {current_status}", fg="#2ecc71")
        else:
            self.bot_status_label.configure(text=f"STATUS: {current_status}", fg="#e74c3c")

        self.schedule_next_loop(start_time)


