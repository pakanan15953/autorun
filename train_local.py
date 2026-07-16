import os
import zipfile
import urllib.request
from ultralytics import YOLO

# พิกัดโฟลเดอร์ Dataset ที่คุณดาวน์โหลดมา
extract_path = "Cookie Run Auto Run.v2-model6-full.yolov8"

def main():
    print("=== เริ่มกระบวนการตรวจสอบและเทรนบอท YOLOv8 แบบโลคอล ===")
    
    # 1-2. ตรวจสอบโฟลเดอร์รูปภาพ
    if not os.path.exists(extract_path):
        print(f"❌ ไม่พบโฟลเดอร์ Dataset ที่: {os.path.abspath(extract_path)}")
        print("กรุณาตรวจสอบว่าคุณแตกไฟล์ Dataset ไว้ที่โฟลเดอร์นี้ถูกต้องแล้ว")
        return
    else:
        print(f"✔️ ตรวจพบโฟลเดอร์ข้อมูล '{extract_path}'")

    # 3. แก้ไขไฟล์ data.yaml ให้เป็น Absolute Path เพื่อไม่ให้ YOLO แจ้งเตือนหาภาพไม่เจอ
    yaml_file = os.path.join(extract_path, "data.yaml")
    if os.path.exists(yaml_file):
        print("\n3. 🔧 กำลังปรับจูนไฟล์ตั้งค่า data.yaml ให้ตรงกับเครื่องคอมพิวเตอร์ของคุณ...")
        
        # อ่านไฟล์เดิม
        with open(yaml_file, "r") as f:
            lines = f.readlines()
        
        new_lines = []
        # เขียน absolute path ไปที่บรรทัดแรกสุด
        new_lines.append(f"path: {os.path.abspath(extract_path)}\n")
        
        for line in lines:
            # ข้ามบรรทัด path เดิม (ถ้ามี)
            if line.startswith("path:"):
                continue
            # ลบ ../ ออกเพื่อให้ไปหาที่ absolute path ที่ตั้งไว้ในบรรทัดแรก
            elif line.strip().startswith("train:"):
                new_lines.append("train: train/images\n")
            elif line.strip().startswith("val:"):
                new_lines.append("val: valid/images\n")
            elif line.strip().startswith("test:"):
                new_lines.append("test: test/images\n")
            else:
                new_lines.append(line)
                
        with open(yaml_file, "w") as f:
            f.writelines(new_lines)
            
        print("✔️ แก้ไขและปรับปรุง data.yaml เรียบร้อย!")
        # พิมพ์ตัวอย่างไฟล์ yaml หลังแก้ไข
        print("-" * 40)
        with open(yaml_file, "r") as f:
            print(f.read().strip())
        print("-" * 40)
    else:
        print(f"❌ ไม่พบไฟล์ data.yaml ใน: {yaml_file}")
        return

    # 4. เริ่มต้นรันเทรนโมเดล YOLOv8
    print("\n4. 🏋️ เริ่มการเทรนปัญญาประดิษฐ์ YOLOv8 บนเครื่องคอมพิวเตอร์ของคุณ...")
    print("ระบบจะตรวจหาการ์ดจอแยก RTX 3050 Notebook ของคุณและใช้เทรนโดยอัตโนมัติ")
    print("กด Ctrl+C เพื่อหยุดก่อนกำหนดหากต้องการ\n")
    
    try:
        # ใช้โมเดล 'best.pt' ของเดิมที่เราเทรนมาเป็นตัวตั้งต้นในการเรียนรู้เพิ่มเติม (Fine-Tuning)
        model = YOLO("best.pt")
        # เริ่มการเทรน 50 รอบ ขนาดภาพความละเอียด 640 พิกเซล
        model.train(data=os.path.abspath(yaml_file), epochs=50, imgsz=640)
        
        print("\n🎉 ยินดีด้วย! การฝึกสอนบอท AI สำเร็จเรียบร้อย!")
        print("ไฟล์สมองกลเซฟอยู่ที่: runs/detect/train/weights/best.pt")
        print("กรุณาคัดลอกไฟล์ 'best.pt' ไปไว้ที่หน้าหลักเพื่อรันใช้งานคู่กับ 'yolo_bot.py'")
    except Exception as e:
        print(f"❌ การเทรนโมเดลขัดข้อง: {e}")

if __name__ == "__main__":
    main()
