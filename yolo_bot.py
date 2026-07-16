import cv2
import numpy as np
import time
import random
import ctypes
import os
import win32gui
import win32con
import win32ui
from ultralytics import YOLO
import tkinter as tk
from PIL import Image, ImageTk
import traceback

# ----------------- Windows Background Input Configuration -----------------
SCAN_SHIFT = 0x2A
SCAN_SPACE = 0x39
SCAN_ALT = 0x38           # Scan code ของปุ่ม Alt

VK_LSHIFT = win32con.VK_LSHIFT
VK_SPACE = win32con.VK_SPACE
VK_ALT = win32con.VK_MENU  # ปุ่ม Alt สำหรับเปลี่ยนตัวผลัดสอง

def human_press_bg(hwnd, vk_code, scan_code, duration_min=0.05, duration_max=0.12):
    """ส่งสัญญาณกดคีย์บอร์ดเสมือนตรงไปที่หน้าต่างเบื้องหลัง (Background Input)"""
    lParam_down = 1 | (scan_code << 16)
    lParam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
    
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
    hold_time = random.uniform(duration_min, duration_max)
    time.sleep(hold_time)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)

def find_render_hwnd(parent_hwnd):
    """ค้นหาหน้าต่างลูกของ Emulator ที่เป็นหน้าต่างเรนเดอร์/รับอินพุตจริง"""
    render_hwnd = [parent_hwnd]
    
    def cb(hwnd, extra):
        classname = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        
        # ค้นหาเป้าหมายหลักที่มีคำว่า mumunxdevice (เช่นหน้าต่างหลักคันวาส MuMuNxDevice)
        if "mumunxdevice" in title.lower() or "mumunxdevice" in classname.lower():
            render_hwnd[0] = hwnd
            return False
            
        # สำรองเผื่อกรณีเป็นตัวจำลองคลาสอื่นที่มีคำว่า render หรือ d3d
        if "render" in classname.lower() or "render" in title.lower() or "d3d" in classname.lower():
            render_hwnd[0] = hwnd
        return True
        
    try:
        win32gui.EnumChildWindows(parent_hwnd, cb, None)
    except:
        pass
        
    if render_hwnd[0] == parent_hwnd:
        children = []
        def cb2(hwnd, extra):
            children.append(hwnd)
            return True
        try:
            win32gui.EnumChildWindows(parent_hwnd, cb2, None)
            if children:
                render_hwnd[0] = children[-1]
        except:
            pass
            
    return render_hwnd[0]

def human_click_bg(hwnd, x_norm, y_norm, click_name=""):
    """คลิกเมาส์ซ้ายเบื้องหลังจำลองแบบมนุษย์ โดยสเกลพิกัด 800x450 ไปยังพิกัดจริงของหน้าต่างย่อยที่เรนเดอร์เกม"""
    try:
        target_hwnd = find_render_hwnd(hwnd)
        left, top, w_client, h_client = win32gui.GetClientRect(target_hwnd)
        
        if w_client <= 0 or h_client <= 0:
            left_w, top_w, right_w, bot_w = win32gui.GetWindowRect(hwnd)
            w = right_w - left_w
            h = bot_w - top_w
            w_client = w - 16
            h_client = h - 46
            target_hwnd = hwnd
            x_actual = int(8 + x_norm * (w_client / 800.0))
            y_actual = int(38 + y_norm * (h_client / 450.0))
        else:
            x_actual = int(x_norm * (w_client / 800.0))
            y_actual = int(y_norm * (h_client / 450.0))
            
        x_final = x_actual + random.randint(-3, 3)
        y_final = y_actual + random.randint(-3, 3)
        x_final = max(0, min(x_final, w_client - 1))
        y_final = max(0, min(y_final, h_client - 1))
        
        lParam = (y_final << 16) | (x_final & 0xFFFF)
        
        print(f"🖱️ [Click] '{click_name}' (Target HWND: {target_hwnd}) | สเกล ({x_norm}, {y_norm}) -> พิกัดจริง ({x_final}, {y_final})")
        
        win32gui.PostMessage(target_hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(random.uniform(0.03, 0.06))
        win32gui.PostMessage(target_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(random.uniform(0.08, 0.15))
        win32gui.PostMessage(target_hwnd, win32con.WM_LBUTTONUP, 0, lParam)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการคลิกเมาส์เบื้องหลัง: {e}")

def find_template_match(hwnd, frame, template_img, threshold=0.75):
    """ค้นหาตำแหน่งรูปภาพต้นแบบในเฟรมหน้าจอ คืนค่า (พบหรือไม่, พิกัด X, พิกัด Y) เทียบกับสเกล 800x450"""
    if template_img is None or hwnd is None:
        return False, 0, 0
    try:
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_frame, template_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # แสดงคะแนน Debug สำหรับวิเคราะห์หาปุ่ม
        h, w = template_img.shape[:2]
        if (h == 58 and w == 176) or (h == 60 and w == 181):
            now = time.time()
            if not hasattr(find_template_match, "last_debug_time"):
                find_template_match.last_debug_time = 0
            if now - find_template_match.last_debug_time > 1.5:
                find_template_match.last_debug_time = now
                name = "openall" if w == 176 else "confirmafteropenall"
                print(f"[Debug Match] {name} score: {max_val:.4f} (Threshold: {threshold})")
        
        if max_val >= threshold:
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return True, center_x, center_y
    except Exception as e:
        pass
    return False, 0, 0


def capture_window_bg(hwnd):
    """ดึงภาพสกรีนช็อกจากวินโดวส์เป้าหมายเบื้องหลัง แม้จะมีหน้าต่างอื่นบังอยู่ โดยจับที่หน้าต่างย่อยก่อน ถ้าไม่ได้ค่อยครอปหน้าต่างหลัก"""
    try:
        # ค้นหาหน้าต่างย่อยที่เป็นตัวเรนเดอร์เกมจริง
        target_hwnd = find_render_hwnd(hwnd)
        
        # 1. พยายามดึงภาพจากหน้าต่างย่อยโดยตรง (ไม่มีขอบ/ไตเติลบาร์)
        left, top, right, bot = win32gui.GetWindowRect(target_hwnd)
        w = right - left
        h = bot - top
        
        if w > 50 and h > 50:
            hwndDC = win32gui.GetWindowDC(target_hwnd)
            mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
            saveDC.SelectObject(saveBitMap)
            
            result = ctypes.windll.user32.PrintWindow(target_hwnd, saveDC.GetSafeHdc(), 3)
            
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype='uint8')
            img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
            
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(target_hwnd, hwndDC)
            
            if result == 1:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                # ตรวจสอบว่ารูปไม่ได้ดำสนิท
                if np.mean(img_bgr) > 5.0:
                    return cv2.resize(img_bgr, (800, 450))

        # 2. ถ้าดึงจากหน้าต่างย่อยไม่สำเร็จ ให้ย้อนกลับไปดึงจากหน้าต่างหลักแล้วครอปตัดขอบ (Fallback)
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        w = right - left
        h = bot - top
        if w <= 0 or h <= 0:
            return None

        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)
        
        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
        
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        if result == 1:
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            if img_bgr.shape[0] > 50 and img_bgr.shape[1] > 50:
                cropped = img_bgr[38:-8, 8:-8]
                return cv2.resize(cropped, (800, 450))
            return cv2.resize(img_bgr, (800, 450))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงภาพเบื้องหลัง: {e}")
    return None

class CookieRunAIApp(tk.Tk):
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
        self.slide_hold_ms = 810
        self.conf_val = 0.30
        self.autostart_enabled = True

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
        self.STATE_RESTING = "RESTING"
        
        self.current_state = self.STATE_PLAYING
        self.last_action_time = 0
        self.last_random_jump_check_time = 0
        self.last_switch_check_time = 0
        self.last_endgame_check_time = 0
        self.action_cooldown = 0.30
        
        # Switch variables
        self.cached_switch_status = False
        self.cached_switch_rect = None
        self.cached_switch_val = 0.0
        self.FALLBACK_COOKIE_X = 220
        
        # Autostart templates
        self.autostart_templates = {}
        
        # Load resources and search emulator window
        self.init_resources()
        
        # Construct UI elements
        self.create_layout()
        
        # Bind closing protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start cooperative loop
        self.after(100, self.update_loop)

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
                    if "android device" in t.lower() or "mumuplayer" in t.lower() or "mumu" in c.lower() or "mumu" in t.lower():
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
        if os.path.exists("best.pt"):
            print("📥 กำลังโหลดโมเดล YOLOv8 'best.pt'...")
            self.model = YOLO("best.pt")
            print("✅ โหลดโมเดล YOLOv8 สำเร็จ!")
        else:
            print("❌ ไม่พบโมเดล 'best.pt' ในโฟลเดอร์บอท!")

        # 3. Load switch template
        if os.path.exists("autochangeplayer.png"):
            self.template_btn = cv2.imread("autochangeplayer.png", cv2.IMREAD_GRAYSCALE)
            print("📥 โหลดปุ่มผลัดสองสำรองสำเร็จ!")

        # 4. Load autostart templates
        autostart_dir = "C:/Users/gluee/Desktop/cookierunbot/autostart"
        autostart_files = {
            "ok": "ok_1.png",
            "openall": "openall_2.png",
            "confirmafteropenall": "confirmafteropenall_1.png",
            "playlobby": "playlobby_1.png",
            "selectbuff_1": "selectbuff_1.png",
            "selectbuff_2": "selectbuff_2.png",
            "selectbuff_3": "selectbuff_3.png",
            "affterselectbuff": "affterselectbuff_1.png",
            "confirmlevelup": "confirmlevelup1.png"
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

    def create_layout(self):
        # Configure grid for root window
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- Left Panel: Control and Settings ---
        self.sidebar_frame = tk.Frame(self, bg="#1e1e24")
        self.sidebar_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        # Header title
        self.logo_label = tk.Label(self.sidebar_frame, text="Cookie Run AI Bot", font=("Arial", 16, "bold"), fg="#3498db", bg="#1e1e24")
        self.logo_label.pack(pady=(20, 5))
        
        # Connection status label
        status_text = "Emulator: CONNECTED" if self.hwnd else "Emulator: DISCONNECTED"
        status_color = "#2ecc71" if self.hwnd else "#e74c3c"
        self.status_label = tk.Label(self.sidebar_frame, text=status_text, font=("Arial", 10, "bold"), fg=status_color, bg="#1e1e24")
        self.status_label.pack(pady=(0, 20))
        
        # Decorative divider
        self.divider = tk.Frame(self.sidebar_frame, height=2, bg="#2c2c35")
        self.divider.pack(fill="x", padx=20, pady=5)
        
        # Settings Container
        self.settings_frame = tk.Frame(self.sidebar_frame, bg="#1e1e24")
        self.settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Tkinter variables for Checkbuttons
        self.autostart_var = tk.IntVar(value=1 if self.autostart_enabled else 0)
        self.rest_var = tk.IntVar(value=1 if self.rest_breaks_enabled else 0)
        self.eco_var = tk.IntVar(value=1 if self.eco_mode_enabled else 0)

        # Toggle Switch for Auto Start
        self.autostart_switch = tk.Checkbutton(
            self.settings_frame, text="Auto Start Game", font=("Arial", 10, "bold"),
            variable=self.autostart_var, command=self.on_toggle_autostart,
            bg="#1e1e24", fg="#ffffff", selectcolor="#2c2c35",
            activebackground="#1e1e24", activeforeground="#ffffff", bd=0, highlightthickness=0
        )
        self.autostart_switch.pack(pady=3, anchor="w")
        
        # Toggle Switch for Auto-Rest Breaks
        self.rest_switch = tk.Checkbutton(
            self.settings_frame, text="Auto-Rest Breaks", font=("Arial", 10, "bold"),
            variable=self.rest_var, command=self.on_toggle_rest,
            bg="#1e1e24", fg="#ffffff", selectcolor="#2c2c35",
            activebackground="#1e1e24", activeforeground="#ffffff", bd=0, highlightthickness=0
        )
        self.rest_switch.pack(pady=3, anchor="w")
        
        # Toggle Switch for Eco Mode
        self.eco_mode_switch = tk.Checkbutton(
            self.settings_frame, text="Eco Mode (20 FPS)", font=("Arial", 10, "bold"),
            variable=self.eco_var, command=self.on_toggle_eco,
            bg="#1e1e24", fg="#ffffff", selectcolor="#2c2c35",
            activebackground="#1e1e24", activeforeground="#ffffff", bd=0, highlightthickness=0
        )
        self.eco_mode_switch.pack(pady=3, anchor="w")
        
        # Session Progress Label
        self.session_runs_label = tk.Label(self.settings_frame, text=f"Session: {self.current_session_runs}/{self.target_session_runs} games", font=("Arial", 10, "bold"), fg="#9b59b6", bg="#1e1e24")
        self.session_runs_label.pack(anchor="w", pady=(8, 2))
        
        # Slider 0: Max Games per Session
        self.session_limit_title = tk.Label(self.settings_frame, text=f"Max Games/Session: {self.max_session_runs_limit} runs", font=("Arial", 9), fg="#ffffff", bg="#1e1e24")
        self.session_limit_title.pack(anchor="w", pady=(5, 1))
        self.session_limit_slider = tk.Scale(
            self.settings_frame, from_=5, to=30, orient=tk.HORIZONTAL, command=self.on_session_limit_change,
            bg="#1e1e24", fg="#ffffff", troughcolor="#2c2c35", activebackground="#3498db",
            bd=0, highlightthickness=0, showvalue=False
        )
        self.session_limit_slider.set(self.max_session_runs_limit)
        self.session_limit_slider.pack(fill="x", pady=(0, 5))
        
        # Slider 1: Trigger Distance
        self.dist_title = tk.Label(self.settings_frame, text=f"Trigger Distance: {self.trigger_dist} px", font=("Arial", 9), fg="#ffffff", bg="#1e1e24")
        self.dist_title.pack(anchor="w", pady=(5, 1))
        self.dist_slider = tk.Scale(
            self.settings_frame, from_=50, to=300, orient=tk.HORIZONTAL, command=self.on_dist_change,
            bg="#1e1e24", fg="#ffffff", troughcolor="#2c2c35", activebackground="#3498db",
            bd=0, highlightthickness=0, showvalue=False
        )
        self.dist_slider.set(self.trigger_dist)
        self.dist_slider.pack(fill="x", pady=(0, 5))
        
        # Slider 2: Slide Hold ms
        self.slide_title = tk.Label(self.settings_frame, text=f"Slide Hold: {self.slide_hold_ms} ms", font=("Arial", 9), fg="#ffffff", bg="#1e1e24")
        self.slide_title.pack(anchor="w", pady=(5, 1))
        self.slide_slider = tk.Scale(
            self.settings_frame, from_=100, to=1500, orient=tk.HORIZONTAL, command=self.on_slide_change,
            bg="#1e1e24", fg="#ffffff", troughcolor="#2c2c35", activebackground="#3498db",
            bd=0, highlightthickness=0, showvalue=False
        )
        self.slide_slider.set(self.slide_hold_ms)
        self.slide_slider.pack(fill="x", pady=(0, 5))
        
        # Slider 3: YOLO Conf threshold
        self.conf_title = tk.Label(self.settings_frame, text=f"YOLO Threshold: {int(self.conf_val * 100)}%", font=("Arial", 9), fg="#ffffff", bg="#1e1e24")
        self.conf_title.pack(anchor="w", pady=(5, 1))
        self.conf_slider = tk.Scale(
            self.settings_frame, from_=0.10, to=0.85, resolution=0.01, orient=tk.HORIZONTAL, command=self.on_conf_change,
            bg="#1e1e24", fg="#ffffff", troughcolor="#2c2c35", activebackground="#3498db",
            bd=0, highlightthickness=0, showvalue=False
        )
        self.conf_slider.set(self.conf_val)
        self.conf_slider.pack(fill="x", pady=(0, 8))
        
        # Second divider
        self.divider2 = tk.Frame(self.sidebar_frame, height=2, bg="#2c2c35")
        self.divider2.pack(fill="x", padx=20, pady=5)
        
        # Bottom Status Indicator
        self.bot_status_label = tk.Label(self.sidebar_frame, text="STATUS: RUNNING", font=("Arial", 13, "bold"), fg="#2ecc71", bg="#1e1e24")
        self.bot_status_label.pack(pady=15)
        


    # --- UI Callbacks ---
    def on_toggle_autostart(self):
        self.autostart_enabled = self.autostart_var.get() == 1
        print(f"⚙️ Auto Start Toggled: {self.autostart_enabled}")

    def on_toggle_rest(self):
        self.rest_breaks_enabled = self.rest_var.get() == 1
        print(f"⚙️ Auto-Rest Breaks Toggled: {self.rest_breaks_enabled}")

    def on_toggle_eco(self):
        self.eco_mode_enabled = self.eco_var.get() == 1
        print(f"⚙️ Eco Mode Toggled: {self.eco_mode_enabled}")

    def on_session_limit_change(self, val):
        self.max_session_runs_limit = int(val)
        self.session_limit_title.configure(text=f"Max Games/Session: {self.max_session_runs_limit} runs")
        
        # ปรับจูนค่าเป้าหมายปัจจุบันให้เหมาะสมกับลิมิตใหม่ทันทีหากมันมากเกินไป
        if self.target_session_runs > self.max_session_runs_limit:
            self.target_session_runs = self.max_session_runs_limit
            self.session_runs_label.configure(text=f"Session: {self.current_session_runs}/{self.target_session_runs} games")

    def on_dist_change(self, val):
        self.trigger_dist = int(val)
        self.dist_title.configure(text=f"Trigger Distance: {self.trigger_dist} px")

    def on_slide_change(self, val):
        self.slide_hold_ms = int(val)
        self.slide_title.configure(text=f"Slide Hold: {self.slide_hold_ms} ms")

    def on_conf_change(self, val):
        self.conf_val = float(val)
        self.conf_title.configure(text=f"YOLO Threshold: {int(self.conf_val * 100)}%")

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
            self.status_label.configure(text="Emulator: DISCONNECTED", fg="#e74c3c")
            self.bot_status_label.configure(text="STATUS: OFFLINE", fg="#e74c3c")
            self.init_resources()
            self.after(2000, self.update_loop)
            return

        self.status_label.configure(text="Emulator: CONNECTED", fg="#2ecc71")
        start_time = time.time()
        now = time.time()

        # Handle RESTING break state
        if self.current_state == self.STATE_RESTING:
            remaining = self.rest_end_time - now
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                
                # Update status displays
                self.bot_status_label.configure(text=f"RESTING ({mins:02d}:{secs:02d})", fg="#f39c12")
                self.session_runs_label.configure(text=f"Session: {self.current_session_runs}/{self.target_session_runs} (Resting)")

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
                self.session_runs_label.configure(text=f"Session: 0/{self.target_session_runs} games")

        # 1. Capture screen
        frame = capture_window_bg(self.hwnd)
        if frame is None:
            self.after(30, self.update_loop)
            return

        # 2. Check Autostart state machine (Self-correcting with dynamic retries)
        if self.autostart_enabled and self.current_state != self.STATE_PLAYING:
            self.bot_status_label.configure(text=f"STATUS: {self.current_state}", fg="#f39c12")
            

            # Global Level Up check
            if "confirmlevelup" in self.autostart_templates:
                found_lv, cx_lv, cy_lv = find_template_match(self.hwnd, frame, self.autostart_templates["confirmlevelup"])
                if found_lv:
                    print(f"[{time.strftime('%H:%M:%S')}] ⭐ ตรวจพบป๊อปอัป Level Up! ทำการคลิกปิดเพื่อไปต่อ...")
                    human_click_bg(self.hwnd, cx_lv, cy_lv, "Level Up Close Button")
                    time.sleep(random.uniform(2.0, 3.5))
                    self.schedule_next_loop(start_time)
                    return

            # Execute state actions
            if self.current_state == self.STATE_WAIT_OK:
                found_openall, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("openall", None), threshold=0.68)
                found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.68)
                found_lobby, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None))
                
                if found_openall:
                    self.current_state = self.STATE_WAIT_OPENALL
                elif found_confirm:
                    self.current_state = self.STATE_WAIT_CONFIRM_OPENALL
                elif found_lobby:
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
                found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.68)
                found_lobby, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None))
                
                if found_confirm:
                    self.current_state = self.STATE_WAIT_CONFIRM_OPENALL
                elif found_lobby:
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                else:
                    if "openall" in self.autostart_templates:
                        found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["openall"], threshold=0.68)
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
                found_lobby, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None))
                if found_lobby:
                    self.current_state = self.STATE_WAIT_PLAYLOBBY
                else:
                    if "confirmafteropenall" in self.autostart_templates:
                        found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["confirmafteropenall"], threshold=0.68)
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
                    found, cx, cy = find_template_match(self.hwnd, frame, self.autostart_templates["playlobby"])
                    if found:
                        # รอ 5.0 วินาทีหลังจากเปลี่ยนสเตทมาที่ WAIT_PLAYLOBBY
                        # เพื่อให้เกมรีเฟรชและโหลดหน้าล็อบบี้ให้เสร็จสมบูรณ์ก่อนกด Play
                        if now - self.last_action_time > 20.0:
                            print(f"[{time.strftime('%H:%M:%S')}] 🖱️ คลิกปุ่ม Play ล็อบบี้ด้วยพิกัดล็อก (680, 390)")
                            human_click_bg(self.hwnd, 680, 390, "Play Lobby Button")
                            self.last_action_time = now
                            self.current_state = self.STATE_WAIT_SELECTBUFF_1

            elif self.current_state == self.STATE_WAIT_SELECTBUFF_1:
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
                    self.current_state = self.STATE_WAIT_START

            elif self.current_state == self.STATE_WAIT_START:
                # 4. ตรวจเช็คความสว่างของพื้นหลังเพื่อดูว่าป๊อปอัปปิดหรือยัง (Dynamic Wait)
                # เมื่อป๊อปอัปปิดลง หน้าจอจะสว่างปกติ (พิกัดพื้นหลัง 140, 200 จะสว่าง > 180.0)
                # ในขณะที่ตอนเปิดป๊อปอัปอยู่ พื้นหลังจะถูกเบลอมืดลง (< 80.0)
                pixel = frame[200, 140]
                brightness = np.mean(pixel)
                
                # หากสุ่มเสร็จแล้ว ป๊อปอัปปิดตัวลง หน้าจอปกติสว่างขึ้น
                if brightness > 180.0:
                    if now - self.last_action_time > 1.0:
                        print(f"[{time.strftime('%H:%M:%S')}] 🎮 ตรวจพบป๊อปอัปปิดแล้ว (ความสว่างพื้นหลัง: {brightness:.1f}) -> คลิกปุ่มเริ่มวิ่งสีเขียว (670, 390)")
                        human_click_bg(self.hwnd, 670, 390, "Start Game Button")
                        
                        self.current_session_runs += 1
                        print(f"[{time.strftime('%H:%M:%S')}] 🎮 เริ่มต้นเกมใหม่สำเร็จ! (นับรอบสะสม: {self.current_session_runs}/{self.target_session_runs})")
                        self.session_runs_label.configure(text=f"Session: {self.current_session_runs}/{self.target_session_runs} games")
                        
                        self.current_state = self.STATE_PLAYING
                        self.last_action_time = now
                        time.sleep(random.uniform(3.0, 5.0))
                else:
                    # ป้องกันกรณีค้างหรือสุ่มนานเกิน 22 วินาที ให้บังคับกดปิดป๊อปอัป
                    if now - self.last_action_time > 22.0:
                        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ สุ่มบัฟนานเกิน 22 วินาที -> บังคับปิดป๊อปอัป X (612, 56)")
                        human_click_bg(self.hwnd, 612, 56, "Close Popup X Button")
                        self.last_action_time = now + 1.0  # หน่วงเวลาเพิ่มเพื่อให้สเตทถัดไปกดเพลย์หลังปิดจอ 2 วินาที

            self.schedule_next_loop(start_time)
            return

        # --- NORMAL GAMEPLAY: YOLO Run Controls ---
        self.bot_status_label.configure(text="STATUS: RUNNING", fg="#2ecc71")
        self.session_runs_label.configure(text=f"Session: {self.current_session_runs}/{self.target_session_runs} games")
        
        # Check if game ended (Anti-ban check before OK click)
        if self.autostart_enabled:
            if now - self.last_endgame_check_time > 1.5:
                self.last_endgame_check_time = now
                
                # สเตทที่กำลังอยู่ระหว่างโหลดหน้าร้านค้า/สุ่มบัฟ ไม่ควรให้ Sync Check แทรกแซง
                _transitioning = self.current_state in (
                    self.STATE_WAIT_SELECTBUFF_1,
                    self.STATE_WAIT_SELECTBUFF_2,
                    self.STATE_WAIT_SELECTBUFF_3,
                    self.STATE_WAIT_START,
                )
                
                # เช็คปุ่มอื่นๆ เพื่อกู้คืนสเตทเผื่อบอทรันกลางคันหรือสเตทไม่ตรงกับหน้าจอ
                found_openall, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("openall", None), threshold=0.68)
                found_confirm, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("confirmafteropenall", None), threshold=0.68)
                found_lobby, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("playlobby", None))
                found_buff1, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("selectbuff_1", None))
                found_start, _, _ = find_template_match(self.hwnd, frame, self.autostart_templates.get("affterselectbuff", None))
                
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
                    self.schedule_next_loop(start_time)
                    return
                elif found_buff1 or found_start:
                    if not _transitioning:
                        print(f"[{time.strftime('%H:%M:%S')}] 🔄 ซิงค์สเตทกลางคัน: พบหน้าจอซื้อบัฟ/เตรียมเริ่มเกม -> สลับสเตทเป็น WAIT_SELECTBUFF_1")
                        self.current_state = self.STATE_WAIT_SELECTBUFF_1
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
                            self.session_runs_label.configure(text=f"Session: {self.current_session_runs}/{self.target_session_runs} (Resting)")
                            self.bot_status_label.configure(text="RESTING", fg="#f39c12")
                            
                            self.schedule_next_loop(start_time)
                            return
                        else:
                            # Proceed with normal restart flow
                            self.current_state = self.STATE_WAIT_OK
                            print(f"[{time.strftime('%H:%M:%S')}] 🏁 พบหน้าจอจบเกม (ปุ่ม OK)! สลับเข้าสู่โหมดกดเริ่มใหม่อัตโนมัติ...")
                            time.sleep(random.uniform(1.5, 3.0))
                            
                            self.bot_status_label.configure(text=f"STATUS: {self.current_state}", fg="#f39c12")
                            self.schedule_next_loop(start_time)
                            return

        # YOLO inference
        if self.model is None:
            self.after(30, self.update_loop)
            return

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

        # Check character switch player template
        if self.template_btn is not None:
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
                
                if max_val > 0.75:
                    self.cached_switch_status = True
                    self.cached_switch_rect = (max_loc, tw, th)
                    self.cached_switch_val = max_val
                else:
                    self.cached_switch_status = False

            if self.cached_switch_status and self.cached_switch_rect is not None:
                found_switch = True


        cookie_front_x = self.FALLBACK_COOKIE_X

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

        if closest_obstacle_info is not None:
            obs_x1, obs_y1, obs_x2, obs_y2, obs_name, dist = closest_obstacle_info
            
            cookie_center_y = cookie_box[1] + int((cookie_box[3]-cookie_box[1])/2) if cookie_box else 250
            obs_center_y = obs_y1 + int((obs_y2-obs_y1)/2)

            if dist <= self.trigger_dist:
                if obs_name in ["jump_obs", "jump_potato", "double_jump_obs", "raised_floor", "coin"]:
                    is_double_jump = False
                    if obs_name == "double_jump_obs":
                        is_double_jump = True
                    elif len(jump_obstacles) >= 2:
                        first_obs = jump_obstacles[0]
                        second_obs = jump_obstacles[1]
                        gap = second_obs[0] - first_obs[1]
                        if gap < 130:
                            is_double_jump = True
                            
                    if is_double_jump:
                        found_double_jump_obstacle = True
                    else:
                        found_jump_obstacle = True
                        
                elif obs_name == "slide_obs":
                    found_slide_obstacle = True

        # Cliff detection
        ground_boxes = []
        for x1, y1, x2, y2, c_name, conf in detected_objects:
            if c_name == "ground":
                ground_boxes.append((x1, x2, y1, y2))

        for x1, x2, y1, y2 in ground_boxes:
            if x1 <= 220 and x2 >= 180:
                dist_to_cliff = x2 - cookie_front_x
                if 10 < dist_to_cliff <= 130:
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
                        print(f"[{time.strftime('%H:%M:%S')}] เรดาร์เตือน: ตรวจพบขอบเหวห่างออกไป {int(dist_to_cliff)}px -> สั่งกระโดดหลบเหว!")
                        break

        # Background keyboard control inputs
        current_status = "RUNNING"
        if now - self.last_action_time > self.action_cooldown:
            if found_switch:
                current_status = "SWITCH_COOKIE"
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> เปลี่ยนตัว Alt")
                human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08)
                time.sleep(random.uniform(0.06, 0.10))
                human_press_bg(self.hwnd, VK_ALT, SCAN_ALT, duration_min=0.05, duration_max=0.08)
                self.last_action_time = time.time()
            elif found_double_jump_obstacle:
                current_status = "DOUBLE_JUMP"
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> ดับเบิ้ลจัมพ์")
                win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, (SCAN_SHIFT << 16) | 1)
                time.sleep(random.uniform(0.05, 0.08))
                win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_LSHIFT, (SCAN_SHIFT << 16) | 1 | (1 << 30) | (1 << 31))
                time.sleep(random.uniform(0.16, 0.22))
                win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, (SCAN_SHIFT << 16) | 1)
                time.sleep(random.uniform(0.05, 0.08))
                win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_LSHIFT, (SCAN_SHIFT << 16) | 1 | (1 << 30) | (1 << 31))
                self.last_action_time = time.time()
            elif found_jump_obstacle:
                current_status = "JUMPING"
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> กระโดด")
                slide_duration = random.uniform(0.06, 0.10)
                human_press_bg(self.hwnd, VK_LSHIFT, SCAN_SHIFT, duration_min=slide_duration * 0.95, duration_max=slide_duration * 1.05)
                self.last_action_time = time.time()
            elif found_slide_obstacle:
                current_status = "SLIDING"
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> หมอบสไลด์")
                slide_duration = self.slide_hold_ms / 1000.0
                human_press_bg(self.hwnd, VK_SPACE, SCAN_SPACE, duration_min=slide_duration * 0.95, duration_max=slide_duration * 1.05)
                self.last_action_time = time.time()

        # Update bot status UI labels
        if current_status == "RUNNING":
            self.bot_status_label.configure(text=f"STATUS: {current_status}", fg="#2ecc71")
        else:
            self.bot_status_label.configure(text=f"STATUS: {current_status}", fg="#e74c3c")

        self.schedule_next_loop(start_time)


    def on_closing(self):
        self.destroy()
        print("=== ปิดการทำงานบอทเรียบร้อย ===")

if __name__ == "__main__":
    app = CookieRunAIApp()
    app.mainloop()
