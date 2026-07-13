import cv2
import numpy as np
import mss
import time
import random
import ctypes
import os

# ----------------- Hardware Input Simulation (DirectInput) -----------------
KEY_JUMP = 0x2A  # ปุ่ม Left Shift
KEY_SLIDE = 0x39 # ปุ่ม Spacebar

PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

def press_key(hex_key_code):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hex_key_code, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key(hex_key_code):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hex_key_code, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def human_press(hex_key_code, duration_min=0.05, duration_max=0.12):
    press_key(hex_key_code)
    hold_time = random.uniform(duration_min, duration_max)
    time.sleep(hold_time)
    release_key(hex_key_code)

# ----------------- OpenCV Helper Functions -----------------
def nothing(x):
    pass

JUMP_PATH = "templates/jump"
SLIDE_PATH = "templates/slide"
os.makedirs(JUMP_PATH, exist_ok=True)
os.makedirs(SLIDE_PATH, exist_ok=True)

def load_templates():
    jump_templates = []
    slide_templates = []
    
    for file in os.listdir(JUMP_PATH):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            img = cv2.imread(os.path.join(JUMP_PATH, file), 0)
            if img is not None:
                jump_templates.append((file, img))
                
    for file in os.listdir(SLIDE_PATH):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            img = cv2.imread(os.path.join(SLIDE_PATH, file), 0)
            if img is not None:
                slide_templates.append((file, img))
                
    print(f"📥 โหลดภาพเทมเพลตเรียบร้อย: กระโดด {len(jump_templates)} ภาพ | สไลด์ {len(slide_templates)} ภาพ")
    return jump_templates, slide_templates

def match_templates_in_roi(roi_gray, templates, threshold_val):
    """รัน Template Matching คืนค่าสถานะพิกเซลตำแหน่งที่พบ"""
    best_max_val = 0
    best_max_loc = None
    best_template_shape = None
    best_name = None
    
    threshold = threshold_val / 100.0

    for name, template in templates:
        t_h, t_w = template.shape[:2]
        if roi_gray.shape[0] < t_h or roi_gray.shape[1] < t_w:
            continue
            
        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val > best_max_val:
            best_max_val = max_val
            best_max_loc = max_loc
            best_template_shape = (t_w, t_h)
            best_name = name
            
    if best_max_val >= threshold:
        return True, best_max_val, best_max_loc, best_template_shape, best_name
    return False, best_max_val, None, None, None

# พิกัดกรอบดึงภาพหน้าจอเกมหลัก
monitor = {
    "top": 200,
    "left": 100,
    "width": 800,
    "height": 450
}

def main():
    print("=== บอท Cookie Run (โหมดเส้นตรวจจับอัจฉริยะ Trigger Line) เริ่มทำงาน ===")
    print("วิธีปรับแต่งจังหวะหลบ:")
    print("- ลากแถบ 'Trigger Line X' (เส้นสีแดง):")
    print("  - ลากไปขวา (เช่น 450) = บอทจะตัดสินใจ 'หลบเร็วขึ้น' (เหมาะกับด่านวิ่งเร็ว)")
    print("  - ลากไปซ้าย (เช่น 350) = บอทจะตัดสินใจ 'หลบช้าลง'")
    print("กด 'r' เพื่อรีโหลดภาพเทมเพลตใหม่ | กด 'q' เพื่อหยุดทำงาน\n")

    # โหลดรูปภาพเทมเพลต
    jump_templates, slide_templates = load_templates()

    # สร้างแผงควบคุมสไลเดอร์แบบย่อ (เข้าใจง่ายขึ้นมาก)
    cv2.namedWindow("Bot Control & Tuning", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Bot Control & Tuning", 400, 200)

    # จุดเริ่มต้นสแกนแกน X (หลบหลังคุกกี้เพื่อไม่ให้บอทสแกนโดนตัวคุกกี้เอง)
    # สมมติคุกกี้จมึกอยู่ที่ X = 200 เราจะตั้งค่านี้ไว้ตายตัวในโปรแกรม
    cookie_x_end = 220
    
    # สไลเดอร์ปรับตำแหน่งเส้นแจ้งเตือน (สีแดง)
    cv2.createTrackbar("Trigger Line X", "Bot Control & Tuning", 420, 800, nothing)
    cv2.createTrackbar("Match Thresh (%)", "Bot Control & Tuning", 75, 100, nothing)

    last_action_time = 0
    action_cooldown = 0.55  # วินาที
    current_status = "RUNNING"

    with mss.mss() as sct:
        while True:
            start_time = time.time()

            # อ่านค่าสไลเดอร์
            trigger_line = cv2.getTrackbarPos("Trigger Line X", "Bot Control & Tuning")
            match_thresh = cv2.getTrackbarPos("Match Thresh (%)", "Bot Control & Tuning")

            # ควบคุมไม่ให้เส้นทริกเกอร์อยู่ด้านหลังคุกกี้
            if trigger_line <= cookie_x_end:
                trigger_line = cookie_x_end + 10

            # 1. ดึงภาพหน้าจอเกม
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # กำหนดพื้นที่ค้นหา (ความสูงครอบคลุมทั้งเลน 50 ถึง 400, ความกว้างตั้งแต่หลังคุกกี้ไปจนถึงเส้นทริกเกอร์สีแดง)
            y_scan_start = 50
            y_scan_end = 400
            
            roi_scan = gray[y_scan_start:y_scan_end, cookie_x_end:trigger_line]

            # 2. ค้นหาสิ่งกีดขวางในพื้นที่อันตราย (ระหว่างคุกกี้กับเส้นแดง)
            found_jump, jump_score, jump_loc, jump_shape, jump_name = match_templates_in_roi(
                roi_scan, jump_templates, match_thresh
            )
            
            found_slide, slide_score, slide_loc, slide_shape, slide_name = match_templates_in_roi(
                roi_scan, slide_templates, match_thresh
            )

            # 3. ลอจิกสั่งงาน
            now = time.time()
            if now - last_action_time > action_cooldown:
                if found_jump:
                    current_status = "JUMPING"
                    time.sleep(random.uniform(0.01, 0.03))
                    print(f"[{time.strftime('%H:%M:%S')}] ตรวจเจอสิ่งกีดขวางบนพื้น: {jump_name} ในโซนทริกเกอร์! -> กระโดด!")
                    human_press(KEY_JUMP, duration_min=0.06, duration_max=0.10)
                    last_action_time = time.time()

                elif found_slide:
                    current_status = "SLIDING"
                    time.sleep(random.uniform(0.01, 0.03))
                    print(f"[{time.strftime('%H:%M:%S')}] ตรวจเจอสิ่งกีดขวางลอยฟ้า: {slide_name} ในโซนทริกเกอร์! -> สไลด์!")
                    human_press(KEY_SLIDE, duration_min=0.45, duration_max=0.60)
                    last_action_time = time.time()
                
                else:
                    current_status = "RUNNING"

            # 4. วาดเส้นและพื้นที่เซนเซอร์บนภาพ Debug
            # วาดเส้นสีเขียว (หลังคุกกี้)
            cv2.line(frame, (cookie_x_end, y_scan_start), (cookie_x_end, y_scan_end), (0, 255, 0), 2)
            # วาดเส้นสีแดง (Trigger Line)
            cv2.line(frame, (trigger_line, y_scan_start), (trigger_line, y_scan_end), (0, 0, 255), 2)
            
            # ระบายสีพื้นหลังโซนสแกนจางๆ เพื่อให้ผู้ใช้มองเห็นพื้นที่สแกน
            overlay = frame.copy()
            cv2.rectangle(overlay, (cookie_x_end, y_scan_start), (trigger_line, y_scan_end), (255, 0, 0), -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

            # 5. วาดกรอบสี่เหลี่ยมสีเขียวรอบสิ่งกีดขวางที่ตรวจจับได้ในโซน
            if found_jump and jump_loc is not None:
                # แปลงพิกัดสัมพัทธ์ใน ROI กลับมาเป็นพิกัดภาพหลัก
                obj_x = cookie_x_end + jump_loc[0]
                obj_y = y_scan_start + jump_loc[1]
                t_w, t_h = jump_shape
                cv2.rectangle(frame, (obj_x, obj_y), (obj_x + t_w, obj_y + t_h), (0, 255, 0), 3)
                cv2.putText(frame, f"JUMP OBSTACLE ({jump_score*100:.0f}%)", 
                            (obj_x, obj_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if found_slide and slide_loc is not None:
                obj_x = cookie_x_end + slide_loc[0]
                obj_y = y_scan_start + slide_loc[1]
                t_w, t_h = slide_shape
                cv2.rectangle(frame, (obj_x, obj_y), (obj_x + t_w, obj_y + t_h), (0, 255, 0), 3)
                cv2.putText(frame, f"SLIDE OBSTACLE ({slide_score*100:.0f}%)", 
                            (obj_x, obj_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # แสดงสถานะปัจจุบัน
            fps = 1.0 / (time.time() - start_time)
            cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"STATUS: {current_status}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(frame, f"Templates: Jump={len(jump_templates)} | Slide={len(slide_templates)}", 
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow("Bot Vision (Original & Scanning Zones)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("\n🔄 รีโหลดรูปภาพเทมเพลตใหม่...")
                jump_templates, slide_templates = load_templates()

    cv2.destroyAllWindows()
    print("=== บอทปิดการทำงานเรียบร้อย ===")

if __name__ == "__main__":
    main()
