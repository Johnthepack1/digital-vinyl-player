from machine import Pin, ADC
import time

# ===============================
# Pico Controls (MicroPython)
# - GP26 / ADC0: Volume pot   -> "VOL:<0-100>"
# - GP27 / ADC1: Needle pot   -> "NEEDLE:DOWN" / "NEEDLE:UP"
# - GP16: Button to GND       -> "BTN:SHORT" / "BTN:LONG" (7s hold)
# ===============================

VOL_ADC = ADC(26)      # GP26 / ADC0
NEEDLE_ADC = ADC(27)   # GP27 / ADC1
BTN = Pin(16, Pin.IN, Pin.PULL_UP)

# ----- Volume -----
VOL_DEADBAND = 2
VOL_MIN_MS = 80
last_vol = -1
last_vol_ms = 0

# ----- Needle thresholds (tune later if needed) -----
NEEDLE_DOWN_THRESH = 40000
NEEDLE_UP_THRESH   = 36000
needle_down = False
last_needle_down = None

# ----- Button -----
DEBOUNCE_MS = 30
LONG_PRESS_MS = 7000
btn_last = 1
btn_pressed = False
long_sent = False
press_start_ms = 0
last_change_ms = 0

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def read_avg(adc, samples=8):
    s = 0
    for _ in range(samples):
        s += adc.read_u16()
        time.sleep_ms(2)
    return s // samples

def vol_percent():
    raw = read_avg(VOL_ADC, 10)              # 0..65535
    v = int((raw * 100) // 65535)            # 0..100
    return clamp(v, 0, 100)

def handle_volume(now_ms):
    global last_vol, last_vol_ms
    if now_ms - last_vol_ms < VOL_MIN_MS:
        return
    v = vol_percent()
    if last_vol < 0 or abs(v - last_vol) >= VOL_DEADBAND:
        print("VOL:%d" % v)
        last_vol = v
        last_vol_ms = now_ms

def handle_needle():
    global needle_down, last_needle_down
    raw = read_avg(NEEDLE_ADC, 6)

    if (not needle_down) and raw > NEEDLE_DOWN_THRESH:
        needle_down = True
    elif needle_down and raw < NEEDLE_UP_THRESH:
        needle_down = False

    if last_needle_down is None or needle_down != last_needle_down:
        last_needle_down = needle_down
        print("NEEDLE:DOWN" if needle_down else "NEEDLE:UP")

def handle_button(now_ms):
    global btn_last, btn_pressed, long_sent, press_start_ms, last_change_ms

    reading = BTN.value()  # 1=released, 0=pressed

    if reading != btn_last:
        btn_last = reading
        last_change_ms = now_ms

    if now_ms - last_change_ms <= DEBOUNCE_MS:
        return

    if (not btn_pressed) and reading == 0:
        btn_pressed = True
        long_sent = False
        press_start_ms = now_ms

    if btn_pressed and (not long_sent) and reading == 0:
        if now_ms - press_start_ms >= LONG_PRESS_MS:
            long_sent = True
            print("BTN:LONG")

    if btn_pressed and reading == 1:
        btn_pressed = False
        if not long_sent:
            print("BTN:SHORT")

# boot
time.sleep_ms(300)
print("BOOT")
print("VOL:%d" % vol_percent())
handle_needle()

# loop
while True:
    now = time.ticks_ms()
    handle_volume(now)
    handle_needle()
    handle_button(now)
    time.sleep_ms(20)
