## ESP32 Setup Guide (LEDs + 16x2 I²C LCD) – From Zero to Working

Use this guide to get the ESP32 side running for the dynamic traffic signal project.

### 1) Install Arduino IDE and ESP32 Board Support
1. Install Arduino IDE (2.x recommended).
2. Open Arduino IDE → File → Preferences → “Additional Boards Manager URLs” → add:
   - https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
3. Tools → Board → Boards Manager… → search “esp32” → install “esp32 by Espressif Systems”.
4. Tools → Board → select your ESP32 (e.g., “ESP32 Dev Module”).

### 2) Install Required Libraries
We need the LiquidCrystal_I2C library for 16x2 LCD with I²C backpack.

- Sketch → Include Library → Manage Libraries… → search “LiquidCrystal I2C”
- Install one of these popular libraries:
  - “LiquidCrystal I2C” by Frank de Brabander, or
  - “LiquidCrystal_I2C” by Marco Schwartz

Either works with the included code. If your LCD shows garbled text, try the other library.

### 3) Wiring
LEDs (use 220–330 Ω series resistors):
- Red LED anode → GPIO 26; cathode → GND
- Yellow LED anode → GPIO 25; cathode → GND
- Green LED anode → GPIO 33; cathode → GND

I²C LCD (typical backpack address 0x27):
- LCD VCC → 5V (or 3.3V if backpack supports it)
- LCD GND → GND
- LCD SDA → GPIO 21
- LCD SCL → GPIO 22

Ensure common ground between all devices and the ESP32.

### 4) Open the Project Sketch
1. In Arduino IDE, open `esp32_traffic_controller.ino` from this repository.
2. Confirm these lines match your hardware:
```
const int PIN_RED = 26;
const int PIN_YELLOW = 25;
const int PIN_GREEN = 33;
LiquidCrystal_I2C lcd(0x27, 16, 2);
```
If your I²C address differs, update `0x27` accordingly (see Step 6 for scanning).

### 5) Select Port and Upload
1. Connect the ESP32 via USB.
2. Tools → Port → select the correct COM port (Windows) or /dev/ttyUSBx (Linux) or /dev/cu.SLAB_USBtoUART (macOS).
3. Click Upload. Wait for “Done uploading.”

### 6) (Optional) Find the LCD I²C Address
If your LCD shows a blank screen, contrast might be too low (adjust potentiometer) or the address is not 0x27.

- Upload an I²C scanner example (search “Arduino I2C scanner” online), or use this minimal sketch:
```
#include <Wire.h>
void setup(){ Serial.begin(115200); Wire.begin(); }
void loop(){
  Serial.println("Scanning...");
  byte count=0; for (byte addr=1; addr<127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission()==0){ Serial.printf("Found: 0x%02X\n", addr); count++; }
  }
  if(!count) Serial.println("No I2C devices found"); delay(2000);
}
```
Update the address in `LiquidCrystal_I2C lcd(<address>, 16, 2);` to match.

### 7) Run the Python Controller
1. Install Python requirements in your virtual environment:
```
pip install -r requirements.txt
```
2. In `main.py`, set `SERIAL_PORT` to your ESP32 port (e.g., `COM3`).
3. Run:
```
python main.py
```
The Python app will send lines like `GREEN:30,RED:60,YELLOW:5,SAVED:15` to the ESP32.

### 8) What You Should See
- LCD line 1: active phase and remaining seconds (e.g., `GREEN 42s`).
- LCD line 2: `Saved:<total_seconds>`
- LEDs: only one LED on at a time according to the phase.
- When Python reduces the green time mid-phase, the LCD will quickly animate from the old value to the new lower value.

### 9) Troubleshooting
- Nothing on LCD:
  - Adjust the contrast potentiometer on the LCD backpack.
  - Verify SDA/SCL wiring (GPIO 21/22).
  - Scan for the correct I²C address and update the code.
- Garbled characters:
  - Try the alternate LiquidCrystal I2C library.
  - Confirm 16x2 geometry in constructor `(16, 2)`.
- LEDs not lighting:
  - Double-check resistor orientation and pin numbers.
  - Ensure GND is common.
- Serial conflicts:
  - Close Arduino Serial Monitor before running `main.py`.
  - Keep baud at 115200 on both sides.
- Python cannot open port:
  - Update `SERIAL_PORT` in `main.py` and ensure drivers are installed.

### 10) Customization
- Change LED pins: update `PIN_RED`, `PIN_YELLOW`, `PIN_GREEN` in the sketch.
- Change LCD address: modify `LiquidCrystal_I2C lcd(0x27, 16, 2);`.
- Change yellow/red durations: Python controls logic; ESP32 uses `cfgYellow`/`cfgRed` from the latest message.
- LCD animation speed: adjust `animIntervalMs` in the sketch (smaller = faster).

You’re ready to go! Upload the ESP32 sketch, run `main.py`, and watch the LEDs and LCD follow the dynamic green time based on real-time density analysis.


