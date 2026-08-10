"""MicroPython driver for the Inkplate 5 and Inkplate 5V2 e-paper displays."""

import time
import os
import inkplate
import framebuf
from machine import ADC, I2C, Pin, SDCard
from pcal6416a import *
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

# Valid hardware variants for this driver. Both boards use a single PCAL6416A internal
# expander at 0x20 (confirmed -- unlike Inkplate6/6V2's MCP23017-vs-PCAL6416A split,
# there's no free expander-chip signal to auto-detect this pair by) and neither has a
# separate external expander. No known electrical signal distinguishes them, so unlike
# inkplate6.py/inkplate10.py, variant must be passed explicitly -- there is no
# _detect_variant() here.
_VALID_VARIANTS = ("inkplate5v1", "inkplate5v2")

# Raw display constants (rows, cols) per variant.
_DIMENSIONS = {
    "inkplate5v1": (540, 960),
    "inkplate5v2": (720, 1280),
}

# Inkplate5V2's panel data-shift-register scans columns opposite to Inkplate6/10's, so
# every pixel/shape/text primitive (all of which funnel through gfx.c's gfx_set_pixel)
# needs the same horizontal flip. Classic Inkplate5's scan direction relative to
# Inkplate5V2 is UNCONFIRMED on real hardware -- False here is provisional, based on
# the mirrored-text symptom seen running the V2 board config on real v1 hardware.
# Verify on a real v1 panel before trusting non-mirrored output.
_MIRROR_X = {
    "inkplate5v1": False,
    "inkplate5v2": True,
}

# Pre-refresh clean-cycle rep count, from upstream Arduino's display1b()/display3b()
# clean() calls (clean(1, N)/clean(0, N) pairs) -- 14 for classic Inkplate5, 11 for
# Inkplate5V2. Separate from board_config_t's partial_reps (a different, C-side rep
# count for partialUpdate's I2S transfer loop).
_CLEAN_REPS = {
    "inkplate5v1": 14,
    "inkplate5v2": 11,
}

# Classic Inkplate5's upstream Arduino clean sequence has one extra trailing
# clean(2, 1) discharge pulse that Inkplate5V2's doesn't (9 calls vs 8) -- see the
# board's own display1b()/display3b() clean() call sequence.
_CLEAN_TRAILING_DISCHARGE = {
    "inkplate5v1": True,
    "inkplate5v2": False,
}


# Inkplate provides access to the pins of the Inkplate 5/5V2 as well as to low-level
# display functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c, variant):
        if variant not in _VALID_VARIANTS:
            raise ValueError(
                "unknown Inkplate5 variant {!r}, must be one of {} -- this board pair has no "
                "electrical auto-detect signal, so variant must always be passed "
                "explicitly".format(variant, _VALID_VARIANTS)
            )
        cls._variant = variant
        cls._clean_reps = _CLEAN_REPS[variant]
        cls._clean_trailing_discharge = _CLEAN_TRAILING_DISCHARGE[variant]
        cls._i2c = i2c
        # Both Inkplate5 and Inkplate5V2 have only one PCAL6416A expander (at 0x20) --
        # unlike Inkplate6/6V2 there's no separate external expander at 0x21/0x22; this
        # same chip also carries TPS_*/VBAT_EN/SD_ENABLE.
        cls._PCAL6416A = PCAL6416A(i2c)
        # Display control lines -- pin mode/initial level only; toggling happens in C.
        Pin(0, Pin.OUT, value=0)  # EPD_CL
        Pin(2, Pin.OUT, value=0)  # EPD_LE
        Pin(32, Pin.OUT, value=0)  # EPD_CKV
        Pin(33, Pin.OUT, value=1)  # EPD_SPH
        inkplate.select_board(variant)
        inkplate.set_expander_write_cb(cls._expander_write_cb)
        inkplate.gfx_set_mirror_x(_MIRROR_X[variant])

        cls.EPD_OE = GpioPin(cls._PCAL6416A, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._PCAL6416A, 1, mode_output)
        # EPD_SPV itself is never read again -- toggling happens in C via pin_spv in
        # board_config.c, which must stay pin 2 on this same expander (0x20) to match.
        # This call's job is the pin_mode(OUTPUT) side effect, not the object it
        # returns.
        cls.EPD_SPV = GpioPin(cls._PCAL6416A, 2, mode_output)

        # Display data lines - we only use the Pin class to init the pins.
        Pin(4, Pin.OUT)  # D0
        Pin(5, Pin.OUT)  # D1
        Pin(18, Pin.OUT)  # D2
        Pin(19, Pin.OUT)  # D3
        Pin(23, Pin.OUT)  # D4
        Pin(25, Pin.OUT)  # D5
        Pin(26, Pin.OUT)  # D6
        Pin(27, Pin.OUT)  # D7
        # TPS65186 power regulator control

        cls.TPS_WAKEUP = GpioPin(cls._PCAL6416A, 3, mode_output)
        cls.TPS_WAKEUP.digital_write(0)

        cls.TPS_PWRUP = GpioPin(cls._PCAL6416A, 4, mode_output)
        cls.TPS_PWRUP.digital_write(0)

        cls.TPS_VCOM = GpioPin(cls._PCAL6416A, 5, mode_output)
        cls.TPS_VCOM.digital_write(0)

        cls.TPS_INT = GpioPin(cls._PCAL6416A, 6, mode_input)
        cls.TPS_PWR_GOOD = GpioPin(cls._PCAL6416A, 7, mode_input)

        # Misc

        cls.GPIO0_PUP = GpioPin(cls._PCAL6416A, 8, mode_output)
        cls.GPIO0_PUP.digital_write(0)

        cls.VBAT_EN = GpioPin(cls._PCAL6416A, 9, mode_output)
        cls.VBAT_EN.digital_write(0)  # Initially disable the battery read

        cls.VBAT = ADC(Pin(35))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)

        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, 10, mode_output)

        cls._on = False  # Whether panel is powered on or not

    # _expander_write_cb is invoked from C (epd_control.c, via expander_bridge.c) to
    # toggle a PCAL6416A-controlled line (currently only SPV) -- only one expander on
    # this board, unlike Inkplate6/6V2's two.
    @classmethod
    def _expander_write_cb(cls, addr, pin, value):
        if addr == cls._PCAL6416A.addr:
            cls._PCAL6416A.digital_write(pin, value)
        else:
            raise ValueError("no expander at addr {:#x}".format(addr))

    # Read the battery voltage. Note that the result depends on the ADC
    # calibration, and be a bit off.
    @classmethod
    def read_battery(cls):
        return read_battery_voltage(cls.VBAT, cls.VBAT_EN)

    # Read panel temperature via the TPS65186's internal sensor. Varies +- 1-2 degree.
    @classmethod
    def read_temperature(cls):
        return cls._tps.read_temperature()

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE).
    @classmethod
    def power_on(cls):
        if cls._on:
            return
        cls._on = True
        restore_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)
        if not cls._tps.power_up():
            raise RuntimeError("TPS65186 power-up timed out (PWR_GOOD not OK)")
        # Wake-up display
        cls.EPD_GMODE.digital_write(1)
        cls.EPD_OE.digital_write(1)

        time.sleep_ms(50)

    # power_off puts the display to sleep and cuts the power.
    @classmethod
    def power_off(cls):
        if not cls._on:
            return
        cls._on = False
        # Put display to sleep.
        cls.EPD_GMODE.digital_write(0)
        cls.EPD_OE.digital_write(0)

        cls._tps.power_down()
        # Tri-state the bit-banged control/data bus to stop current leakage during
        # deep sleep.
        tristate_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start/vscan_write/vscan_end/fill_screen are implemented in C
    # (firmware/usermods/inkplate/epd_control.c), config-driven via board_config_t --
    # same names/signatures as Inkplate10/6, so inkplate_mono.py/inkplate_gs.py/
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

    # pre_clean runs the pre-refresh clean-cycle sequence shared by InkplateMono.display,
    # InkplateGS4.display, and Inkplate.clean() -- rep count and the extra trailing
    # discharge pulse are variant-specific (see _CLEAN_REPS/_CLEAN_TRAILING_DISCHARGE).
    @classmethod
    def pre_clean(cls):
        n = cls._clean_reps
        cls.clean(0, 1)
        cls.clean(1, n)
        cls.clean(2, 1)
        cls.clean(0, n)
        cls.clean(2, 1)
        cls.clean(1, n)
        cls.clean(2, 1)
        cls.clean(0, n)
        if cls._clean_trailing_discharge:
            cls.clean(2, 1)

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
    def __init__(self, d_rows, d_cols):
        self._framebuf = bytearray(d_rows * d_cols // 8)
        super().__init__(self._framebuf, d_cols, d_rows, framebuf.MONO_HMSB)

    # display sends the monochrome buffer to the display, clearing it first.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean the display (I2S DMA); rep count is variant-specific (see _CLEAN_REPS).
        t0 = time.ticks_ms()
        ip.pre_clean()

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


class InkplateGS4(framebuf.FrameBuffer):
    """Inkplate display driver: 8-level (3-bit) grayscale storage (GS4_HMSB, raw 0-7).

    The C engine (firmware/usermods/inkplate/epd_i2s.c, waveform.c) drives the real
    3-bit/8-level waveform table natively -- no intermediate fold.
    """

    def __init__(self, d_rows, d_cols):
        self._framebuf = bytearray(d_rows * d_cols // 2)
        super().__init__(self._framebuf, d_cols, d_rows, framebuf.GS4_HMSB)

    # display sends the grayscale buffer to the display, clearing it first.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean the display (I2S DMA); same sequence as display1b() on this board --
        # rep count is variant-specific (see _CLEAN_REPS).
        t0 = time.ticks_ms()
        ip.pre_clean()

        # The display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS4: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # Trailing park sequence -- unlike Inkplate6, this board deliberately omits a
        # trailing vscan_start() call here.
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    def clear(fb):
        inkplate.gfx_buf_fill(fb, 0x77)  # Both nibbles = raw level 7 (white)


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

    # start makes a reference copy of the current framebuffer.
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer
    # contents -- runs over I2S DMA in C (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame), matching how mono/GS/clean already work. Always
    # walks the full frame (no region params): unchanged pixels get a skip code from
    # the diff, so there's no row-range transmission shortcut over I2S. Reps driven by
    # board_config_t's partial_reps (6 for Inkplate5, 4 for Inkplate5V2).
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


# gfx/text/image draw methods come from shared/mixins/inkplate_{gfx,text,image_gs4}_mixin.py
# (same shared code as inkplate10/6/6plusv2/6flick/4tempera). self._d_cols/
# self._d_rows must be set (done in __init__) before any draw call runs, or drawing
# will be offset. This board's gfx_set_mirror_x column-flip (variant-specific, set in
# _Inkplate.init) still applies to every gfx_* call the mixin makes.
class Inkplate(GfxMixin, TextMixin, ImageGS4Mixin):
    # Inkplate wrapper to make it easier to use.

    INKPLATE_1BIT = 0
    INKPLATE_2BIT = 1

    BLACK = 1
    WHITE = 0

    rotation = 0
    display_mode = 0
    text_size = 1

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    # variant has no default -- this board pair has no electrical auto-detect signal
    # (see _VALID_VARIANTS), so the caller must always state which hardware it's
    # running on. Pass "inkplate5v1" (classic, 960x540) or "inkplate5v2" (1280x720).
    def __init__(self, mode, variant):
        if variant not in _VALID_VARIANTS:
            raise ValueError(
                "unknown Inkplate5 variant {!r}, must be one of {}".format(variant, _VALID_VARIANTS)
            )
        self.display_mode = mode
        self._variant = variant
        self._d_rows, self._d_cols = _DIMENSIONS[variant]
        self._width = self._d_cols
        self._height = self._d_rows

    def begin(self):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)), self._variant)

        _Inkplate._tps = TPS65186(
            _Inkplate._i2c, _Inkplate.TPS_WAKEUP, _Inkplate.TPS_PWRUP, _Inkplate.TPS_VCOM
        )
        _Inkplate._tps.begin()
        _Inkplate._rtc = RTC(_Inkplate._i2c)

        self.ipg = InkplateGS4(self._d_rows, self._d_cols)
        self.ipm = InkplateMono(self._d_rows, self._d_cols)

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
        _Inkplate.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # Same SD wiring/pins as Inkplate6/10.
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
        _Inkplate.SD_ENABLE.digital_write(1)
        time.sleep_ms(5)

    def sd_card_wake(self):
        _Inkplate.SD_ENABLE.digital_write(0)
        time.sleep_ms(5)

    def gpio_expander_pin(self, expander, pin, mode):
        return GpioPin(_Inkplate._PCAL6416A, pin, mode)

    def clear_display(self):
        InkplateMono.clear(self.ipm._framebuf)
        InkplateGS4.clear(self.ipg._framebuf)

    def display(self):
        if self.display_mode == 0:
            self.ipm.display()
            self.ipp.start()
        elif self.display_mode == 1:
            self.ipg.display()

        self.ipp.start()  # Making framebuffer copy for partial update

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
        # Burn-in sequence; rep count is variant-specific (see _CLEAN_REPS).
        _Inkplate.pre_clean()
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

    # Rotation helpers (kept for API compatibility).
    def set_rotation(self, x):
        self.rotation = x % 4
        if self.rotation == 0 or self.rotation == 2:
            self._width = self._d_cols
            self._height = self._d_rows
        elif self.rotation == 1 or self.rotation == 3:
            self._width = self._d_rows
            self._height = self._d_cols

    def get_rotation(self):
        return self.rotation

    # Active framebuf for the current display_mode -- shared by every gfx_* call in
    # GfxMixin/TextMixin/ImageGS4Mixin, since C owns the whole draw instead of a
    # per-pixel Python callback.
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
