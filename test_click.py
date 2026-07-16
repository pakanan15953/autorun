import win32gui
import win32con
import time

def get_mumu_hwnd():
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
    return hwnd

def test():
    parent_hwnd = get_mumu_hwnd()
    if not parent_hwnd:
        print("❌ Could not find MuMu Player window")
        return
        
    children = []
    def cb(hwnd, extra):
        children.append(hwnd)
        return True
    win32gui.EnumChildWindows(parent_hwnd, cb, None)
    
    # We found children. Usually Child [1] (nemudisplay) or Child [0] is the target.
    # Let's test on BOTH child windows with different message combinations.
    
    x_norm, y_norm = 282, 390
    
    print("--- Starting Detailed Click Methods Test ---")
    print("We will try 4 different click methods on each child window.")
    print("Please watch the game screen to see if any method clicks the 'OK' button!\n")
    
    for idx, hwnd in enumerate(children):
        classname = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        _, _, w, h = win32gui.GetClientRect(hwnd)
        
        print(f"==========================================")
        print(f"Testing HWND: {hwnd} | Class: '{classname}' | Title: '{title}' ({w}x{h})")
        print(f"==========================================")
        
        x = int(x_norm * (w / 800.0))
        y = int(y_norm * (h / 450.0))
        lParam = (y << 16) | (x & 0xFFFF)
        
        # Method 1: Send Message (Synchronous) instead of Post Message
        print(f"👉 [Method 1] SendMessage WM_LBUTTONDOWN/UP to HWND {hwnd}...")
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(0.1)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        time.sleep(3.0)
        
        # Method 2: Mouse Move first, then Click
        print(f"👉 [Method 2] PostMessage WM_MOUSEMOVE then Click to HWND {hwnd}...")
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(0.1)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        time.sleep(3.0)
        
        # Method 3: Click with WM_ACTIVATE first (Activate client)
        print(f"👉 [Method 3] Send WM_ACTIVATE then Click to HWND {hwnd}...")
        # 1 = WA_ACTIVE
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, 1, 0) 
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(0.1)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        time.sleep(3.0)

        # Method 4: Double Click message
        print(f"👉 [Method 4] Send WM_LBUTTONDBLCLK to HWND {hwnd}...")
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, lParam)
        time.sleep(0.1)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        time.sleep(3.0)

    print("\nDetailed Test completed!")

if __name__ == "__main__":
    test()
