"""MicroPython driver for the Inkplate 6 e-paper display."""

import time
import os
import inkplate
import framebuf
from machine import ADC, I2C, Pin, SDCard
from pcal6416a import *
from mcp23017 import MCP23017
from tps65186 import TPS65186, read_battery_voltage
from rtc import RTC
from epd_power_pins import tristate_display_pins, restore_display_pins
from micropython import const
from inkplate_gfx_mixin import GfxMixin
from inkplate_text_mixin import TextMixin
from inkplate_image_gs4_mixin import ImageGS4Mixin
import gfx_standard_font_01 as montserrat_black
import gc


import machine

machine.freq(240000000)
# Raw display constants for Inkplate 6
D_ROWS = const(600)
D_COLS = const(800)

# Valid hardware variants for this driver. INKPLATE6V2's internal expander
# (OE/GMODE/SPV/TPS_*/etc, addr 0x20) is a PCAL6416A; classic INKPLATE6V1's
# same-role expander is an MCP23017. External expander addr also differs
# (v1=0x22, V2=0x21). Pass variant="inkplate6v1" to Inkplate() if your board is
# the original (non-V2) revision -- that also enables TOUCH1/2/3 (v1-only,
# same expander pins 10/11/12 that V2 repurposes for SD_ENABLE). Can't be
# auto-detected: neither expander chip exposes an ID/WHOAMI register to probe
# for which one is present.
_DEFAULT_VARIANT = "inkplate6v2"
_VALID_VARIANTS = ("inkplate6v1", "inkplate6v2")

# Inkplate provides access to the pins of the Inkplate 6 as well as to low-level display
# functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c, variant=_DEFAULT_VARIANT):
        if variant not in _VALID_VARIANTS:
            raise ValueError(
                "unknown Inkplate6 variant {!r}, must be one of {}".format(variant, _VALID_VARIANTS)
            )
        cls._variant = variant
        cls._is_classic = variant != "inkplate6v2"
        cls._expander2_addr = 0x22 if cls._is_classic else 0x21

        cls._i2c = i2c
        # External user-GPIO expander is a separate chip from the required internal one
        # (0x20, drives EPD_OE/GMODE/SPV/TPS_*) and some boards ship without it due to
        # chip shortages -- scan first so a missing chip disables gpio_expander_pin(2, ...)
        # instead of NACKing the eager MCP23017.__init__ I2C write and crashing begin().
        detected = i2c.scan()
        expander2_present = cls._expander2_addr in detected
        if cls._is_classic:
            cls._expander1 = MCP23017(i2c)
            cls._expander2 = MCP23017(i2c, cls._expander2_addr) if expander2_present else None
        else:
            cls._expander1 = PCAL6416A(i2c)
            cls._expander2 = PCAL6416A(i2c, cls._expander2_addr) if expander2_present else None
        if not expander2_present:
            print(
                "WARNING: external user-GPIO expander (addr {:#x}) not detected on I2C "
                "bus -- gpio_expander_pin(2, ...) disabled".format(cls._expander2_addr)
            )
        # Display control lines -- pin mode/initial level only; toggling happens in C.
        Pin(0, Pin.OUT, value=0)  # EPD_CL
        Pin(2, Pin.OUT, value=0)  # EPD_LE
        Pin(32, Pin.OUT, value=0)  # EPD_CKV
        Pin(33, Pin.OUT, value=1)  # EPD_SPH
        inkplate.select_board(variant)
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

        # Pin 10 (and 11/12) is classic-only touchpads vs V2-only SD_ENABLE --
        # both roles share the same expander pin per variant; they aren't
        # simultaneously present on either board.
        if cls._is_classic:
            cls.TOUCH1 = GpioPin(cls._expander1, 10, mode_input)
            cls.TOUCH2 = GpioPin(cls._expander1, 11, mode_input)
            cls.TOUCH3 = GpioPin(cls._expander1, 12, mode_input)
        else:
            cls.SD_ENABLE = GpioPin(cls._expander1, 10, mode_output)

        cls._on = False  # whether panel is powered on or not

    # _expander_write_cb is invoked from C (epd_control.c, via expander_bridge.c) to
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

    # Read the battery voltage. Result depends on ADC calibration and may be
    # a bit off.
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
        # Tri-state the bit-banged control/data bus to stop current leakage
        # during deep sleep.
        tristate_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start/vscan_write/vscan_end/fill_screen are implemented in C
    # (firmware/usermods/inkplate/epd_control.c), config-driven via board_config_t.
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


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean-cycle rep counts here are specific to this board -- not a
        # copy-paste bug.
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)
        ip.clean(2, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)

        # The display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 6 phases driven in C.
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    def clear(fb):
        inkplate.gfx_buf_fill(fb, 0x00)


class InkplateGS2(framebuf.FrameBuffer):
    """Inkplate display driver: 8-level (3-bit) grayscale storage (GS4_HMSB, raw 0-7).

    The C engine (firmware/usermods/inkplate/epd_i2s.c, waveform.c) drives the
    3-bit/8-level waveform table natively -- no intermediate fold.
    """

    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 2)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.GS4_HMSB)

    # display sends the grayscale buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean-cycle sequence is identical to display1b()'s on this board.
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)
        ip.clean(2, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)

        # The display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # Trailing park sequence.
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    def clear(fb):
        inkplate.gfx_buf_fill(fb, 0x77)  # both nibbles = raw level 7 (white)


class InkplatePartial:
    """Manages partial display updates by diffing framebuffer copies.

    It starts by making a copy of the current framebuffer, then when asked to draw
    renders the differences between the copy and the new framebuffer state. The
    constructor needs a reference to the current/main display object
    (InkplateMono); only InkplateMono is supported at the moment.
    """

    def __init__(self, base):
        self._base = base
        self._framebuf = bytearray(len(base._framebuf))

    # start makes a reference copy of the current framebuffer
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer contents
    # -- runs over I2S DMA in C (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame). Always walks the full frame (no region params):
    # unchanged pixels get a skip code from the diff, there's no row-range
    # transmission shortcut over I2S.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        t0 = time.ticks_ms()
        ip.partial_display(self._framebuf, self._base._framebuf)
        t1 = time.ticks_ms()

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

        td = time.ticks_diff(t1, t0)
        print("Partial: draw %dms" % td)


# gfx/text/image draw methods come from the shared inkplate_{gfx,text,
# image_gs4}_mixin.py modules. self._d_cols/self._d_rows (set in __init__) must
# be set before any draw call runs, since the mixins read those instead of
# D_COLS/D_ROWS directly.
class Inkplate(GfxMixin, TextMixin, ImageGS4Mixin):
    # Inkplate wrapper class for easier use

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

    def __init__(self, mode, variant=_DEFAULT_VARIANT):
        self.display_mode = mode
        self._variant = variant
        self._d_cols = D_COLS
        self._d_rows = D_ROWS

    def begin(self):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)), self._variant)

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
        # Classic v1 has no SD-card power MOSFET -- SD is always powered,
        # nothing to enable.
        if not _Inkplate._is_classic:
            _Inkplate.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # 4MHz SD clock is a conservative value carried over from another
                    # board's verified setup, not yet independently confirmed on this
                    # board's hardware -- safe to try raising if it proves
                    # unnecessarily conservative.
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
        if not _Inkplate._is_classic:
            _Inkplate.SD_ENABLE.digital_write(1)
        time.sleep_ms(5)

    def sd_card_wake(self):
        if not _Inkplate._is_classic:
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
                    "external user-GPIO expander (addr {:#x}) not present on this board".format(
                        _Inkplate._expander2_addr
                    )
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

    # API compatibility functions
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

    # Active framebuf for the current display_mode -- shared by every gfx_* call
    # in GfxMixin/TextMixin/ImageGS4Mixin.
    def _framebuf(self):
        return self.ipm._framebuf if self.display_mode == 0 else self.ipg._framebuf

    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        return _Inkplate.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return _Inkplate.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_data(self):
        return _Inkplate.rtc_get_rtc_data()


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
