import cv2

def find_template_match(hwnd, frame, template_img, threshold=0.75):
    """ค้นหาตำแหน่งรูปภาพต้นแบบในเฟรมหน้าจอ คืนค่า (พบหรือไม่, พิกัด X, พิกัด Y) เทียบกับสเกล 800x450"""
    if template_img is None or hwnd is None or frame is None:
        return False, 0, 0
    try:
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_frame, template_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= threshold:
            h, w = template_img.shape[:2]
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return True, cx, cy
    except Exception as e:
        pass
    return False, 0, 0
