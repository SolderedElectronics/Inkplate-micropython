"""MicroPython driver for the MCP4018 digital potentiometer, used on
Inkplate4TEMPERA to set the buzzer's pitch (DIGIPOT_ADDR 0x2F).

MCP4018/17/19 have no internal register/command byte -- unlike the frontlight
pot on the same board (frontlight.py, a different chip at a different address
needing a 2-byte register write), a single write IS the raw 7-bit wiper value
(0-127 across the pot's 128 steps).
"""


class MCP4018:
    def __init__(self, i2c, addr=0x2F):
        self.i2c = i2c
        self.addr = addr

    def set_wiper(self, value):
        self.i2c.writeto(self.addr, bytes((value & 0x7F,)))

    # Rounds to the nearest wiper step (percent/100 * 127)
    def set_wiper_percent(self, percent):
        self.set_wiper(int(percent / 100.0 * 127.0 + 0.5))
