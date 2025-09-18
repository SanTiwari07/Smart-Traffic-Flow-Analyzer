## CEP Dynamic Traffic Signal – YOLO + SORT + ESP32

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Platform](https://img.shields.io/badge/OS-Windows-blue)](https://www.microsoft.com/windows/) [![YOLOv8](https://img.shields.io/badge/YOLOv8-ultralytics-00A67E)](https://github.com/ultralytics/ultralytics)

This project analyzes vehicle density in a polygonal region of a traffic video using YOLOv8 + SORT, dynamically adjusts the green-light duration, and sends timing updates to an ESP32 that drives three LEDs and a 16x2 I²C LCD.

### Key Features
- YOLOv8 + SORT detect/track vehicles inside a masked polygon
- 5s sliding-average density drives dynamic green-time reduction after the first 10s
- Green duration clamped to 30–90 seconds; total time saved is accumulated
- Serial messages to ESP32 control LEDs and LCD countdown display

---

## Table of Contents
- [Quick Start](#quick-start)
- [Repository Structure](#repository-structure)
- [Run with Your Own Video](#run-with-your-own-video)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [ESP32: Wiring & Flashing](#esp32-wiring--flashing)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [License](#license)

---

## Quick Start

Copy–paste these commands on Windows (PowerShell):

```powershell
# 1) Create and activate a virtual environment (optional)
python -m venv myenv
myenv\Scripts\Activate.ps1

# 2) Install requirements
pip install -r requirements.txt

# 3) Set your ESP32 COM port in main.py (e.g., 'COM3')
#    Then run the app
python main.py
```

Controls: Press `q` in the OpenCV window to quit.

Interactive checklist:
- [ ] Place `video.mp4` and `mask.png` in the project root
- [ ] Update `SERIAL_PORT` in `main.py` to your COM port (e.g., `COM3`)
- [ ] Flash the ESP32 with `esp32_traffic_controller.ino`
- [ ] Watch LEDs/LCD reflect dynamic timing

---

## Repository Structure
- `main.py` – Video analytics brain (YOLO + SORT + density + dynamic timing + Serial)
- `esp32_traffic_controller.ino` – ESP32 firmware for LEDs and LCD countdown
- `mask.png` – ROI mask (same size as the video frame after resizing)
- `video.mp4` – Input traffic video
- `yolov8l.pt` / `yolov8n.pt` – YOLO models (`main.py` defaults to `yolov8l.pt`)
- `requirements.txt` – Python dependencies (includes `pyserial`)
- `sort.py` – SORT tracker implementation
- `how_to_do.md` – Expanded ESP32 setup guide

---

## Run with Your Own Video
1) Replace `video.mp4` with your clip, or edit the video path in `main.py`.

2) Update the ROI polygon if needed. In `main.py`, set `polygon_points` to outline your region of interest. A starter `mask.png` is included and auto-resized to the frame.

3) Performance tips:
- Prefer `yolov8n.pt` for lower-end CPUs/GPUs
- Reduce input resolution or process every Nth frame if needed

---

## Configuration

Python (`main.py`):

| Setting | Description | Example |
| --- | --- | --- |
| `SERIAL_PORT` | COM port to ESP32 | `COM3` |
| `SERIAL_BAUD` | Serial baud; must match Arduino code | `115200` |
| `polygon_points` | ROI polygon vertices | list of `(x, y)` |
| Model | Choose model path | `yolov8l.pt` or `yolov8n.pt` |
| Timing init | Yellow/Red during controller init | `DynamicTimingController(yellow_seconds=5, red_seconds=60)` |

ESP32 (`esp32_traffic_controller.ino`):
- LED pins: `PIN_RED`, `PIN_YELLOW`, `PIN_GREEN`
- LCD I²C address: `0x27` (change if needed)

---

## How It Works
1. Python reads frames from `video.mp4`, applies `mask.png`, and runs YOLOv8 detections.
2. SORT tracker stabilizes detections; overlap with the polygon provides a density signal.
3. A 5-second sliding average density is computed.
4. Dynamic green logic:
   - Start at 90s green
   - First 10s: observe only
   - Every 5s: reduce remaining green time by 40% (density < 0.3), by 25% (0.4–0.6), or not at all (≥ 0.7)
   - Clamp green to 30–90s and accumulate time saved
5. On updates/phase changes, Python sends a Serial line to ESP32:

```
GREEN:<g>,RED:<r>,YELLOW:<y>,SAVED:<s>
```

---

## ESP32: Wiring & Flashing

<details>
<summary><strong>Wiring (click to expand)</strong></summary>

### LED Connections
- Red LED anode → ESP32 `GPIO 26` through 220–330 Ω resistor
- Yellow LED anode → ESP32 `GPIO 25` through 220–330 Ω resistor
- Green LED anode → ESP32 `GPIO 33` through 220–330 Ω resistor
- All LED cathodes → GND

Pins used (editable in `esp32_traffic_controller.ino`):
- `PIN_RED = 26`
- `PIN_YELLOW = 25`
- `PIN_GREEN = 33`

### 16x2 I²C LCD
- LCD `VCC` → 5V (or 3.3V if your module supports it)
- LCD `GND` → GND
- LCD `SDA` → ESP32 `GPIO 21`
- LCD `SCL` → ESP32 `GPIO 22`

Default I²C address in code: `0x27`.

If your LCD does not show text, scan the I²C bus and update:

```
LiquidCrystal_I2C lcd(0x27, 16, 2);
```

Power notes:
- ESP32 5V pin can power the LCD backpack; ensure common GND
- Use resistors with LEDs to limit current

</details>

<details>
<summary><strong>Flashing the ESP32 (click to expand)</strong></summary>

1. Open `esp32_traffic_controller.ino` in Arduino IDE (or PlatformIO)
2. Select board (e.g., “ESP32 Dev Module”)
3. Select the correct COM port
4. Upload
5. Start `python main.py` and watch the LCD/LEDs follow the dynamic timing

For a step-by-step, see `how_to_do.md`.

</details>

---

## Troubleshooting

<details>
<summary><strong>LCD issues</strong></summary>

- Nothing on LCD: check SDA/SCL (GPIO 21/22), power, contrast, I²C address
- Garbled text: try the alternate LiquidCrystal I2C library; confirm `(16, 2)`

</details>

<details>
<summary><strong>LEDs/Serial</strong></summary>

- LEDs never change: verify pins/wiring; ensure resistors are present
- Serial conflicts: close Arduino Serial Monitor while running Python; match baud 115200
- Python cannot open port: fix `SERIAL_PORT` in `main.py`, install drivers

</details>

<details>
<summary><strong>Performance/ROI</strong></summary>

- Use `yolov8n.pt` for faster inference
- Lower resolution or skip frames
- Ensure `mask.png` matches frame size (auto-resized in `main.py`)
- Adjust `polygon_points` to match your ROI

</details>

---

## FAQ
**Q:** Can I change rule thresholds?

**A:** Yes—update `DynamicTimingController.maybe_apply_rules` in `main.py`.

**Q:** Does the ESP32 decide timings?

**A:** No. ESP32 enforces and displays timings sent by Python.

**Q:** Can I run without the ESP32?

**A:** Yes. If `pyserial`/port is unavailable, Python will print and skip Serial writes.

**Q:** Where do I see density metrics?

**A:** The OpenCV window overlays density (live and 5s avg), phase, remaining green, and total saved.

---

## License
For academic/educational use. Models (YOLO) are under their respective licenses.

