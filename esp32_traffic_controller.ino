#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// --------- Pins (change as needed) ---------
const int PIN_RED = 26;
const int PIN_YELLOW = 25;
const int PIN_GREEN = 33;

// LCD I2C address and geometry (change address if your module differs)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// --------- State ---------
enum Phase { PH_GREEN, PH_YELLOW, PH_RED };
Phase currentPhase = PH_GREEN;

int cfgGreen = 90;   // seconds (remaining when last update received)
int cfgYellow = 5;   // seconds per yellow phase
int cfgRed = 60;     // seconds per red phase
int totalSaved = 0;  // accumulated seconds saved reported by Python

unsigned long phaseStartMs = 0;
unsigned long nowMs = 0;

long remainingGreenAtUpdate = 90; // seconds when last GREEN update received

// --- Fast countdown animation state (for GREEN reductions) ---
bool animActive = false;
long displayRemaining = 90;     // what we show on LCD during GREEN
long animTarget = 90;           // target remaining to animate to
unsigned long animLastMs = 0;
const unsigned long animIntervalMs = 40; // smaller = faster animation

// Helper: set LEDs
void setLeds(bool r, bool y, bool g) {
  digitalWrite(PIN_RED, r ? HIGH : LOW);
  digitalWrite(PIN_YELLOW, y ? HIGH : LOW);
  digitalWrite(PIN_GREEN, g ? HIGH : LOW);
}

// Helper: show two lines on LCD
void showLCD(const String &line1, const String &line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

// Parse line like: GREEN:30,RED:60,YELLOW:5,SAVED:15
void parseLine(const String &line) {
  int g = cfgGreen, r = cfgRed, y = cfgYellow, s = totalSaved;

  int start = 0;
  while (start < (int)line.length()) {
    int comma = line.indexOf(',', start);
    String token = (comma == -1) ? line.substring(start) : line.substring(start, comma);
    token.trim();

    int colon = token.indexOf(':');
    if (colon > 0) {
      String key = token.substring(0, colon);
      String val = token.substring(colon + 1);
      key.trim();
      val.trim();
      int iv = val.toInt();
      if (key.equalsIgnoreCase("GREEN")) g = iv;
      else if (key.equalsIgnoreCase("RED")) r = iv;
      else if (key.equalsIgnoreCase("YELLOW")) y = iv;
      else if (key.equalsIgnoreCase("SAVED")) s = iv;
    }

    if (comma == -1) break;
    start = comma + 1;
  }

  cfgGreen = g > 0 ? g : 0;
  cfgRed = r > 0 ? r : 0;
  cfgYellow = y > 0 ? y : 0;
  totalSaved = s >= 0 ? s : 0;

  // If we get a GREEN update, ensure local countdown aligns to new remaining value
  if (currentPhase == PH_GREEN) {
    // Compute current remaining BEFORE resetting reference
    unsigned long nowRef = millis();
    unsigned long elapsedMs = nowRef - phaseStartMs;
    long prevRemaining = remainingGreenAtUpdate - (long)(elapsedMs / 1000);
    if (prevRemaining < 0) prevRemaining = 0;

    // Set new remaining from Python
    remainingGreenAtUpdate = cfgGreen;
    phaseStartMs = nowRef; // reset reference for true countdown

    // Start fast animation if new value is lower than what was shown
    if (cfgGreen < prevRemaining) {
      displayRemaining = prevRemaining;
      animTarget = cfgGreen;
      animActive = true;
      animLastMs = nowRef;
    } else {
      animActive = false;
      displayRemaining = cfgGreen;
    }
  }
}

String readLineFromSerial() {
  static String buffer;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() > 0) {
        String line = buffer;
        buffer = "";
        return line;
      }
    } else {
      buffer += c;
    }
  }
  return String();
}

void setup() {
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  setLeds(true, false, false);

  Serial.begin(115200);
  Wire.begin();
  lcd.init();
  lcd.backlight();

  phaseStartMs = millis();
  currentPhase = PH_GREEN; // Python starts with GREEN and will send initial timing
  remainingGreenAtUpdate = cfgGreen;
  displayRemaining = cfgGreen;

  showLCD("Waiting timing", "from Python...");
}

void loop() {
  nowMs = millis();

  // Handle incoming serial commands
  String line = readLineFromSerial();
  if (line.length() > 0) {
    parseLine(line);
  }

  // Phase management and countdowns
  if (currentPhase == PH_GREEN) {
    setLeds(false, false, true);

    unsigned long elapsedMs = nowMs - phaseStartMs;
    long trueRemaining = remainingGreenAtUpdate - (long)(elapsedMs / 1000);
    if (trueRemaining < 0) trueRemaining = 0;

    // Drive animation if active; otherwise show true remaining
    if (animActive) {
      if (displayRemaining > animTarget && (nowMs - animLastMs) >= animIntervalMs) {
        displayRemaining--;
        animLastMs = nowMs;
      }
      if (displayRemaining <= animTarget) {
        animActive = false;
        displayRemaining = animTarget;
      }
    } else {
      displayRemaining = trueRemaining;
    }

    showLCD("GREEN " + String(displayRemaining) + "s",
            "Saved:" + String(totalSaved) + "s");

    if (trueRemaining == 0) {
      currentPhase = PH_YELLOW;
      phaseStartMs = nowMs;
    }
  }
  else if (currentPhase == PH_YELLOW) {
    setLeds(false, true, false);

    unsigned long elapsedMs = nowMs - phaseStartMs;
    long remaining = cfgYellow - (long)(elapsedMs / 1000);
    if (remaining < 0) remaining = 0;

    showLCD("YELLOW " + String(remaining) + "s",
            "Saved:" + String(totalSaved) + "s");

    if (remaining == 0) {
      currentPhase = PH_RED;
      phaseStartMs = nowMs;
    }
  }
  else { // PH_RED
    setLeds(true, false, false);

    unsigned long elapsedMs = nowMs - phaseStartMs;
    long remaining = cfgRed - (long)(elapsedMs / 1000);
    if (remaining < 0) remaining = 0;

    showLCD("RED " + String(remaining) + "s",
            "Saved:" + String(totalSaved) + "s");

    if (remaining == 0) {
      // Expect Python to send the next GREEN timing before/around this moment.
      currentPhase = PH_GREEN;
      phaseStartMs = nowMs;
      remainingGreenAtUpdate = cfgGreen;
    }
  }

  delay(50);
}


