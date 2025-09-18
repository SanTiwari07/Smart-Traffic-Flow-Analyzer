## CEP Dynamic Traffic Signal – YOLO + SORT + ESP32

This project calculates vehicle density in a polygonal region of a traffic video using YOLOv8 + SORT, dynamically adjusts the green-light duration based on density, and sends timing updates to an ESP32. The ESP32 controls three LEDs (Red/Yellow/Green) and a 16x2 I2C LCD to display the active light, countdown, and total time saved.

### Key Features
- YOLOv8 + SORT detect/track vehicles in a masked polygon region
- 5s sliding-average density drives dynamic green-time reduction after an initial 10s window
- Green duration bounded to 30–90 seconds; total time saved is accumulated
- Serial messages to ESP32 control LEDs and LCD countdown display

---

## Repository Structure
- `main.py` – Video analytics brain (YOLO + SORT + density + dynamic timing + Serial)
- `esp32_traffic_controller.ino` – ESP32 firmware for LEDs and LCD countdown
- `mask.png` – Region of interest mask (same size as the video frame after resizing)
- `video.mp4` – Input traffic video
- `yolov8l.pt` / `yolov8n.pt` – YOLO models (you can choose one; `main.py` uses `yolov8l.pt`)
- `requirements.txt` – Python dependencies (includes `pyserial`)
- `sort.py` – SORT tracker implementation

---

## Hardware Required
- ESP32 Dev Board (e.g., ESP32-DevKitC, NodeMCU-32S)
- 3× LEDs (Red, Yellow, Green) + 3× resistors (220–330 Ω)
- 16x2 LCD with I2C backpack (typical address `0x27`)
- Breadboard + jumper wires
- USB cable for ESP32

---

## Wiring (ESP32)

### LED Connections
- Red LED anode → ESP32 `GPIO 26` through 220–330 Ω resistor
- Yellow LED anode → ESP32 `GPIO 25` through 220–330 Ω resistor
- Green LED anode → ESP32 `GPIO 33` through 220–330 Ω resistor
- All LED cathodes → GND

Pins used (changeable in `esp32_traffic_controller.ino`):
- `PIN_RED = 26`
- `PIN_YELLOW = 25`
- `PIN_GREEN = 33`

### 16x2 I²C LCD
- LCD `VCC` → 5V (or 3.3V if your module supports it)
- LCD `GND` → GND
- LCD `SDA` → ESP32 `GPIO 21`
- LCD `SCL` → ESP32 `GPIO 22`

Default I²C address in code: `0x27`.

If your LCD does not show text, scan the I²C bus (e.g., with an Arduino I2C scanner sketch) and update the address in:
```
LiquidCrystal_I2C lcd(0x27, 16, 2);
```

Power notes:
- ESP32 5V pin can power the LCD backpack; ensure common GND between ESP32 and peripherals.
- Do not exceed ESP32 GPIO current limits; use resistors with LEDs.

---

## How the System Works
1. Python reads frames from `video.mp4`, applies `mask.png` and runs YOLOv8 detections.
2. SORT tracker stabilizes detections; intersection area between tracked boxes and polygon gives density.
3. A 5-second sliding average density is computed continuously.
4. Dynamic green logic:
   - Start green at 90s.
   - First 10s: no change, only measure density.
   - Every 5s thereafter:
     - If density < 0.3 → reduce remaining green time by 40%.
     - If 0.4 ≤ density ≤ 0.6 → reduce remaining green time by 25%.
     - If density ≥ 0.7 → no reduction.
   - Clamp total green between 30–90s.
   - After RED ends, add (90 − actual_green) to total saved.
5. Python sends timing to ESP32 via Serial whenever green changes, and on each phase change.
6. ESP32 drives LEDs and shows countdown + total saved on LCD.

Serial message format (one line, newline-terminated):
```
GREEN:<g>,RED:<r>,YELLOW:<y>,SAVED:<s>
```
Where `<g>`, `<r>`, `<y>`, `<s>` are integer seconds.

---

## Software Setup (Windows, venv recommended)
1. Create/activate venv (optional but recommended):
```
python -m venv myenv
myenv\Scripts\activate
```
2. Install requirements:
```
pip install -r requirements.txt
```
3. Place `video.mp4` and `mask.png` in the project root (already present). Ensure the path in `main.py` points to your video.
4. Connect the ESP32 via USB. Find its COM port in Device Manager (e.g., `COM3`).
5. In `main.py`, set:
```
SERIAL_PORT = 'COM3'
```
6. Run Python:
```
python main.py
```
Press `q` in the OpenCV window to quit.

---

## Flashing the ESP32
1. Open `esp32_traffic_controller.ino` in the Arduino IDE (or PlatformIO).
2. Board: select your ESP32 variant (e.g., “ESP32 Dev Module”).
3. Port: select the COM port identified earlier.
4. Upload the sketch.
5. With the ESP32 running, start `main.py`. It will send timing lines over Serial.

LCD should show the phase and countdown; LEDs will match the phase.

---

## Configuration
Python (`main.py`):
- `SERIAL_PORT` – COM port to ESP32 (e.g., `COM3`).
- `SERIAL_BAUD` – default 115200; must match Arduino code.
- `polygon_points` – edit to change ROI polygon.
- `yolov8l.pt` – switch to `yolov8n.pt` for speed if needed.
- Yellow and Red durations for controller initialization: `DynamicTimingController(yellow_seconds=5, red_seconds=60)`.

ESP32 (`esp32_traffic_controller.ino`):
- LED pins: `PIN_RED`, `PIN_YELLOW`, `PIN_GREEN`.
- LCD I2C address: `0x27` (change if needed).

---

## Troubleshooting
- No LCD text:
  - Verify SDA/SCL wiring (GPIO 21/22), power, contrast pot on backpack.
  - Scan I²C address and update `0x27` if different.
- LEDs never change:
  - Check pin numbers and wiring; ensure resistors are used.
  - Serial baud mismatch (set both Python and ESP32 to 115200).
- Python cannot open serial port:
  - Update `SERIAL_PORT` in `main.py`.
  - Close any serial monitor in Arduino IDE while Python runs.
- YOLO performance too slow:
  - Use `yolov8n.pt` instead of `yolov8l.pt`.
  - Lower input resolution or skip frames.
- Mask/ROI misaligned:
  - Ensure `mask.png` gets resized to the video’s frame size (handled in `main.py`).
  - Adjust `polygon_points` to match your region of interest.

---

## FAQ
**Q:** Can I change the rule thresholds?  
**A:** Yes. Update the logic in `DynamicTimingController.maybe_apply_rules` in `main.py`.

**Q:** Does ESP32 decide timings?  
**A:** No. ESP32 only displays and enforces the countdown sent by Python.

**Q:** Can I run without the ESP32?  
**A:** Yes. If `pyserial` or the port is unavailable, Python will print messages and skip writing to Serial.

**Q:** Where do I see density metrics?  
**A:** The OpenCV window overlays live density, 5s average, phase, remaining green, and total saved.

---

## License
For academic/educational use. Models (YOLO) are under their respective licenses.


# Smart-Traffic-Flow-Analyzer
