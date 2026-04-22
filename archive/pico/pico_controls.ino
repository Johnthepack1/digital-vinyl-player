// ===============================
//  Pico Controls (Arduino-Pico)
//  - GP26 / ADC0: Volume pot   -> "VOL:<0-100>"
//  - GP27 / ADC1: Needle pot   -> "NEEDLE:DOWN" / "NEEDLE:UP"
//  - GP16: Button to GND       -> "BTN:SHORT" / "BTN:LONG" (7s hold)
// ===============================

#include <Arduino.h>

// ---- Pins (Pico) ----
const int VOL_POT_PIN    = 26;   // ADC0 (GP26)
const int NEEDLE_POT_PIN = 27;   // ADC1 (GP27)
const int BTN_PIN        = 16;   // GP16, button to GND, INPUT_PULLUP

// ---- Function prototypes ----
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

// ----- Needle settings (POT + hysteresis) -----
int NEEDLE_DOWN_THRESH = 620;   // crossing above -> NEEDLE:DOWN
int NEEDLE_UP_THRESH   = 580;   // crossing below -> NEEDLE:UP
bool needleDown = false;
bool lastNeedleDown = false;

// ----- Button settings -----
bool btnLastState   = HIGH;
bool btnPressed     = false;
bool longSent       = false;
unsigned long pressStartMs = 0;

const unsigned long DEBOUNCE_MS   = 30;
const unsigned long LONG_PRESS_MS = 7000; // 7s

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(BTN_PIN, INPUT_PULLUP);

  // Initial volume
  Serial.print("VOL:");
  Serial.println(readVolumePercent());

  // Initial needle
  int n = readAveraged(NEEDLE_POT_PIN, 8);
  needleDown = (n > NEEDLE_DOWN_THRESH);
  lastNeedleDown = needleDown;
  Serial.println(needleDown ? "NEEDLE:DOWN" : "NEEDLE:UP");
}

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

void handleNeedle() {
  int needleRaw = readAveraged(NEEDLE_POT_PIN, 6);

  if (!needleDown && needleRaw > NEEDLE_DOWN_THRESH) {
    needleDown = true;
  } else if (needleDown && needleRaw < NEEDLE_UP_THRESH) {
    needleDown = false;
  }

  if (needleDown != lastNeedleDown) {
    lastNeedleDown = needleDown;
    Serial.println(needleDown ? "NEEDLE:DOWN" : "NEEDLE:UP");
  }
}

void handleButton() {
  static unsigned long lastChangeMs = 0;

  bool reading = digitalRead(BTN_PIN);
  unsigned long now = millis();

  if (reading != btnLastState) {
    btnLastState = reading;
    lastChangeMs = now;
  }

  if ((now - lastChangeMs) > DEBOUNCE_MS) {
    if (!btnPressed && reading == LOW) {
      btnPressed = true;
      longSent = false;
      pressStartMs = now;
    }

    if (btnPressed && !longSent && reading == LOW) {
      if ((now - pressStartMs) >= LONG_PRESS_MS) {
        longSent = true;
        Serial.println("BTN:LONG");
      }
    }

    if (btnPressed && reading == HIGH) {
      btnPressed = false;
      if (!longSent) Serial.println("BTN:SHORT");
    }
  }
}

void loop() {
  handleVolume();
  handleNeedle();
  handleButton();
  delay(20);
}
