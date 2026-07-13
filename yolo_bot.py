import cv2
import numpy as np
import time
import random
import ctypes
import win32gui
import win32con
import win32ui
from ultralytics import YOLO

# ----------------- Windows Background Input Configuration -----------------
# Scan codes (DirectInput)
SCAN_SHIFT = 0x2A
SCAN_SPACE = 0x39

# Virtual Key codes
VK_LSHIFT = win32con.VK_LSHIFT
VK_SPACE = win32con.VK_SPACE

def human_press_bg(hwnd, vk_code, scan_code, duration_min=0.05, duration_max=0.12):
    """ส่งสัญญาณกดคีย์บอร์ดเสมือนตรงไปที่หน้าต่างเบื้องหลัง (Background Input)"""
    # lParam สำหรับกดปุ่มลง (KEYDOWN): repeat count = 1, scan code
    lParam_down = 1 | (scan_code << 16)
    # lParam สำหรับปล่อยปุ่ม (KEYUP): repeat count = 1, scan code, transition flags
    lParam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
    
    # กดปุ่มลง
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
    # หน่วงเวลากดค้างให้สมจริงแบบมนุษย์
    hold_time = random.uniform(duration_min, duration_max)
    time.sleep(hold_time)
    # ปล่อยปุ่ม
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)

def nothing(x):
    pass

def capture_window_bg(hwnd):
    """ดึงภาพสกรีนช็อกจากวินโดวส์เป้าหมายเบื้องหลัง แม้จะมีหน้าต่างอื่นบังอยู่"""
    try:
        # ดึงขอบเขตขนาดของหน้าต่างโปรแกรม
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        w = right - left
        h = bot - top
        
        if w <= 0 or h <= 0:
            return None

        # สร้าง Device Contexts สำหรับหน่วยความจำคัดลอกภาพ
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)

        # สั่งดึงภาพจาก Window มาใส่ในเมมโมรี่ DC (ใช้ธง 3 เพื่อดึงเฉพาะภาพของ Client + Render)
        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
        
        # แปลงข้อมูลรูปภาพดิบเป็น Numpy Array
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

        # คืนทรัพยากรเมมโมรี่เพื่อป้องกันการเกิด Memory Leak
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        if result == 1:
            # แปลงสีกราฟิก BGRA ของวินโดวส์เป็น BGR สำหรับ OpenCV
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # ทำการครอบตัด (Crop) หัวข้อเรื่องวินโดวส์ด้านบน (38px) และขอบข้าง (8px) ออก
            # เพื่อให้เหลือเฉพาะหน้าจอตัวเกมเพลย์จริงๆ
            if img_bgr.shape[0] > 50 and img_bgr.shape[1] > 50:
                cropped = img_bgr[38:-8, 8:-8]
                # ย่อ/ขยายรูปภาพที่ครอบแล้วให้เป็น 800x450 พิกเซลอัตโนมัติ เพื่อรักษาพิกัดคงที่สำหรับ AI
                return cv2.resize(cropped, (800, 450))
            return cv2.resize(img_bgr, (800, 450))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงภาพเบื้องหลัง: {e}")
    return None

def main():
    print("=== บอท Cookie Run (โหมดเบื้องหลังไร้สัมผัส Background Mode X) เริ่มทำงาน ===")
    print("ระบบกำลังค้นหาและเชื่อมต่อไปที่หน้าต่าง MuMu Player...")

    # ค้นหาหน้าต่างเกม Android Device-1-1 ของ MuMu Player
    hwnd = win32gui.FindWindow("Qt5156QWindowIcon", "Android Device-1-1")
    if not hwnd:
        hwnd = win32gui.FindWindow(None, "Android Device-1-1")
        
    if not hwnd:
        print("❌ ไม่พบหน้าต่างโปรแกรม 'Android Device-1-1' ของ MuMu Player!")
        print("กรุณาเปิดหน้าต่าง MuMu Player ขึ้นมารอไว้ก่อนเปิดบอทครับ")
        return

    print(f"✅ เชื่อมต่อหน้าต่าง Emulator สำเร็จ! (HWND: {hwnd})")
    print("คุณสามารถนำหน้าต่างอื่น เช่น Chrome, YouTube, Chat หรือโฟลเดอร์งานมาวางบังทับหน้าต่างเกมได้เลย!")
    print("⚠️ ข้อกำหนด: ห้ามย่อหน้าต่างเกมลง Taskbar (Minimize) เท่านั้นครับ\n")

    # โหลดไฟล์สมองกล AI YOLOv8
    model = YOLO("best.pt")

    # สร้างสไลเดอร์จูนระยะห่างและดีเลย์ปุ่ม
    cv2.namedWindow("AI Control & Tuning", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("AI Control & Tuning", 400, 260)
    
    # ดึงค่าเฉลี่ยเริ่มต้นตามที่คุณจูนจังหวะไว้ล่าสุด
    cv2.createTrackbar("Trigger Dist (Px)", "AI Control & Tuning", 140, 400, nothing)
    cv2.createTrackbar("Slide Hold (ms)", "AI Control & Tuning", 810, 1500, nothing)
    cv2.createTrackbar("Conf Thresh (%)", "AI Control & Tuning", 35, 100, nothing)

    last_action_time = 0
    last_random_jump_check_time = 0
    action_cooldown = 0.30  # วินาที (ปรับลดให้บอทกระโดด/สไลด์ต่อเนื่องได้ไวขึ้น)
    current_status = "RUNNING"
    
    # พิกัดแนวหน้าคุกกี้ที่คงที่สำหรับการคำนวณความเสถียรแนวราบ
    FALLBACK_COOKIE_X = 220

    while True:
        start_time = time.time()

        # อ่านค่าจากสไลเดอร์สดๆ บนหน้าจอ
        trigger_dist = cv2.getTrackbarPos("Trigger Dist (Px)", "AI Control & Tuning")
        conf_val = cv2.getTrackbarPos("Conf Thresh (%)", "AI Control & Tuning") / 100.0
        slide_hold_ms = cv2.getTrackbarPos("Slide Hold (ms)", "AI Control & Tuning")

        # 1. แคปภาพเบื้องหลังหน้าต่าง MuMu
        frame = capture_window_bg(hwnd)
        if frame is None:
            print("⚠️ ดึงภาพหน้าจอไม่ได้ชั่วคราว (กรุณาเช็คว่าหน้าต่างย่อลง Taskbar หรือไม่?)")
            time.sleep(0.1)
            continue

        # 2. ส่งให้ AI YOLOv8 ประมวลผลหาคุกกี้และสิ่งกีดขวางทั่วหน้าจอ
        results = model(frame, conf=conf_val, verbose=False)

        found_jump_obstacle = False
        found_double_jump_obstacle = False
        found_slide_obstacle = False
        
        cookie_box = None
        detected_objects = []

        # วนลูปเก็บวัตถุที่ตรวจเจอจากโมเดล
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                score = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                class_name = model.names[cls].lower()
                
                detected_objects.append((int(x1), int(y1), int(x2), int(y2), class_name, score))
                
                # ค้นหาตำแหน่งคุกกี้เพื่อใช้วาดจุด
                if class_name == "cookie":
                    cookie_box = (int(x1), int(y1), int(x2), int(y2))

        # 3. กำหนดพิกัดอ้างอิงของตัวคุกกี้แนวราบที่คงที่ (220px)
        cookie_front_x = FALLBACK_COOKIE_X
        
        # วาดวงกลมสีเขียวที่จุดอ้างอิงเป็นไกด์ไลน์บอกระยะหน้ารถ
        if cookie_box is not None:
            cv2.circle(frame, (cookie_front_x, int((cookie_box[1] + cookie_box[3])/2)), 6, (0, 255, 0), -1)
        else:
            cv2.circle(frame, (cookie_front_x, 250), 6, (0, 255, 0), -1)

        # 4. ค้นหาสิ่งกีดขวางแนวราบที่อยู่หน้าคุกกี้เพื่อวัดระยะห่าง
        jump_obstacles = []
        slide_obstacles = []
        closest_obstacle_info = None
        closest_obstacle_distance = 9999

        for x1, y1, x2, y2, c_name, conf in detected_objects:
            if x1 > cookie_front_x:
                distance = x1 - cookie_front_x
                if distance < 400: # สแกนล่วงหน้าแนวราบไม่เกิน 400 พิกเซล
                    if c_name in ["jump_obs", "jump_potato", "double_jump_obs", "raised_floor", "coin"]:
                        jump_obstacles.append((int(x1), int(x2), int(y1), int(y2), c_name, distance))
                    elif c_name == "slide_obs":
                        slide_obstacles.append((int(x1), int(x2), int(y1), int(y2), c_name, distance))
                    
                    # หาตัวที่เข้าใกล้แนวคุกกี้มากที่สุด
                    if distance < closest_obstacle_distance:
                        closest_obstacle_distance = distance
                        closest_obstacle_info = (int(x1), int(y1), int(x2), int(y2), c_name, distance)

        # เรียงอุปสรรคตามระยะทาง
        jump_obstacles.sort(key=lambda o: o[5])
        slide_obstacles.sort(key=lambda o: o[5])

        # 5. วิเคราะห์พฤติกรรมการกระโดดแบบฉลาดและวัดระยะห่าง
        if closest_obstacle_info is not None:
            obs_x1, obs_y1, obs_x2, obs_y2, obs_name, dist = closest_obstacle_info
            
            # ลากเส้นบอกระยะสด (Lidar Line)
            line_color = (0, 0, 255) if dist <= trigger_dist else (255, 0, 0)
            cookie_center_y = cookie_box[1] + int((cookie_box[3]-cookie_box[1])/2) if cookie_box else 250
            obs_center_y = obs_y1 + int((obs_y2-obs_y1)/2)
            
            cv2.line(frame, (cookie_front_x, cookie_center_y), (obs_x1, obs_center_y), line_color, 2)
            cv2.putText(frame, f"Dist: {int(dist)}px", (int((cookie_front_x + obs_x1)/2), int((cookie_center_y + obs_center_y)/2) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, line_color, 2)

            # ตรวจสอบข้ามพิกเซนเซอร์
            if dist <= trigger_dist:
                # ตรวจสอบปุ่มโดด
                if obs_name in ["jump_obs", "jump_potato", "double_jump_obs", "raised_floor", "coin"]:
                    is_double_jump = False
                    
                    # เป็นสิ่งกีดขวางดับเบิ้ลจัมพ์โดยตรง
                    if obs_name == "double_jump_obs":
                        is_double_jump = True
                    # หรือเจอกลุ่มอุปสรรคกระโดดสองชิ้นวางติดชิดกันมากๆ
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
                        
                # ตรวจสอบปุ่มหมอบ
                elif obs_name == "slide_obs":
                    found_slide_obstacle = True

        # 5.5 ระบบตรวจจับขอบเหวอัจฉริยะ (Cliff Detection)
        # ตรวจสอบขอบขวาของพื้นดินที่คุกกี้กำลังเหยียบอยู่ เพื่อหลบหลุมตกเหวโดยไม่จำเป็นต้องมีสิ่งกีดขวาง
        ground_boxes = []
        for x1, y1, x2, y2, c_name, conf in detected_objects:
            if c_name == "ground":
                ground_boxes.append((x1, x2, y1, y2))

        for x1, x2, y1, y2 in ground_boxes:
            # ตรวจจับแผ่นพื้นดินที่คุกกี้กำลังวิ่งอยู่ (ครอบคลุมพิกัดแนววิ่งของคุกกี้ที่ X=180 ถึง X=220)
            if x1 <= 220 and x2 >= 180:
                dist_to_cliff = x2 - cookie_front_x
                
                # ถ้าแผ่นพื้นดินกำลังจะสิ้นสุดในอีก 10 ถึง 130 พิกเซลข้างหน้า (แสดงว่ากำลังจะตกหลุม)
                if 10 < dist_to_cliff <= 130:
                    # ตรวจสอบว่ามีพื้นแผ่นอื่นมารองรับต่อกันทันทีไหม (ห่างกันไม่เกิน 45px)
                    has_continuation = False
                    for nx1, nx2, ny1, ny2 in ground_boxes:
                        if 0 <= (nx1 - x2) < 45:
                            has_continuation = True
                            break
                    
                    # ตรวจสอบว่ามี raised_floor มารองรับต่อกันไหม
                    for rx1, ry1, rx2, ry2, rc_name, rconf in detected_objects:
                        if rc_name == "raised_floor":
                            if 0 <= (rx1 - x2) < 45:
                                            has_continuation = True
                                            break
                                
                    if not has_continuation:
                        found_jump_obstacle = True
                        print(f"[{time.strftime('%H:%M:%S')}] เรดาร์เตือน: ตรวจพบขอบเหวห่างออกไป {int(dist_to_cliff)}px -> สั่งกระโดดหลบเหว!")
                        
                        # วาดเส้นแจ้งเตือนขอบเหวสีส้มบนจอดีบัก
                        cv2.line(frame, (x2, y1), (x2, y2), (0, 165, 255), 3)
                        cv2.putText(frame, "CLIFF!", (x2, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                        break

        # 5.8 สุ่มกระโดดเล่นแก้เซ็งแบบมนุษย์ (สุ่มโอกาส 2% ทุกๆ 1 วินาทีที่พื้นโล่งและไม่มีสิ่งกีดขวาง)
        found_random_jump = False
        if closest_obstacle_info is None and not found_jump_obstacle and not found_double_jump_obstacle and not found_slide_obstacle:
            if now - last_random_jump_check_time > 1.0:
                last_random_jump_check_time = now
                if random.random() < 0.02:
                    found_random_jump = True

        # 6. ลอจิกจำลองคีย์บอร์ดแบบเบื้องหลัง (Background Keyboard Event)
        now = time.time()
        if now - last_action_time > action_cooldown:
            # 1. ดับเบิ้ลจัมพ์
            if found_double_jump_obstacle:
                current_status = "DOUBLE_JUMP"
                time.sleep(random.uniform(0.01, 0.03))
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> ดับเบิ้ลจัมพ์ (สิ่งกีดขวางระยะ {closest_obstacle_distance}px)")
                
                # กดกระโดดครั้งที่ 1
                win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, (SCAN_SHIFT << 16) | 1)
                time.sleep(random.uniform(0.05, 0.08))
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, VK_LSHIFT, (SCAN_SHIFT << 16) | 1 | (1 << 30) | (1 << 31))
                
                # หน่วงจอยลอยฟ้าก่อนกดครั้งที่สอง
                time.sleep(random.uniform(0.16, 0.22))
                
                # กดกระโดดครั้งที่ 2
                win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_LSHIFT, (SCAN_SHIFT << 16) | 1)
                time.sleep(random.uniform(0.05, 0.08))
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, VK_LSHIFT, (SCAN_SHIFT << 16) | 1 | (1 << 30) | (1 << 31))
                
                last_action_time = time.time()
                
            # 2. กระโดดปกติ (หลบอุปสรรค/ขอบเหว หรือ สุ่มโดดเล่นแบบมนุษย์)
            elif found_jump_obstacle or found_random_jump:
                current_status = "JUMPING" if found_jump_obstacle else "RANDOM_JUMP"
                time.sleep(random.uniform(0.01, 0.03))
                if found_random_jump:
                    print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> สุ่มกระโดดเล่นแก้เซ็ง (2% Chance)")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> กระโดด (สิ่งกีดขวางระยะ {closest_obstacle_distance}px)")
                
                # จำลองการกดแบบเบื้องหลัง
                slide_duration = random.uniform(0.06, 0.10)
                human_press_bg(hwnd, VK_LSHIFT, SCAN_SHIFT, duration_min=slide_duration * 0.95, duration_max=slide_duration * 1.05)
                last_action_time = time.time()
                
            # 3. หมอบ/สไลด์
            elif found_slide_obstacle:
                current_status = "SLIDING"
                time.sleep(random.uniform(0.01, 0.03))
                print(f"[{time.strftime('%H:%M:%S')}] เบื้องหลัง -> หมอบสไลด์ (สิ่งกีดขวางระยะ {closest_obstacle_distance}px)")
                
                # ปรับตามค่าสไลเดอร์บวกสุ่มจังหวะแบบมนุษย์
                slide_duration = slide_hold_ms / 1000.0
                human_press_bg(hwnd, VK_SPACE, SCAN_SPACE, duration_min=slide_duration * 0.95, duration_max=slide_duration * 1.05)
                last_action_time = time.time()
            else:
                current_status = "RUNNING"

        # 7. วาดผลลัพธ์การสแกนรอบจอบนเฟรมดีบักเกอร์
        for x1, y1, x2, y2, c_name, conf in detected_objects:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{c_name} ({conf*100:.0f}%)", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # คำนวณความเร็วเฟรมและแสดงผลสถานะบนหน้าต่างแยก
        fps = 1.0 / (time.time() - start_time)
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"AI STATUS: {current_status}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"Radar Dist: {int(closest_obstacle_distance)} px / Trigger: {trigger_dist} px", 
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        cv2.imshow("Bot Vision (YOLOv8 AI Background Mode)", frame)

        # กด 'q' เพื่อหยุดทำงาน
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("=== ปิดการทำงานบอทเรียบร้อย ===")

if __name__ == "__main__":
    main()
