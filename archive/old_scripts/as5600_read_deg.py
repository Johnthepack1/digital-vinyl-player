#!/usr/bin/env python3
import time
from smbus2 import SMBus

AS5600_ADDR = 0x36
RAW_ANGLE_HI = 0x0C
RAW_ANGLE_LO = 0x0D

def read_angle_deg(bus) -> float:
    hi = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_HI)
    lo = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_LO)
    raw = ((hi << 8) | lo) & 0x0FFF
    return raw * 360.0 / 4096.0

def main():
    with SMBus(1) as bus:
        a = read_angle_deg(bus)
        print(f"{a:.2f}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import time
from smbus2 import SMBus

AS5600_ADDR = 0x36
RAW_ANGLE_HI = 0x0C
RAW_ANGLE_LO = 0x0D

def read_angle_deg(bus) -> float:
    hi = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_HI)
    lo = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_LO)
    raw = ((hi << 8) | lo) & 0x0FFF
    return raw * 360.0 / 4096.0

def main():
    with SMBus(1) as bus:
        a = read_angle_deg(bus)
        print(f"{a:.2f}")

if __name__ == "__main__":
    main()
