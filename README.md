# Cookie Run Auto Run AI Bot 🏃‍♂️💨

An intelligent, background-running automated bot for Cookie Run, powered by a customized **YOLOv8 Object Detection model** and Windows Win32 keyboard APIs.

---

## 🛠️ Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/pakanan15953/autorun.git
   cd autorun
   ```

2. **Install Dependencies:**
   Run the following command to install required libraries (make sure you use Python 3.8+):
   ```bash
   pip install opencv-python numpy pywin32 ultralytics
   ```

3. **Add Model Weights:**
   Ensure you copy your trained YOLOv8 weights file named **`best.pt`** and paste it directly into the root folder of this project.

---

## 🎮 How to Run

1. Open your emulator (**MuMu Player**) and launch Cookie Run. 
2. Enter a practice run or standard stage. Keep the emulator window visible (it can be overlapped by other windows but do not minimize it to the Taskbar).
3. Start the bot by running:
   ```bash
   python yolo_bot.py
   ```
4. Use the slider window to adjust the **Trigger Distance**, **Slide Duration**, and **AI Confidence Threshold** in real-time as the bot runs!
