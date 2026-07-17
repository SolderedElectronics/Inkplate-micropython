"""MicroPython driver for the MCP23017 GPIO expander."""

from machine import Pin as mPin
from micropython import const

IODIR = const(0)
IOCON = const(0xA)
GPPU = const(0xC)
GPIO = const(0x12)
OLAT = const(0x14)


class MCP23017:
    """Minimal driver for the MCP23017 16-bit I2C I/O expander."""

    def __init__(self, i2c, addr=0x20):
        self.i2c = i2c
        self.addr = addr
        self.write(IOCON, 0x00)
        self.write2(IODIR, 0xFF, 0xFF)  # All inputs
        self.gpio0 = 0
        self.gpio1 = 0
        self.write2(GPIO, 0, 0)

    def read(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def write(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes((v,)))

    def write2(self, reg, v1, v2):
        self.i2c.writeto_mem(self.addr, reg, bytes((v1, v2)))

    def writebuf(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, v)

    # Caches gpio0/gpio1 so a bit write is a read-modify-write on the shadow
    # value instead of an extra I2C read of the actual register.
    def bit(self, reg, num, v=None):
        if v is None:
            data = self.read(reg)
            if reg == GPIO:
                self.gpio0 = data
            elif reg == GPIO + 1:
                self.gpio1 = data
            return (data >> num) & 1
        else:
            mask = 0xFF ^ (1 << num)
            if reg == GPIO:
                self.gpio0 = (self.gpio0 & mask) | ((v & 1) << num)
                self.write(reg, self.gpio0)
            elif reg == GPIO + 1:
                self.gpio1 = (self.gpio1 & mask) | ((v & 1) << num)
                self.write(reg, self.gpio1)
            else:
                data = (self.read(reg) & mask) | ((v & 1) << num)
                self.write(reg, data)

    def pin(self, num, mode=mPin.IN, pull=None, value=None):
        return Pin(self, num, mode, pull, value)

    def pin_mode(self, pin, mode):
        # mode uses the same 0/1/2/3 convention as pcal6416a.py's mode_input/
        # mode_output/mode_input_pullup/mode_input_pulldown -- kept as plain ints
        # here so this driver has no import dependency on pcal6416a.py.
        if mode == 3:  # mode_input_pulldown
            raise ValueError("MCP23017 has no pull-down support")
        incr = pin >> 3
        num = pin & 0x7
        self.bit(IODIR + incr, num, 0 if mode == 1 else 1)
        if mode == 2:  # mode_input_pullup
            self.bit(GPPU + incr, num, 1)

    def digital_write(self, pin, value):
        self.bit(GPIO + (pin >> 3), pin & 0x7, value)

    def digital_read(self, pin):
        return self.bit(GPIO + (pin >> 3), pin & 0x7)


class Pin:
    """Minimal machine.Pin look-alike for pins on the MCP23017."""

    def __init__(self, mcp23017, num, mode=mPin.IN, pull=None, value=None):
        self.bit = mcp23017.bit
        incr = num >> 3  # Bank selector
        self.gpio = GPIO + incr
        self.num = num = num & 0x7
        if value is not None:
            self.bit(self.gpio, num, value)
        self.bit(IODIR + incr, num, 1 if mode == mPin.IN else 0)
        self.bit(GPPU + incr, num, 1 if pull == mPin.PULL_UP else 0)

    def value(self, v=None):
        if v is None:
            return self.bit(self.gpio, self.num)
        else:
            self.bit(self.gpio, self.num, v)

    __call__ = value
