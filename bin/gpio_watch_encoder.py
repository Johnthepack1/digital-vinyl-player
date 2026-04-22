#!/usr/bin/env python3
import time

from gpiozero import Button

CLK = 17
DT = 27
SW = 22

clk = Button(CLK, pull_up=True)
dt = Button(DT, pull_up=True)
sw = Button(SW, pull_up=True, bounce_time=0.02)

print("Watching encoder pins (BCM): CLK=17 DT=27 SW=22")
print("Turn knob and press button. Printing only when something changes.\n")

last = None
while True:
    current = (clk.value, dt.value, sw.value)
    if current != last:
        print(f"CLK={int(current[0])}  DT={int(current[1])}  SW={int(current[2])}")
        last = current
    time.sleep(0.005)
