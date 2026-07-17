"""MicroPython driver for the Inkplate 6PLUS (V2 revision) e-paper display.

Display-path + SD card + battery/temperature + touch. setVCOM/writeVCOMToPanelEEPROM/
getStoredVCOM/getVCOMValue are not implemented. Only the V2 hardware revision is wired
here (IO_EXT_ADDR 0x21); the classic (non-V2) INKPLATE6PLUS uses 0x22 there and isn't
supported by this file -- touch is unaffected by that split (its own
TOUCHSCREEN_IO_EXPANDER is IO_INT_ADDR, 0x20, the same on both revisions). Touch (Elan
controller, shared with Inkplate4TEMPERA) and frontlight (shared with Inkplate4TEMPERA/
6FLICK) are also wired here.
"""

import time
import os
import inkplate
import framebuf
from machine import ADC, I2C, Pin, SDCard
from pcal6416a import *
from tps65186 import TPS65186, read_battery_voltage_autodetect
from rtc import RTC
from epd_power_pins import tristate_display_pins, restore_display_pins
from touch_elan import Touch
from frontlight import Frontlight
from micropython import const
from inkplate_gfx_mixin import GfxMixin
from inkplate_text_mixin import TextMixin
from inkplate_image_gs4_mixin import ImageGS4Mixin
import gfx_standard_font_01 as montserrat_black
import gc


import machine

machine.freq(240000000)
# Raw display constants for Inkplate 6PLUS -- same panel as Inkplate6FLICK (1024x758).
D_ROWS = const(758)
D_COLS = const(1024)

# IO_EXT_ADDR 0x21 is for the V2 revision this file targets (0x22 for the classic/
# non-V2 board, not wired here). Not currently used for touch -- the expander object
# below exists only so expander_bridge_write() can route to it if needed.
_EXPANDER2_ADDR = 0x21

# Inkplate provides access to the pins of the Inkplate 6PLUS as well as to low-level
# display functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c):
        cls._i2c = i2c
        cls._PCAL6416A_1 = PCAL6416A(i2c)
        cls._PCAL6416A_2 = PCAL6416A(i2c, _EXPANDER2_ADDR)
        # Display control lines -- pin mode/initial level only; toggling happens in C.
        Pin(0, Pin.OUT, value=0)  # EPD_CL
        Pin(2, Pin.OUT, value=0)  # EPD_LE
        Pin(32, Pin.OUT, value=0)  # EPD_CKV
        Pin(33, Pin.OUT, value=1)  # EPD_SPH
        inkplate.select_board("inkplate6plusv2")
        inkplate.set_expander_write_cb(cls._expander_write_cb)

        cls.EPD_OE = GpioPin(cls._PCAL6416A_1, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._PCAL6416A_1, 1, mode_output)
        # EPD_SPV itself is never read again -- toggling happens in C via pin_spv in
        # board_config.c, which must stay pin 2 on this same expander (0x20) to match.
        # This call's job is the pin_mode(OUTPUT) side effect (see PCAL6416A.GpioPin),
        # not the object it returns.
        cls.EPD_SPV = GpioPin(cls._PCAL6416A_1, 2, mode_output)

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

        cls.TPS_WAKEUP = GpioPin(cls._PCAL6416A_1, 3, mode_output)
        cls.TPS_WAKEUP.digital_write(0)

        cls.TPS_PWRUP = GpioPin(cls._PCAL6416A_1, 4, mode_output)
        cls.TPS_PWRUP.digital_write(0)

        cls.TPS_VCOM = GpioPin(cls._PCAL6416A_1, 5, mode_output)
        cls.TPS_VCOM.digital_write(0)

        # Battery-read ADC -- this pin's resting state auto-detects PMOS-only (older
        # board) vs PMOS+NMOS (newer board) polarity, so its mode flips between
        # input/output on every read (see read_battery below); no fixed-mode GpioPin
        # wrapper here, just the pin number on the same expander.
        cls.VBAT_EN_PIN = 9
        cls.VBAT = ADC(Pin(35))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)

        # SD card P-MOS enable -- pin 13 (SD_PMOS_PIN / IO_PIN_B5), on this same
        # expander (0x20). Different pin number from Inkplate6/5v2's own SD_ENABLE
        # (pin 10) -- board-specific wiring.
        cls.SD_ENABLE = GpioPin(cls._PCAL6416A_1, 13, mode_output)

        cls._on = False  # whether panel is powered on or not

    # _expander_write_cb is invoked from C (epd_control.c, via expander_bridge.c) to
    # toggle a PCAL6416A-controlled line (currently only SPV) -- routes by I2C address
    # to whichever expander instance owns that address.
    @classmethod
    def _expander_write_cb(cls, addr, pin, value):
        if addr == cls._PCAL6416A_1.addr:
            cls._PCAL6416A_1.digital_write(pin, value)
        elif addr == cls._PCAL6416A_2.addr:
            cls._PCAL6416A_2.digital_write(pin, value)
        else:
            raise ValueError("no expander at addr {:#x}".format(addr))

    # Read the battery voltage. Note that the result depends on the ADC
    # calibration, and be a bit off.
    @classmethod
    def read_battery(cls):
        return read_battery_voltage_autodetect(cls._PCAL6416A_1, cls.VBAT, cls.VBAT_EN_PIN)

    # Read panel temperature via the TPS65186's internal sensor. Varies +- 1-2 degree.
    @classmethod
    def read_temperature(cls):
        return cls._tps.read_temperature()

    @classmethod
    def rtc_set_time(cls, rtc_hour, rtc_minute, rtc_second):
        cls._rtc.set_time(rtc_hour, rtc_minute, rtc_second)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        cls._rtc.set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    @classmethod
    def rtc_get_rtc_data(cls):
        return cls._rtc.get_data()

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE).
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

    # power_off puts the display to sleep and cuts the power.
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
        # sleep.
        tristate_display_pins(cls.EPD_OE, cls.EPD_GMODE, cls.EPD_SPV)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start/vscan_write/vscan_end/fill_screen are implemented in C
    # (firmware/usermods/inkplate/epd_control.c), config-driven via board_config_t --
    # same names/signatures as Inkplate10/6/5v2/6FLICK, so inkplate_mono.py/
    # inkplate_gs.py/inkplate_partial.py need no changes.
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


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first.
    # extra_clean runs the pre-clean sequence twice instead of once -- defaults on because the
    # panel's prior content may be GS3 (8-level), whose per-pixel charge diversity a single-pass
    # rep count (tuned for same-mode transitions) doesn't fully flush, causing ghosting on a
    # GS3->mono switch with a single pass; two passes clear it. Costs an extra ~570ms; pass
    # extra_clean=False to skip it for back-to-back mono updates that don't need it.
    def display(self, extra_clean=True):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean the display (I2S DMA) -- this pre-clean sequence is identical to the GS
        # display's own sequence on this board, though the rep counts differ from
        # Inkplate6's.
        t0 = time.ticks_ms()
        for _ in range(2 if extra_clean else 1):
            ip.clean(0, 1)
            ip.clean(1, 15)
            ip.clean(2, 1)
            ip.clean(0, 5)
            ip.clean(2, 1)
            ip.clean(1, 15)

        # The display is written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 4 white-push phases + 1
        # final black-push phase driven in C. inkplatemodule.c's inkplate_mono_display
        # special-cases this board onto inkplate_gen_mono_wave_white_first instead of the
        # usual inkplate_gen_mono_wave: this board runs the same 4-iteration phase loop as
        # the other boards, but its phase *roles* are reversed from every other wired
        # board's (repeated phases push white/skip black, one final phase pushes
        # black/skip white). Do not assume this board's black_phases mapping matches the
        # other boards' -- its own LUTW/LUTB roles must be decoded independently.
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # Trailing park sequence (clean(2, 2); clean(3, 1); vscan_start();) -- unlike
        # Inkplate6's own mono driver, this board's sequence does end with a bare
        # vscan_start() pulse.
        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.vscan_start()
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

    # display sends the grayscale buffer to the display, clearing it first.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # Clean the display (I2S DMA) -- identical pre-clean sequence to the mono
        # display's on this board.
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 15)
        ip.clean(2, 1)
        ip.clean(0, 5)
        ip.clean(2, 1)
        ip.clean(1, 15)

        # The display is written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # Trailing park sequence (clean(3, 1); vscan_start();).
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

    # start makes a reference copy of the current framebuffer.
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer contents
    # -- runs over I2S DMA in C (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame, cfg->partial_reps=5), matching how mono/GS/clean already
    # work. Always walks the full frame (no region params).
    #
    # No pre-clean here -- this only nudges pixels that changed vs the reference snapshot.
    # Caller must ensure the physical panel already matches that snapshot; a full mono
    # display() must run at least once after any GS3 display() before this is safe to call,
    # or it ghosts badly.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        t0 = time.ticks_ms()
        ip.partial_display(self._framebuf, self._base._framebuf)
        t1 = time.ticks_ms()

        # Tail sequence (clean(2, 2); clean(3, 1); vscan_start();).
        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

        td = time.ticks_diff(t1, t0)
        print("Partial: draw %dms" % td)


# Gfx/text/image draw methods come from shared/mixins/inkplate_{gfx,text,image_gs4}_mixin.py;
# self._d_cols/self._d_rows (set in __init__) must be set before any draw call runs,
# or drawing will look offset/corrupted.
class Inkplate(GfxMixin, TextMixin, ImageGS4Mixin):
    # Inkplate wrapper class for easier use.

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

        # EN=12/RST=10 on the *internal* expander (0x20, IO_INT_ADDR), same on both the
        # classic and V2 revision. No collision with this expander's other pins
        # (OE=0/GMOD=1/SPV=2/TPS_WAKEUP=3/PWRUP=4/VCOM=5/FRONTLIGHT_EN=11/
        # SD_ENABLE=13), unlike Inkplate4TEMPERA's touch wiring.
        #
        # Touch coordinates are mirrored against true screen position at every corner
        # (decoded_x == (width-1)-true_x, decoded_y == (height-1)-true_y), no axis swap
        # involved -- a different bug shape than Inkplate4TEMPERA's (flip+swap), so this
        # is per-board and not reusable without its own measurement.
        Touch.init(
            _Inkplate._i2c,
            _Inkplate._PCAL6416A_1,
            self,
            en_pin=12,
            rst_pin=10,
            width=D_COLS,
            height=D_ROWS,
            xy_flipped=True,
        )

        # FRONTLIGHT_EN=11 on the internal expander (0x20), no collision with that
        # expander's other pins (OE=0/GMOD=1/SPV=2/WAKEUP=3/PWRUP=4/VCOM=5/VBAT_EN=9/
        # touch RST=10/EN=12/SD_ENABLE=13).
        Frontlight.init(_Inkplate._i2c, _Inkplate._PCAL6416A_1, 11)

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
                    # Same SD wiring as Inkplate6/10/5v2 (miso=12/mosi=13/sck=14/cs=15).
                    # Starting at the same 4MHz value those boards settled on; not yet
                    # independently confirmed on Inkplate6PLUSV2 hardware -- raise if
                    # 4MHz proves unnecessarily conservative here.
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

    def sd_card_wake(self):
        _Inkplate.SD_ENABLE.digital_write(0)

    # Touchscreen -- thin delegation to touch_elan.Touch, wired to this instance in
    # begin() (so Touch can read .rotation for its coordinate remap).
    def ts_init(self, power_state=1):
        return Touch.ts_init(power_state)

    def ts_shutdown(self):
        Touch.ts_shutdown()

    def ts_available(self):
        return Touch.ts_available()

    def ts_set_power_state(self, state):
        Touch.ts_set_power_state(state)

    def ts_get_power_state(self):
        return Touch.ts_get_power_state()

    def ts_get_data(self, x_pos, y_pos):
        return Touch.ts_get_data(x_pos, y_pos)

    def ts_get_raw_data(self):
        return Touch.ts_get_raw_data()

    def touch_in_area(self, x1, y1, w, h):
        return Touch.touch_in_area(x1, y1, w, h)

    # Frontlight -- thin delegation to frontlight.Frontlight, wired in begin().
    def set_frontlight(self, state):
        Frontlight.set_state(state)

    def set_frontlight_brightness(self, v):
        Frontlight.set_brightness(v)

    def gpio_expander_pin(self, expander, pin, mode):
        if expander == 1:
            return GpioPin(_Inkplate._PCAL6416A_1, pin, mode)
        elif expander == 2:
            return GpioPin(_Inkplate._PCAL6416A_2, pin, mode)

    def clear_display(self):
        InkplateMono.clear(self.ipm._framebuf)
        InkplateGS2.clear(self.ipg._framebuf)

    def display(self, extra_clean=True):
        if self.display_mode == 0:
            self.ipm.display(extra_clean=extra_clean)
            self.ipp.start()
        elif self.display_mode == 1:
            self.ipg.display()

        self.ipp.start()  # making framebuffer copy for partial update

    # CAUTION: unlike display(), this never runs a pre-clean and never resyncs ipp's reference
    # snapshot on its own -- both only happen inside display(). Calling this as the first mono
    # operation after a GS3 display() ghosts badly (worse than a plain mono display() with
    # extra_clean=False): the physical panel still shows the GS3 frame and there's no baseline
    # to diff against. Always call display() at least once after switching away from GS mode
    # before relying on partial_update().
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

    def eink_on(self):
        _Inkplate.power_on()

    def eink_off(self):
        _Inkplate.power_off()

    def read_temperature(self):
        return _Inkplate.read_temperature()

    def read_battery(self):
        return _Inkplate.read_battery()

    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        return _Inkplate.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return _Inkplate.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_data(self):
        return _Inkplate.rtc_get_rtc_data()

    def width(self):
        return self._width

    def height(self):
        return self._height

    # Compatibility functions
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
    # GfxMixin/TextMixin/ImageGS4Mixin, since C owns the whole draw instead of a
    # per-pixel Python callback.
    def _framebuf(self):
        return self.ipm._framebuf if self.display_mode == 0 else self.ipg._framebuf


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
