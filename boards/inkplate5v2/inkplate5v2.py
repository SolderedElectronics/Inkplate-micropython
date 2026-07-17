"""MicroPython driver for the Inkplate 5V2 e-paper display."""

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
# Raw display constants for Inkplate 5V2
D_ROWS = const(720)
D_COLS = const(1280)


# Inkplate provides access to the pins of the Inkplate 5V2 as well as to low-level
# display functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c):
        cls._i2c = i2c
        # Inkplate5V2 has only one PCAL6416A expander (IO_INT_ADDR = 0x20 in the Arduino
        # reference's pins.h) -- unlike Inkplate6/6V2 there's no separate external
        # expander at 0x21/0x22, this same chip also carries TPS_*/VBAT_EN/SD_ENABLE.
        cls._PCAL6416A = PCAL6416A(i2c)
        # Display control lines -- pin mode/initial level only; toggling happens in C.
        Pin(0, Pin.OUT, value=0)  # EPD_CL
        Pin(2, Pin.OUT, value=0)  # EPD_LE
        Pin(32, Pin.OUT, value=0)  # EPD_CKV
        Pin(33, Pin.OUT, value=1)  # EPD_SPH
        inkplate.select_board("inkplate5v2")
        inkplate.set_expander_write_cb(cls._expander_write_cb)
        # This panel scans columns opposite to Inkplate6/10's -- every pixel/shape/text
        # primitive funnels through gfx.c's gfx_set_pixel, which needs the same flip
        # (HIL-confirmed on basic_bw.py's logo).
        inkplate.gfx_set_mirror_x(True)

        cls.EPD_OE = GpioPin(cls._PCAL6416A, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._PCAL6416A, 1, mode_output)
        # EPD_SPV itself is never read again -- toggling happens in C via pin_spv in
        # board_config.c, which must stay pin 2 on this same expander (0x20) to match.
        # This call's job is the pin_mode(OUTPUT) side effect (see PCAL6416A.GpioPin),
        # not the object it returns.
        cls.EPD_SPV = GpioPin(cls._PCAL6416A, 2, mode_output)

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

        cls._on = False  # whether panel is powered on or not

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

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed from the real Arduino
        # Inkplate5V2Driver.cpp display1b() -- 11, not Inkplate6's 18 (own reference
        # driver, own value, same precedent as step 22).
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)

        # the display gets written via I2S DMA + the C waveform engine
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

    The C engine (firmware/usermods/inkplate/epd_i2s.c, waveform.c) drives the real
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

        # clean the display (I2S DMA), reps transcribed from the real Arduino
        # Inkplate5V2Driver.cpp display3b() -- identical sequence to display1b() on this
        # board (11 reps, own reference driver's own value, not Inkplate6's 18).
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display3b() -- unlike
        # Inkplate6, Inkplate5V2's own display3b() has its trailing vscan_start() call
        # commented out (never executed), so it's deliberately not ported here either.
        ip.clean(3, 1)
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
    # -- runs over I2S DMA in C now (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame), matching how mono/GS/clean already work. Always walks
    # the full frame (no region params) -- matches the real Arduino reference driver's
    # partialUpdate(), which has none either: unchanged pixels get a skip code from the
    # diff, there's no row-range transmission shortcut over I2S. Reps driven by
    # board_config_t's partial_reps (4 for Inkplate5V2, transcribed from
    # Inkplate5V2Driver.cpp's own partialUpdate() for(k<4) loop).
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


# NEEDS HW TEST: gfx/text/image draw methods now come from shared/inkplate_{gfx,text,
# image_gs4}_mixin.py (same shared code as inkplate10/6/6plusv2/6flick/4tempera).
# Extraction was byte-identical to the prior inline code; only self._d_cols/
# self._d_rows (set in __init__) replace the old direct D_COLS/D_ROWS references. If
# drawing looks offset/corrupted, check those two got set before any draw call runs.
# This board's gfx_set_mirror_x(True) column-flip (set in _Inkplate.init) is untouched
# and still applies to every gfx_* call the mixin makes.
class Inkplate(GfxMixin, TextMixin, ImageGS4Mixin):
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
        self._d_cols = D_COLS
        self._d_rows = D_ROWS

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
        _Inkplate.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # Same SD wiring/expander pin as Inkplate6/10 (confirmed against the
                    # Arduino reference driver's sdCardInit(), same pins) -- reusing the
                    # already-HIL-verified 4MHz value; re-verify on real Inkplate5V2
                    # hardware during this step's HIL pass.
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
        # Reps transcribed from the real Arduino Inkplate5V2Driver.cpp display1b()/
        # display3b() burn-in sequence (11, not Inkplate6's 18 -- own reference driver,
        # own value, same precedent as step 22).
        _Inkplate.clean(0, 1)
        _Inkplate.clean(1, 11)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 11)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(1, 11)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 11)
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

    # Active framebuf for the current display_mode -- shared by every gfx_* call in
    # GfxMixin/TextMixin/ImageGS4Mixin, since C owns the whole draw now instead of a
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
