# CEP Dynamic Traffic Signal – YOLO + SORT + ESP32

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/OS-Windows-blue)](https://www.microsoft.com/windows/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ultralytics-00A67E)](https://github.com/ultralytics/ultralytics)

## Overview

### The Problem
Conventional traffic signals often run fixed-time plans and are not responsive to real-time vehicle load. This can cause long waits on low-demand approaches and wasted green time, reducing throughput and increasing congestion.

### Our Approach
We use OpenCV + YOLOv8 to detect and track vehicles inside a region of interest (ROI). A short sliding-window density signal drives a dynamic timing controller that reduces the remaining green phase when demand is low, within safe bounds. Per-second countdown updates are sent to an ESP32 over TCP for display/LED control.

### Key Features
- **YOLOv8 + SORT**: Detect and track vehicles inside an ROI (masked polygon)
- **Dynamic Timing**: 5-second sliding-average density adjusts remaining green time after the first 10 seconds
- **Safe Bounds**: Green is clamped between 30–90 seconds and total time saved is accumulated
- **Real-time Updates**: Per-second A/B/C TCP messages to ESP32 for live display with optional Serial sync

---

## Table of Contents
- [Repository Structure](#repository-structure)
- [Setup and Run](#setup-and-run)
- [Configure Inputs and ROI](#configure-inputs-and-roi)
- [How It Works](#how-it-works)
- [ESP32: Wiring & TCP](#esp32-wiring--tcp)
- [Troubleshooting](#troubleshooting)
- [Images](#images)
- [Video](#video)
- [Future Scope](#future-scope)
- [License](#license)
- [Contributing](#contributing)
- [Contact](#contact)

---

## Repository Structure

```
CEP_Dynamic_Traffic_Signal/
├── main.py                          # Main video analytics + timing controller
├── sort.py                          # SORT tracker implementation
├── mask.png                         # ROI mask (auto-resized to frame size)
├── video.mp4                        # Sample/input traffic video
├── yolov8l.pt / yolov8n.pt         # YOLO models (defaults to yolov8l.pt)
├── requirements.txt                 # Python dependencies
├── env.sample                       # Copy to .env for environment overrides
├── esp32_traffic_controller/
│   └── tcp_test_sender.py          # TCP tester for A/B/C messages
└── future_scope/
    ├── config.json                  # Runtime configuration (edit this)
    ├── config.example.json          # Configuration template
    ├── config_loader.py             # Configuration loader helper
    └── README.md                    # Configuration system documentation
```

---

## Setup and Run

### Windows PowerShell

```powershell
# 1) (Optional) Create virtual environment
python -m venv myenv
myenv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) (Optional) Configure environment variables
copy env.sample .env
notepad .env   # Set ESP32_IP and ESP32_PORT if using environment overrides

# 4) Run the application
python main.py
```

**Controls**: Press `q` in the OpenCV window to quit.

---

## Configure Inputs and ROI

You can configure the system without editing code using `future_scope/config.json`:

### Configuration Options

- **`video_path`**: Path to your input video file (or keep `video.mp4` in the root)
- **`mask_path`**: Path to your mask image (will be resized to match frame size)
- **`polygon_points`**: List of `[x, y]` vertices defining the ROI (minimum 3 points)
- **`serial`**: Serial port configuration (port, baud rate, timeout)
- **`esp32`**: ESP32 TCP connection settings (IP address and port)

### Example Configuration

```json
{
  "video_path": "D:/Projects/CEP_Dynamic_Traffic_Signal/video.mp4",
  "mask_path": "D:/Projects/CEP_Dynamic_Traffic_Signal/mask.png",
  "polygon_points": [[589, 206], [417, 539], [1275, 539], [874, 209]],
  "serial": {
    "port": "COM3",
    "baud": 115200,
    "timeout": 0.1
  },
  "esp32": {
    "ip": "10.84.30.1",
    "port": 80
  }
}
```

### Setting Polygon Points (ROI)

- Provide at least **3 points** in clockwise or counter-clockwise order
- Each point is `[x, y]` in image pixel coordinates
- Floats are allowed and will be cast to integers
- Example quadrilateral: `[[100, 200], [150, 500], [800, 520], [600, 220]]`

### Path Configuration

- **Windows paths**: Use forward slashes (`D:/data/video.mp4`) or escape backslashes (`D:\\data\\video.mp4`)
- Paths can be absolute or relative
- The mask image will be automatically resized to match the video frame size

### Validation and Fallbacks

If `future_scope/config.json` is missing or malformed, the program uses built-in defaults. If `polygon_points` is invalid (e.g., fewer than 3 points), the default polygon is used.

**Tip**: After changing `config.json`, restart the program to load the new settings.

---

## How It Works

### Processing Pipeline

1. **Frame Capture**: Frames are read from the input video and `mask.png` is applied to isolate the ROI
2. **Detection**: YOLOv8 detects vehicles within the masked region
3. **Tracking**: SORT tracks detected vehicles for stability across frames
4. **Density Calculation**: Intersection area of tracked bounding boxes with the polygon approximates occupancy density
5. **Dynamic Timing**: A 5-second sliding average density feeds the timing controller

### Dynamic Timing Rules

- **Initial green**: 90 seconds
- **First 10 seconds**: Observation only (no timing adjustments)
- **Every 5 seconds**: Adjust remaining green time based on density:
  - **Density < 0.3**: Reduce remaining green by 40%
  - **Density 0.4–0.6**: Reduce remaining green by 25%
  - **Density > 0.6**: No reduction
- **Bounds**: Green is clamped between 30–90 seconds
- **Tracking**: Total time saved is accumulated

### TCP Communication Protocol

Per-second messages are sent to the ESP32 using an A/B/C phase code:

| Phase | Format | Example |
|-------|--------|---------|
| **GREEN** | `C{seconds_left}` | `C42` |
| **YELLOW** | `B{seconds_left}` | `B5` |
| **RED** | `A{seconds_left}` | `A60` |

On phase changes or green adjustments, durations are also sent over Serial (if available).

---

## ESP32: Wiring & TCP

### LED Connections

- Connect Red/Yellow/Green LEDs to your chosen GPIO pins via 220–330Ω resistors
- Connect LED cathodes to GND
- Exact GPIO pins are defined in your ESP32 firmware (update as needed)

**Power Notes**:
- Ensure common GND between ESP32 and LEDs
- Use appropriate resistors to limit LED current

### Flashing the ESP32

1. Open `esp32_traffic_controller.ino` in Arduino IDE or PlatformIO
2. Select your board (e.g., "ESP32 Dev Module")
3. Select the correct COM port
4. Upload the sketch
5. Start `python main.py` and watch the countdown update live via A/B/C messages

### Testing

Use `esp32_traffic_controller/tcp_test_sender.py` to manually send `A60/B5/C42` messages and validate your ESP32 parser.

---

## Troubleshooting

### TCP / LED Issues

- **No updates on display**: 
  - Confirm PC and ESP32 are on the same Wi-Fi network
  - Ping the `ESP32_IP` to verify connectivity
  - Check if firewall is blocking Python (allow outbound connections to `ESP32_PORT`)
- **Testing**: Use `tcp_test_sender.py` to manually send `A60/B5/C42` and validate the ESP32 parser

### Performance / ROI Issues

- **Slow inference**: Use `yolov8n.pt` for faster processing
- **High CPU usage**: Lower video resolution or skip frames
- **ROI mismatch**: 
  - Ensure `mask.png` matches frame size (auto-resized in `main.py`)
  - Adjust `polygon_points` in `config.json` to match your actual ROI

---
## Images

![1](https://github.com/user-attachments/assets/038c257d-7192-49f8-b5b3-74eefa3576b9)
![3](https://github.com/user-attachments/assets/a848f502-9981-404d-86c6-318361dd2e40)
![4](https://github.com/user-attachments/assets/6f45c1e1-c681-4c3b-8445-28fc2be57c01)
<img width="1597" height="892" alt="2" src="https://github.com/user-attachments/assets/3257ea0f-774b-48f9-87bf-49ac9c968ab7" />
![6](https://github.com/user-attachments/assets/73fed9e3-9990-41c2-b976-c7fd7d9d3caa)
<img width="1425" height="822" alt="0" src="https://github.com/user-attachments/assets/52ec57b0-44ea-46f7-98f8-4ea1dbb43acf" />

---
## Video



https://github.com/user-attachments/assets/41fd3e41-b301-4d04-ba95-9b60ef2c781a



---


## Future Scope

### Planned Enhancements

- **Interactive ROI Tool**: Draw/edit the polygon on a frame and auto-save to `config.json`
- **Multiple ROIs**: Support for multiple regions of interest with per-ROI weighting
- **Configuration Formats**: Optional YAML/TOML configs with profile selection (e.g., `intersection_A.json` vs `intersection_B.json`)
- **Advanced Analytics**: Historical data logging and traffic pattern analysis
- **Multi-intersection Coordination**: Synchronize timing across multiple intersections

---

## License

For academic/educational use only. YOLO models are subject to their respective licenses from Ultralytics.

---

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

## Contact

For questions or support, please open an issue in the repository.
