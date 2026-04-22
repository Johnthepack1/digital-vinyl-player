// ===============================
//  Nano v4 Control Board (FINAL)
//  - A0: Volume pot        -> "VOL:<0-100>"
//  - A1: Needle position   -> "NEEDLE:DOWN" / "NEEDLE:UP"   (pot with hysteresis)
//  - D2: Back/Hidden button-> "BTN:SHORT" / "BTN:LONG"      (7s hold)
// ===============================

const int VOL_POT_PIN    = A0;
const int NEEDLE_POT_PIN = A1;
const int BTN_PIN        = 2;   // D2 (button to GND, INPUT_PULLUP)

// ---- Function prototypes (fixes compile error) ----
int  readAveraged(int pin, int samples = 10);
int  readVolumePercent();
void handleVolume();
void handleNeedle();
void handleButton();

// ----- Volume settings -----
int lastVolume = -1;
const int VOL_DEADBAND = 2;            // only send if change >= this
const unsigned long VOL_MIN_MS = 80;   // min time between volume sends
unsigned long lastVolMs = 0;

// ----- Needle settings (POT) -----
// Tune these once by printing raw values while moving needle
int NEEDLE_DOWN_THRESH = 620;   // crossing above -> NEEDLE:DOWN
int NEEDLE_UP_THRESH   = 580;   // crossing below -> NEEDLE:UP
bool needleDown = false;
bool lastNeedleDown = false;

// ----- Button settings -----
bool btnLastState   = HIGH;       // last raw reading
bool btnPressed     = false;      // are we in a press?
bool longSent       = false;
unsigned long pressStartMs = 0;

const unsigned long DEBOUNCE_MS   = 30;     // debounce noise
const unsigned long LONG_PRESS_MS = 7000;   // 7 seconds = Setup Mode

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(BTN_PIN, INPUT_PULLUP);  // button to GND, idle HIGH

  // Send initial volume
  Serial.print("VOL:");
  Serial.println(readVolumePercent());

  // Determine initial needle state
  int n = readAveraged(NEEDLE_POT_PIN, 8);
  needleDown = (n > NEEDLE_DOWN_THRESH);
  lastNeedleDown = needleDown;
  Serial.println(needleDown ? "NEEDLE:DOWN" : "NEEDLE:UP");
}

// Read analog with simple averaging to reduce jitter
int readAveraged(int pin, int samples) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  return (int)(sum / samples);
}

int readVolumePercent() {
  int volRaw = readAveraged(VOL_POT_PIN, 10);
  int volume = map(volRaw, 0, 1023, 0, 100);
  return constrain(volume, 0, 100);
}

// ---------------- Volume Handler ----------------
void handleVolume() {
  unsigned long now = millis();
  if (now - lastVolMs < VOL_MIN_MS) return;

  int volume = readVolumePercent();

  if (lastVolume < 0 || abs(volume - lastVolume) >= VOL_DEADBAND) {
    Serial.print("VOL:");
    Serial.println(volume);
    lastVolume = volume;
    lastVolMs = now;
  }
}

// ---------------- Needle Handler (POT + hysteresis) ----------------
void handleNeedle() {
  int needleRaw = readAveraged(NEEDLE_POT_PIN, 6);

  // Higher raw = more "down/on record"
  if (!needleDown && needleRaw > NEEDLE_DOWN_THRESH) {
    needleDown = true;
  } else if (needleDown && needleRaw < NEEDLE_UP_THRESH) {
    needleDown = false;
  }

  if (needleDown != lastNeedleDown) {
    lastNeedleDown = needleDown;
    Serial.println(needleDown ? "NEEDLE:DOWN" : "NEEDLE:UP");
  }

  // Debug for tuning (temporary):
  // Serial.println(needleRaw);
}

// ------------- Button Handler (short / long) -------------
void handleButton() {
  static unsigned long lastChangeMs = 0;

  bool reading = digitalRead(BTN_PIN);
  unsigned long now = millis();

  // Debounce edge
  if (reading != btnLastState) {
    btnLastState = reading;
    lastChangeMs = now;
  }

  if ((now - lastChangeMs) > DEBOUNCE_MS) {
    // Press start: HIGH -> LOW
    if (!btnPressed && reading == LOW) {
      btnPressed = true;
      longSent = false;
      pressStartMs = now;
    }

    // Long press event while still held
    if (btnPressed && !longSent && reading == LOW) {
      if ((now - pressStartMs) >= LONG_PRESS_MS) {
        longSent = true;
        Serial.println("BTN:LONG");
      }
    }

    // Release: LOW -> HIGH
    if (btnPressed && reading == HIGH) {
      btnPressed = false;

      // Only emit SHORT if we didn't already emit LONG
      if (!longSent) {
        Serial.println("BTN:SHORT");
      }
    }
  }
}

// ---------------- Main Loop ----------------
void loop() {
  handleVolume();
  handleNeedle();
  handleButton();

  delay(20);
}
