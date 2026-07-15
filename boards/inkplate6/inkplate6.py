"""MicroPython driver for the Inkplate 6 e-paper display."""

import time
import micropython
import os
import inkplate
from machine import ADC, I2C, Pin, SDCard
from uarray import array
from pcal6416a import *
from mcp23017 import MCP23017
from tps65186 import TPS65186, read_battery_voltage
from rtc import RTC
from epd_power_pins import tristate_display_pins, restore_display_pins
from micropython import const
import gfx_standard_font_01 as montserrat_black
import gc


import machine

machine.freq(240000000)
# Raw display constants for Inkplate 6
D_ROWS = const(600)
D_COLS = const(800)

# Lookup mask to clear just that pixel's 4 bits (GS4_HMSB, 2 pixels/byte)
pixel_mask_glut = bytearray(b"\xf0\x0f")  # precomputed masks

# This driver targets the INKPLATE6V2 hardware revision by default -- confirmed from this
# repo's own pre-refactor driver, which already used external-expander address 0x21
# (INKPLATE6V2's IO_EXT_ADDR per the Arduino reference driver). INKPLATE6V2's internal
# expander (OE/GMODE/SPV/TPS_*/etc, addr 0x20) is a PCAL6416A; classic INKPLATE6's
# same-role expander is an MCP23017 (confirmed against the real Arduino reference driver
# + this repo's own pre-refactor tve-authored driver). External expander addr also
# differs (classic=0x22, V2=0x21). Flip to "inkplate6" below if your board is the
# original (non-V2) revision -- that also enables TOUCH1/2/3 (classic-only, same
# expander pins 10/11/12 that V2 repurposes for SD_ENABLE).
_BOARD_VARIANT = "inkplate6"
_IS_CLASSIC = _BOARD_VARIANT != "inkplate6v2"
_EXPANDER2_ADDR = 0x21 if _BOARD_VARIANT == "inkplate6v2" else 0x22

# Bit masks used by the (still-Python) byte2gpio table and clean(); the CL/LE/CKV/SPH
# pulse sequencing itself now lives in C (firmware/usermods/inkplate/epd_bitbang.c),
# selected via inkplate.select_board() below.
EPD_DATA = const(0x0E8C0030)  # EPD_D0..EPD_D7
EPD_CL = const(0x00000001)  # in W1Tx0

# Inkplate provides access to the pins of the Inkplate 6 as well as to low-level display
# functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c):
        cls._i2c = i2c
        # External user-GPIO expander is a separate chip from the required internal one
        # (0x20, drives EPD_OE/GMODE/SPV/TPS_*) and some boards ship without it due to
        # chip shortages -- scan first so a missing chip disables gpio_expander_pin(2, ...)
        # instead of NACKing the eager MCP23017.__init__ I2C write and crashing begin().
        detected = i2c.scan()
        expander2_present = _EXPANDER2_ADDR in detected
        if _IS_CLASSIC:
            cls._expander1 = MCP23017(i2c)
            cls._expander2 = MCP23017(i2c, _EXPANDER2_ADDR) if expander2_present else None
        else:
            cls._expander1 = PCAL6416A(i2c)
            cls._expander2 = PCAL6416A(i2c, _EXPANDER2_ADDR) if expander2_present else None
        if not expander2_present:
            print(
                "WARNING: external user-GPIO expander (addr {:#x}) not detected on I2C "
                "bus -- gpio_expander_pin(2, ...) disabled".format(_EXPANDER2_ADDR)
            )
        # Display control lines -- pin mode/initial level only; toggling happens in C.
        Pin(0, Pin.OUT, value=0)  # EPD_CL
        Pin(2, Pin.OUT, value=0)  # EPD_LE
        Pin(32, Pin.OUT, value=0)  # EPD_CKV
        Pin(33, Pin.OUT, value=1)  # EPD_SPH
        inkplate.select_board(_BOARD_VARIANT)
        inkplate.set_expander_write_cb(cls._expander_write_cb)

        cls.EPD_OE = GpioPin(cls._expander1, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._expander1, 1, mode_output)
        # EPD_SPV itself is never read again -- toggling happens in C via pin_spv in
        # board_config.c, which must stay pin 2 on this same expander (0x20) to match.
        # This call's job is the pin_mode(OUTPUT) side effect (see GpioPin), not the
        # object it returns.
        cls.EPD_SPV = GpioPin(cls._expander1, 2, mode_output)

        # Display data lines - we only use the Pin class to init the pins
        Pin(4, Pin.OUT)  # D0
        Pin(5, Pin.OUT)  # D1
        Pin(18, Pin.OUT)  # D2
        Pin(19, Pin.OUT)  # D3
        Pin(23, Pin.OUT)  # D4
        Pin(25, Pin.OUT)  # D5
        Pin(26, Pin.OUT)  # D6
        Pin(27, Pin.OUT)  # D7
        # TPS65186 power regulator control

        cls.TPS_WAKEUP = GpioPin(cls._expander1, 3, mode_output)
        cls.TPS_WAKEUP.digital_write(0)

        cls.TPS_PWRUP = GpioPin(cls._expander1, 4, mode_output)
        cls.TPS_PWRUP.digital_write(0)

        cls.TPS_VCOM = GpioPin(cls._expander1, 5, mode_output)
        cls.TPS_VCOM.digital_write(0)

        cls.TPS_INT = GpioPin(cls._expander1, 6, mode_input)
        cls.TPS_PWR_GOOD = GpioPin(cls._expander1, 7, mode_input)

        # Misc

        cls.GPIO0_PUP = GpioPin(cls._expander1, 8, mode_output)
        cls.GPIO0_PUP.digital_write(0)

        cls.VBAT_EN = GpioPin(cls._expander1, 9, mode_output)
        cls.VBAT_EN.digital_write(0)  # Initially disable the battery read

        cls.VBAT = ADC(Pin(35))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)

        # Pin 10 (and 11/12) is classic-only touchpads vs V2-only SD_ENABLE -- the real
        # Arduino reference driver puts both on the same expander pin per variant, they
        # aren't simultaneously present on either board.
        if _IS_CLASSIC:
            cls.TOUCH1 = GpioPin(cls._expander1, 10, mode_input)
            cls.TOUCH2 = GpioPin(cls._expander1, 11, mode_input)
            cls.TOUCH3 = GpioPin(cls._expander1, 12, mode_input)
        else:
            cls.SD_ENABLE = GpioPin(cls._expander1, 10, mode_output)

        cls._on = False  # whether panel is powered on or not

        if len(_Inkplate.byte2gpio) == 0:
            _Inkplate.gen_byte2gpio()

    # _expander_write_cb is invoked from C (epd_bitbang.c, via expander_bridge.c) to
    # toggle an expander-controlled line (currently only SPV) -- routes by I2C address
    # to whichever expander instance owns that address. Works for either chip since both
    # PCAL6416A and MCP23017 expose the same .addr / .digital_write(pin, value) shape.
    @classmethod
    def _expander_write_cb(cls, addr, pin, value):
        if addr == cls._expander1.addr:
            cls._expander1.digital_write(pin, value)
        elif cls._expander2 is not None and addr == cls._expander2.addr:
            cls._expander2.digital_write(pin, value)
        else:
            raise ValueError("no expander at addr {:#x}".format(addr))

    @classmethod
    def begin(cls):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        cls._tps = TPS65186(cls._i2c, cls.TPS_WAKEUP, cls.TPS_PWRUP, cls.TPS_VCOM)
        cls._tps.begin()
        cls._rtc = RTC(cls._i2c)

        cls.ipg = InkplateGS2()
        cls.ipm = InkplateMono()
        cls.ipp = InkplatePartial(cls.ipm)

    # Read the battery voltage. Note that the result depends on the ADC
    # calibration, and be a bit off.
    @classmethod
    def read_battery(cls):
        return read_battery_voltage(cls.VBAT, cls.VBAT_EN)

    # Read panel temperature via the TPS65186's internal sensor. Varies +- 1-2 degree.
    @classmethod
    def read_temperature(cls):
        return cls._tps.read_temperature()

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE)
    @classmethod
    def power_on(cls):
        if cls._on:
            return
        cls._on = True
        restore_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)
        if not cls._tps.power_up():
            raise RuntimeError("TPS65186 power-up timed out (PWR_GOOD not OK)")
        # wake-up display
        cls.EPD_GMODE.digital_write(1)
        cls.EPD_OE.digital_write(1)

        time.sleep_ms(50)

    # power_off puts the display to sleep and cuts the power
    @classmethod
    def power_off(cls):
        if not cls._on:
            return
        cls._on = False
        # put display to sleep
        cls.EPD_GMODE.digital_write(0)
        cls.EPD_OE.digital_write(0)

        cls._tps.power_down()
        # Tri-state the bit-banged control/data bus to stop current leakage during deep
        # sleep -- ported from the real Arduino reference driver's pinsZstate().
        tristate_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start/vscan_write/vscan_end/fill_screen are implemented in C
    # (firmware/usermods/inkplate/epd_bitbang.c), config-driven via board_config_t --
    # same names/signatures as Inkplate10, so inkplate_mono.py/inkplate_gs.py/
    # inkplate_partial.py need no changes.
    @classmethod
    def vscan_start(cls):
        inkplate.vscan_start()

    @classmethod
    def vscan_end(cls):
        inkplate.vscan_end()

    @staticmethod
    def vscan_write():
        inkplate.vscan_write()

    @classmethod
    def i2s_init(cls):
        inkplate.i2s_init()

    @classmethod
    def i2s_deinit(cls):
        inkplate.i2s_deinit()

    @staticmethod
    def mono_display(framebuf):
        inkplate.mono_display(framebuf)

    @staticmethod
    def gs_display(framebuf):
        inkplate.gs_display(framebuf)

    @staticmethod
    def partial_display(old_fb, new_fb):
        inkplate.partial_display(old_fb, new_fb)

    # byte2gpio converts a byte of data for the screen to 32 bits of gpio0..31
    # (oh, e-radionica, why didn't you group the gpios better?!)
    byte2gpio = []

    @classmethod
    def gen_byte2gpio(cls):
        cls.byte2gpio = array("L", bytes(4 * 256))
        for b in range(256):
            cls.byte2gpio[b] = (
                (b & 0x3) << 4 | (b & 0xC) << 16 | (b & 0x10) << 19 | (b & 0xE0) << 20
            )
        # sanity check that all EPD_DATA bits got set at some point and no more
        union = 0
        for i in range(256):
            union |= cls.byte2gpio[i]
        assert union == EPD_DATA

    @staticmethod
    def fill_screen(data: int):
        inkplate.fill_screen(data)

    # clean fills the screen with one of the four possible pixel patterns via I2S DMA.
    # Caller must have already called i2s_init() -- same precondition as
    # epd_i2s_push_frame/push_row (firmware/usermods/inkplate/epd_i2s.h).
    @classmethod
    def clean(cls, patt, rep):
        c = [0xAA, 0x55, 0x00, 0xFF][patt]
        for i in range(rep):
            inkplate.i2s_push_frame(c)

    @classmethod
    def rtc_set_time(cls, rtc_hour, rtc_minute, rtc_second):
        cls._rtc.set_time(rtc_hour, rtc_minute, rtc_second)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        cls._rtc.set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    @classmethod
    def rtc_get_rtc_data(cls):
        return cls._rtc.get_data()


from inkplate_partial import *
from inkplate_gs import *
from inkplate_mono import *


class Inkplate:
    # Inkplate wraper to make it more easy for use

    INKPLATE_1BIT = 0
    INKPLATE_2BIT = 1

    BLACK = 1
    WHITE = 0

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    display_mode = 0
    text_size = 1

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    def __init__(self, mode):
        self.display_mode = mode

    def begin(self):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        _Inkplate._tps = TPS65186(
            _Inkplate._i2c, _Inkplate.TPS_WAKEUP, _Inkplate.TPS_PWRUP, _Inkplate.TPS_VCOM
        )
        _Inkplate._tps.begin()
        _Inkplate._rtc = RTC(_Inkplate._i2c)

        self.ipg = InkplateGS2()
        self.ipm = InkplateMono()

        if self.display_mode == Inkplate.INKPLATE_2BIT:
            self.textColor = 0
        else:
            self.textColor = 1

        self.textWrapping = 1

        self.cursor = [0, 0]

        self.ipp = InkplatePartial(self.ipm)
        self.fullUpdateThreshold = 10
        self.partialUpdateCounter = 0

        self.clear_display()

        self.font_family = montserrat_black
        self.font = self.font_family._font

    def init_sd_card(self, fast_boot=False):
        # Classic v1 has no SD-card power MOSFET (confirmed against real hardware) --
        # SD is always powered, nothing to enable.
        if not _IS_CLASSIC:
            _Inkplate.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # Same SD wiring/expander as Inkplate10 (confirmed against the Arduino
                    # reference driver's sdCardInit(), same pins), so reusing Inkplate10's
                    # already-HIL-verified 4MHz value here too -- but that finding was
                    # specific to Inkplate10's own SD card/cable on that session's hardware
                    # (docs/REFACTOR-PLAN.md Phase 7 step 21); not yet independently
                    # confirmed on real Inkplate6 hardware. Re-verify during this step's
                    # HIL pass and raise if 4MHz proves unnecessarily conservative here.
                    freq=4000000,
                ),
                "/sd",
            )
            if fast_boot is True:
                if (
                    machine.reset_cause() == machine.PWRON_RESET
                    or machine.reset_cause() == machine.HARD_RESET
                    or machine.reset_cause() == machine.WDT_RESET
                ):
                    machine.soft_reset()

        except Exception:
            print("Sd card could not be read")

    def sd_card_sleep(self):
        if not _IS_CLASSIC:
            _Inkplate.SD_ENABLE.digital_write(1)
        time.sleep_ms(5)

    def sd_card_wake(self):
        if not _IS_CLASSIC:
            _Inkplate.SD_ENABLE.digital_write(0)
        time.sleep_ms(5)

    def touch1(self):
        return _Inkplate.TOUCH1.digital_read()

    def touch2(self):
        return _Inkplate.TOUCH2.digital_read()

    def touch3(self):
        return _Inkplate.TOUCH3.digital_read()

    def gpio_expander_pin(self, expander, pin, mode):
        if expander == 1:
            return GpioPin(_Inkplate._expander1, pin, mode)
        elif expander == 2:
            if _Inkplate._expander2 is None:
                raise RuntimeError(
                    "external user-GPIO expander (addr {:#x}) not present on this "
                    "board".format(_EXPANDER2_ADDR)
                )
            return GpioPin(_Inkplate._expander2, pin, mode)

    def clear_display(self):
        InkplateMono.clear(self.ipm._framebuf)
        InkplateGS2.clear(self.ipg._framebuf)

    def display(self):
        if self.display_mode == 0:
            self.ipm.display()
            self.ipp.start()
        elif self.display_mode == 1:
            self.ipg.display()

        self.ipp.start()  # making framebuffer copy for partial update

    def partial_update(self):
        if self.display_mode == 1:
            return
        else:
            if self.partialUpdateCounter < self.fullUpdateThreshold:
                self.partialUpdateCounter = self.partialUpdateCounter + 1
                self.ipp.display()
            else:
                self.partialUpdateCounter = 0
                self.ipm.display()
            self.ipp.start()

    def draw_polygon(self, x, y, coords, color):
        import array

        coords = array.array("I", coords)
        self.fbuf.poly(x, y, coords, color, 1)

    def fill(self, color):
        self.fbuf.fill(color)

    def set_full_update_threshold(self, new_threshold):
        self.fullUpdateThreshold = new_threshold

    def clean(self):
        self.eink_on()
        _Inkplate.i2s_init()
        _Inkplate.clean(0, 1)
        _Inkplate.clean(1, 18)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 18)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(1, 18)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 18)
        _Inkplate.i2s_deinit()
        self.eink_off()

    def eink_on(self):
        _Inkplate.power_on()

    def eink_off(self):
        _Inkplate.power_off()

    def read_battery(self):
        return _Inkplate.read_battery()

    def read_temperature(self):
        return _Inkplate.read_temperature()

    def width(self):
        return self._width

    def height(self):
        return self._height

    # Arduino compatibility functions
    def set_rotation(self, x):
        self.rotation = x % 4
        if self.rotation == 0 or self.rotation == 2:
            self._width = D_COLS
            self._height = D_ROWS
        elif self.rotation == 1 or self.rotation == 3:
            self._width = D_ROWS
            self._height = D_COLS

    def get_rotation(self):
        return self.rotation

    def draw_pixel(self, x, y, c):
        self.start_write()
        self.write_pixel(x, y, c)
        self.end_write()

    def start_write(self):
        pass

    @micropython.native
    def write_pixel(self, x, y, c):
        if self.display_mode == 0:
            Inkplate.write_pixel_viper(
                self.ipm._framebuf, x, y, c, self.rotation, self.display_mode
            )
        else:
            Inkplate.write_pixel_viper(
                self.ipg._framebuf, x, y, c, self.rotation, self.display_mode
            )

    @staticmethod
    @micropython.viper
    def write_pixel_viper(fb: ptr8, x: int, y: int, c: int, rot: int, display_mode: int):
        w = 800  # physical width
        h = 600  # physical height

        # Logical bounds (swap for 90°/270° so we never address past h)
        if rot & 1:  # 1 or 3 -> 90°/270°
            if x < 0 or y < 0 or x >= h or y >= w:
                return
        else:
            if x < 0 or y < 0 or x >= w or y >= h:
                return

        # Map (x,y) -> physical (px,py) inside w×h
        if rot == 0:  # 0°
            px = x
            py = y
        elif rot == 1:  # 90° CW
            px = y
            py = h - 1 - x
        elif rot == 2:  # 180°
            px = w - 1 - x
            py = h - 1 - y
        else:  # 270° CCW (rot == 3)
            px = w - 1 - y
            py = x
        if display_mode == 0:  # 1bpp
            idx = (py * w + px) >> 3  # 8 pixels per byte
            shift = px & 7
            if c:
                fb[idx] = fb[idx] | (1 << shift)
            else:
                fb[idx] = fb[idx] & ~(1 << shift)

        else:
            c &= 0x07  # raw 0-7 (3-bit/8-level storage, GS4_HMSB)

            # Find byte index (2 pixels/byte)
            byte_index = py * 400 + (px >> 1)

            # Which pixel inside this byte (0..1)
            pixel_index = px & 1
            shift = pixel_index * 4

            # Load current byte
            temp = fb[byte_index]

            # Clear and write the new pixel
            fb[byte_index] = (temp & int(pixel_mask_glut[pixel_index])) | (c << shift)

    def draw_bitmap(self, x, y, data, w, h, c=1):
        byte_width = (w + 7) // 8
        byte = 0
        self.start_write()
        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byte_width + i // 8]
                if byte & 0x80:
                    self.write_pixel(x + i, y + j, c)
        self.end_write()

    # write_fill_rect/write_fast_hline/write_fast_vline predate shared/gfx.py's GFX class
    # (GFX.fill_rect/hline/vline are bound to these, not the other way around) so they were
    # out of scope for the initial gfx C port -- ported here as a direct follow-up since
    # gfx_fill_rect/gfx_hline/gfx_vline already exist and are already tested: collapsing
    # these from an O(w*h)/O(n) per-pixel Python loop into a single C call is the actual win
    # (write_pixel itself is already a viper function, so it wasn't worth touching).
    def write_fill_rect(self, x, y, w, h, c):
        inkplate.gfx_fill_rect(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, w, h, c
        )

    def write_fast_vline(self, x, y, h, c):
        inkplate.gfx_vline(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, h, c
        )

    def write_fast_hline(self, x, y, w, c):
        inkplate.gfx_hline(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, w, c
        )

    # Active framebuf for the current display_mode -- shared by every gfx_* call below,
    # since C owns the whole draw now instead of a per-pixel Python callback.
    def _framebuf(self):
        return self.ipm._framebuf if self.display_mode == 0 else self.ipg._framebuf

    def write_line(self, x0, y0, x1, y1, c):
        inkplate.gfx_line(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x0, y0, x1, y1, c
        )

    def end_write(self):
        pass

    def draw_fast_vline(self, x, y, h, c):
        self.start_write()
        self.write_fast_vline(x, y, h, c)
        self.end_write()

    def draw_fast_hline(self, x, y, w, c):
        self.start_write()
        self.write_fast_hline(x, y, w, c)
        self.end_write()

    def fill_rect(self, x, y, w, h, c):
        self.start_write()
        self.write_fill_rect(x, y, w, h, c)
        self.end_write()

    def fill_screen(self, c):
        self.fill_rect(0, 0, self.width(), self.height(), c)

    def draw_line(self, x0, y0, x1, y1, c):
        self.start_write()
        self.write_line(x0, y0, x1, y1, c)
        self.end_write()

    def draw_rect(self, x, y, w, h, c):
        inkplate.gfx_rect(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, w, h, c
        )

    def draw_circle(self, x, y, r, c):
        inkplate.gfx_circle(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, r, c
        )

    def fill_circle(self, x, y, r, c):
        inkplate.gfx_fill_circle(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, r, c
        )

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_triangle(
            self._framebuf(),
            D_COLS,
            D_ROWS,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            c,
        )

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_fill_triangle(
            self._framebuf(),
            D_COLS,
            D_ROWS,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            c,
        )

    def draw_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_round_rect(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, q, h, r, c
        )

    def fill_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_fill_round_rect(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, q, h, r, c
        )

    def set_display_mode(self, mode):
        self.display_mode = mode

    def get_display_mode(self):
        return self.display_mode

    def set_text_size(self, s):
        self.text_size = s

    def set_font(self, f):
        self.font_family = f
        self.font = self.font_family._font

    def set_text_color(self, c):
        self.textColor = c

    def set_text_wrapping(self, state: bool):
        self.textWrapping = state

    def reset_cursor(self):
        self.cursor = [0, 0]

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    # Ported from shared/gfx.py GFX._print_text, with the per-char blit routed through
    # inkplate.gfx_draw_char instead of GFX._draw_char_1bpp/_draw_char_2bpp. Those two were
    # dispatched by a caller-supplied `bpp` kwarg that had drifted out of sync with the real
    # framebuf storage -- this version dispatches on self.display_mode instead, like every
    # other draw method here, so there is one packing decision instead of two that can
    # disagree.
    def _print_text(self, framebuf, x0, y0, string, size, color, text_wrap=False):
        display_width = self._width

        if self.display_mode == 0:
            color = 1 if color else 0
        else:
            color = min(max(color, 0), 7)

        x = int(x0)
        y = int(y0)
        line_height = 0

        def blit(cx, cy, char_data, ch_w, ch_h):
            inkplate.gfx_draw_char(
                framebuf,
                D_COLS,
                D_ROWS,
                self.rotation,
                self.display_mode,
                cx,
                cy,
                char_data,
                ch_w,
                ch_h,
                size,
                color,
            )

        for chunk in string.split("__"):
            try:
                char_data, ch_h, ch_w = self.font_family.get_ch(chunk)
                line_height = max(line_height, ch_h * size)

                if text_wrap is True and x + ch_w * size > display_width:
                    x = 0
                    y += line_height
                    line_height = ch_h * size

                blit(x, y, char_data, ch_w, ch_h)
                x += ch_w * size
            except (ValueError, TypeError):
                for char in chunk:
                    if char == "\n":
                        x = x0
                        y += line_height
                        line_height = 0
                        continue

                    try:
                        char_data, ch_h, ch_w = self.font_family.get_ch(char)
                    except (ValueError, TypeError):
                        char_data, ch_h, ch_w = self.font_family.get_ch("?")

                    line_height = max(line_height, ch_h * size)

                    if text_wrap is True and x + ch_w * size > display_width:
                        x = 0
                        y += line_height
                        line_height = ch_h * size

                    blit(x, y, char_data, ch_w, ch_h)
                    x += ch_w * size
        return [x, y], line_height

    def print_text(self, x, y, s):
        self._print_text(
            self._framebuf(), x, y, s, self.text_size, self.textColor, text_wrap=self.textWrapping
        )

    def println(self, text):
        self.cursor, line_height = self._print_text(
            self._framebuf(),
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )
        self.cursor[1] += line_height
        self.cursor[0] = 0

    def print(self, text):
        self.cursor, _ = self._print_text(
            self._framebuf(),
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )

    def wrap_text(self, text, max_chars):
        lines = []
        for paragraph in text.split("\n"):
            while len(paragraph) > max_chars:
                # Find last space within limit
                wrap_at = paragraph.rfind(" ", 0, max_chars)
                if wrap_at == -1:
                    wrap_at = max_chars
                lines.append(paragraph[:wrap_at])
                paragraph = paragraph[wrap_at:].lstrip()
            if paragraph:
                lines.append(paragraph)
        return lines

    def draw_text_box(self, x0, y0, x1, y1, text, line_height=20, text_size=None):
        if text_size is not None:
            self.set_text_size(text_size)
        max_width = x1 - x0
        char_width = 6 * self.text_size  # rough estimate
        max_chars = max_width // char_width
        lines = self.wrap_text(text, max_chars)
        y = y0
        for line in lines:
            if y > y1 - 2 * line_height:
                s = list(line)
                s[-1] = "."
                s[-2] = "."
                s[-3] = "."
                s = "".join(s)
                self.print_text(x0, y, s)
                break
            self.print_text(x0, y, line)
            y += line_height

    def draw_image(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """
        Draw an image from either web URL or local file system
        Args:
            path: Either a web URL (http/https) or local file path
            x0, y0: Coordinates for top-left corner of image
            dither: Whether to apply dithering
            kernel_type: Dithering kernel type (0=Floyd-Steinberg, etc.)
            invert: Invert colors
        """
        # Check if path is a web URL
        if path.startswith(("http://", "https://")):
            # Determine image type from URL
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_web(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            # Handle local file
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_sd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")

    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        return _Inkplate.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return _Inkplate.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_data(self):
        return _Inkplate.rtc_get_rtc_data()

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        bmp_size = os.stat(path)[6]
        bmp_data = bytearray(bmp_size)
        with open(path, "rb") as f:
            # os.stat + readinto into a pre-sized bytearray, not f.read(): MicroPython's
            # whole-file read() grows its buffer geometrically and can transiently need
            # more than the final size, MemoryError-ing on files a pre-sized allocation
            # handles fine.
            f.readinto(bmp_data)
        inkplate.bmp_draw_gs4(
            self._framebuf(),
            D_COLS,
            D_ROWS,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            bmp_data,
            invert,
            dither,
            kernel_type,
        )
        gc.collect()

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """Display a BMP image downloaded from the web

        Args:
            url (str): URL of the BMP image
            x0 (int): X position to start drawing
            y0 (int): Y position to start drawing
            invert (bool): Whether to invert colors
            dither (bool): Whether to apply dithering
            kernel_type (int): Dithering kernel (0=Floyd-Steinberg, 1=JJN, 2=Stucki, 3=Burkes)
        """
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            bmp_data = response.content
            response.close()
            inkplate.bmp_draw_gs4(
                self._framebuf(),
                D_COLS,
                D_ROWS,
                self.rotation,
                self.display_mode,
                x0,
                y0,
                bmp_data,
                invert,
                dither,
                kernel_type,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        with open(path, "rb") as f:
            png_data = f.read()
        inkplate.png_draw_gs4(
            self._framebuf(),
            D_COLS,
            D_ROWS,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            png_data,
            invert,
            dither,
            kernel_type,
        )
        gc.collect()

    def draw_png_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()
            inkplate.png_draw_gs4(
                self._framebuf(),
                D_COLS,
                D_ROWS,
                self.rotation,
                self.display_mode,
                x0,
                y0,
                png_data,
                invert,
                dither,
                kernel_type,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def draw_jpg_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        with open(path, "rb") as f:
            jpg_data = f.read()
        inkplate.jpeg_draw_gs4(
            self._framebuf(),
            D_COLS,
            D_ROWS,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            jpg_data,
            invert,
            dither,
            kernel_type,
        )
        gc.collect()

    def draw_jpg_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import urequests

        try:
            response = urequests.get(url, timeout=20)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            jpg_data = response.content
            response.close()
            inkplate.jpeg_draw_gs4(
                self._framebuf(),
                D_COLS,
                D_ROWS,
                self.rotation,
                self.display_mode,
                x0,
                y0,
                jpg_data,
                invert,
                dither,
                kernel_type,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_jpg_from_web:", e)
            if "response" in locals():
                response.close()
            raise


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
