"""Driver for the Elan capacitive touchscreen controller, shared by Inkplate4TEMPERA
and Inkplate6PLUS/6PLUSV2 (same chip; each board supplies its own EN/RST pin
numbers, which PCAL6416A expander they sit on, and panel size).
"""

import time
from machine import Pin
from pcal6416a import *

TOUCHSCREEN_ADDR = 0x15

_HELLO_PACKET = b"\x55\x55\x55\x55"


def _bound(low, value, high):
    return low <= value <= high


def _c_idiv(a, b):
    """C-style truncate-toward-zero integer division, unlike Python's floor `//`.
    ts_get_data()'s rotation remap divides `(raw * E_INK_DIM - 1) / resolution`
    (multiply then subtract 1, not raw*(E_INK_DIM-1)), which goes briefly negative
    when raw==0 -- floor `//` would round the wrong way at that edge."""
    q = a // b
    if a % b != 0 and (a < 0) != (b < 0):
        q += 1
    return q


class Touch:
    _ts_flag = False
    touch_n = 0
    touch_x = [0, 0]
    touch_y = [0, 0]
    touch_t = 0

    _ts_x_resolution = 0
    _ts_y_resolution = 0
    _ts_int_pin = None

    _i2c = None
    _pcal = None
    _inkplate = None

    _en_pin = 0
    _rst_pin = 0
    _int_pin_num = 36
    _addr = TOUCHSCREEN_ADDR
    _width = 0
    _height = 0

    # Per-board touch-overlay calibration flags; set via init().
    _x_raw_inverted = False
    _xy_swapped = False
    _xy_flipped = False

    @classmethod
    def init(
        cls,
        i2c,
        pcal,
        inkplate,
        en_pin,
        rst_pin,
        width,
        height,
        int_pin_num=36,
        addr=TOUCHSCREEN_ADDR,
        x_raw_inverted=False,
        xy_swapped=False,
        xy_flipped=False,
    ):
        cls._i2c = i2c
        cls._pcal = pcal
        cls._inkplate = inkplate
        cls._en_pin = en_pin
        cls._rst_pin = rst_pin
        cls._int_pin_num = int_pin_num
        cls._addr = addr
        cls._width = width
        cls._height = height
        cls._x_raw_inverted = x_raw_inverted
        cls._xy_swapped = xy_swapped
        cls._xy_flipped = xy_flipped

    @classmethod
    def _ts_int(cls, pin):
        cls._ts_flag = True

    @classmethod
    def ts_write_regs(cls, addr, buff):
        try:
            cls._i2c.writeto(addr, bytes(buff))
            return 0  # 0 = success
        except OSError:
            return 1

    @classmethod
    def ts_read_regs(cls, addr, length):
        return cls._i2c.readfrom(addr, length)

    @classmethod
    def ts_get_raw_data(cls):
        return cls._i2c.readfrom(cls._addr, 8)

    @staticmethod
    def ts_get_xy(d, offset):
        x = ((d[offset] & 0xF0) << 4) | d[offset + 1]
        y = ((d[offset] & 0x0F) << 8) | d[offset + 2]
        return x, y

    @classmethod
    def ts_hardware_reset(cls):
        cls._pcal.digital_write(cls._rst_pin, 0)
        time.sleep_ms(15)
        cls._pcal.digital_write(cls._rst_pin, 1)
        time.sleep_ms(15)

    @classmethod
    def ts_software_reset(cls):
        if cls.ts_write_regs(cls._addr, b"\x77\x77\x77\x77") != 0:
            return False

        timeout = 1000
        while not cls._ts_flag and timeout > 0:
            time.sleep_ms(1)
            timeout -= 1
        if timeout > 0:
            cls._ts_flag = True

        rb = cls._i2c.readfrom(cls._addr, 4)
        cls._ts_flag = False
        return rb == _HELLO_PACKET

    @classmethod
    def ts_get_resolution(cls):
        cls.ts_write_regs(cls._addr, b"\x53\x60\x00\x00")
        rec = cls.ts_read_regs(cls._addr, 4)
        x_res = rec[2] | ((rec[3] & 0xF0) << 4)
        cls.ts_write_regs(cls._addr, b"\x53\x63\x00\x00")
        rec = cls.ts_read_regs(cls._addr, 4)
        y_res = rec[2] | ((rec[3] & 0xF0) << 4)
        cls._ts_flag = False
        return x_res, y_res

    @classmethod
    def ts_init(cls, power_state=1):
        GpioPin(cls._pcal, cls._en_pin, mode_output)
        GpioPin(cls._pcal, cls._rst_pin, mode_output)

        cls._pcal.digital_write(cls._en_pin, 0)
        time.sleep_ms(100)

        cls._ts_int_pin = Pin(cls._int_pin_num, mode=Pin.IN, pull=Pin.PULL_UP)
        cls._ts_int_pin.irq(trigger=Pin.IRQ_FALLING, handler=cls._ts_int)

        cls.ts_hardware_reset()
        if not cls.ts_software_reset():
            cls._ts_int_pin.irq(handler=None)
            return False

        cls._ts_x_resolution, cls._ts_y_resolution = cls.ts_get_resolution()
        cls.ts_set_power_state(power_state)

        # Primes the flag true at the end of init, regardless of any actual
        # interrupt having fired yet.
        cls._ts_flag = True
        return True

    @classmethod
    def ts_shutdown(cls):
        cls.end()

    @classmethod
    def ts_set_power_state(cls, state):
        state &= 1
        reg = bytearray(b"\x54\x50\x00\x01")
        reg[1] |= state << 3
        cls.ts_write_regs(cls._addr, reg)

    @classmethod
    def ts_get_power_state(cls):
        cls.ts_write_regs(cls._addr, b"\x53\x50\x00\x01")
        cls._ts_flag = False
        buf = cls.ts_read_regs(cls._addr, 4)
        return (buf[1] >> 3) & 1

    @classmethod
    def ts_available(cls):
        return cls._ts_flag

    @classmethod
    def ts_get_data(cls, x_pos, y_pos):
        cls._ts_flag = False
        raw = cls.ts_get_raw_data()

        fingers = 0
        for i in range(8):
            if raw[7] & (1 << i):
                fingers += 1

        rotation = cls._inkplate.get_rotation() if cls._inkplate is not None else 0

        for i in range(2):
            x_raw, y_raw = cls.ts_get_xy(raw, 1 + i * 3)

            if cls._x_raw_inverted:
                x_raw = cls._ts_x_resolution - x_raw

            if rotation == 0:
                y_pos[i] = cls._height - 1 - _c_idiv(x_raw * cls._height - 1, cls._ts_x_resolution)
                x_pos[i] = _c_idiv(y_raw * cls._width - 1, cls._ts_y_resolution)
            elif rotation == 1:
                x_pos[i] = cls._height - 1 - _c_idiv(x_raw * cls._height - 1, cls._ts_x_resolution)
                y_pos[i] = cls._width - 1 - _c_idiv(y_raw * cls._width - 1, cls._ts_y_resolution)
            elif rotation == 2:
                y_pos[i] = _c_idiv(x_raw * cls._height - 1, cls._ts_x_resolution)
                x_pos[i] = cls._width - 1 - _c_idiv(y_raw * cls._width - 1, cls._ts_y_resolution)
            else:  # rotation == 3
                x_pos[i] = _c_idiv(x_raw * cls._height - 1, cls._ts_x_resolution)
                y_pos[i] = _c_idiv(y_raw * cls._width - 1, cls._ts_y_resolution)

            if cls._xy_swapped:
                x_pos[i], y_pos[i] = y_pos[i], x_pos[i]

            if cls._xy_flipped:
                x_pos[i] = cls._width - 1 - x_pos[i]
                y_pos[i] = cls._height - 1 - y_pos[i]

        return fingers

    @classmethod
    def touch_in_area(cls, x1, y1, w, h):
        x2 = x1 + w
        y2 = y1 + h

        if cls.ts_available():
            x = [0, 0]
            y = [0, 0]
            n = cls.ts_get_data(x, y)

            if n:
                cls.touch_t = time.ticks_ms()
                cls.touch_n = n
                # A naive 2-byte-style copy here would only copy finger 0's X/Y,
                # leaving finger 1's cached values stale after every read --
                # copy both explicitly instead.
                cls.touch_x = list(x)
                cls.touch_y = list(y)
            # n == 0: touch_n/_x/_y deliberately left at their last value --
            # only overwritten on a fresh nonzero read, not reset to 0 here.

        if time.ticks_diff(time.ticks_ms(), cls.touch_t) < 100:
            if (
                cls.touch_n == 1
                and _bound(x1, cls.touch_x[0], x2)
                and _bound(y1, cls.touch_y[0], y2)
            ):
                return True
            if cls.touch_n == 2 and (
                (_bound(x1, cls.touch_x[0], x2) and _bound(y1, cls.touch_y[0], y2))
                or (_bound(x1, cls.touch_x[1], x2) and _bound(y1, cls.touch_y[1], y2))
            ):
                return True

        return False

    @classmethod
    def power(cls, pwr):
        if pwr:
            cls._pcal.digital_write(cls._en_pin, 0)
            time.sleep_ms(50)
            cls._pcal.digital_write(cls._rst_pin, 1)
            time.sleep_ms(50)
        else:
            cls._pcal.digital_write(cls._en_pin, 1)
            time.sleep_ms(50)
            cls._pcal.digital_write(cls._rst_pin, 0)

    @classmethod
    def end(cls):
        if cls._ts_int_pin is not None:
            cls._ts_int_pin.irq(handler=None)
        cls._ts_flag = False
        cls.power(False)
