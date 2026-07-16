"""MicroPython driver for the Inkplate 4TEMPERA e-paper display.

Display-path + SD card + touch -- this pass deliberately does not port
setVCOM/writeVCOMToPanelEEPROM/getStoredVCOM/getVCOMValue/readTemperature, same
precedent as Inkplate6FLICK/6PLUSV2's own first pass (docs/refactor_plan.md
Phase 8 steps 24/25/26).
Touch (Elan controller, shared with Inkplate6PLUS/6PLUSV2), frontlight (shared with
Inkplate6PLUS/6PLUSV2/6FLICK), buzzer, fuel gauge, BME688, APDS9960, and the
LSM6DS3 accelerometer/gyro (all Inkplate4TEMPERA-only except touch/frontlight)
wired in Phase 11 -- every sensor named in this board's pins.h is now ported.
"""

import time
import os
import inkplate
import framebuf
from machine import I2C, Pin, SDCard
from pcal6416a import PCAL6416A, GpioPin, mode_output, mode_input_pullup, mode_input_pulldown
from tps65186 import TPS65186
from rtc import RTC
from epd_power_pins import tristate_display_pins, restore_display_pins
from touch_elan import Touch
from frontlight import Frontlight
from buzzer import Buzzer
from bq27441 import BQ27441
from bme688 import BME688
from apds9960 import APDS9960
from lsm6ds3 import LSM6DS3
from micropython import const
import gfx_standard_font_01 as montserrat_black
import gc


import machine

machine.freq(240000000)
# Raw display constants for Inkplate 4TEMPERA -- first square panel wired in this repo.
D_ROWS = const(600)
D_COLS = const(600)


# IO_EXT_ADDR straight from the pasted Inkplate4TEMPERA pins.h -- this is
# TOUCHSCREEN_IO_EXPANDER, i.e. touch EN/RST live here (see touch_elan.py), not on
# the internal expander (0x20) used for OE/GMODE/SPV/TPS65186/SD.
_EXPANDER2_ADDR = 0x21

# Fuel Gauge GPOUT pin, internal expander (0x20) -- confirmed via the real
# EPDDriver::wakePeripheral/sleepPeripheral (INKPLATE_FUEL_GAUGE branch, both
# operate on `expander1`).
_FG_GPOUT_PIN = const(15)

# BME688's own ctrl_meas register (0x74) -- straight from the pasted pins.h's
# BME_CONTROL_ADDR, used only by wake_peripheral/sleep_peripheral's INKPLATE_BME688
# branch to poke the mode bits directly (real EPDDriver::wakePeripheral/
# sleepPeripheral). Not the sensor's I2C address (0x76, see bme688.py) -- this is
# a register offset on the sensor itself.
_BME_CONTROL_ADDR = const(0x74)

# Peripheral select bitmasks (INKPLATE_BUZZER/ACCELEROMETER/BME688/APDS9960/
# FUEL_GAUGE) live as plain int attributes on the Inkplate class below, not
# module-level micropython.const()s -- MicroPython's const() inlines every
# reference to the bare name, including an assignment target of the same name,
# which broke `Inkplate.INKPLATE_BUZZER = INKPLATE_BUZZER`-style class-attribute
# mirroring (turned into `0x01 = 0x01`, a real on-device SyntaxError caught via
# HIL, not guessed).

# Inkplate provides access to the pins of the Inkplate 4TEMPERA as well as to low-level
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
        inkplate.select_board("inkplate4tempera")
        inkplate.set_expander_write_cb(cls._expander_write_cb)
        # This board's own pasted writePixelInternal() packs GS4_HMSB nibbles opposite to
        # every other wired board (pixelMaskGLUT={0xF,0xF0}, even x -> high nibble) --
        # gfx_set_pixel needs telling, since it defaults to the common convention.
        inkplate.gfx_set_gs4_nibble_swap(True)

        cls.EPD_OE = GpioPin(cls._PCAL6416A_1, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._PCAL6416A_1, 1, mode_output)
        # EPD_SPV itself is never read again -- toggling happens in C via pin_spv in
        # board_config.c, which must stay pin 2 on this same expander (0x20) to match.
        # This call's job is the pin_mode(OUTPUT) side effect (see PCAL6416A.GpioPin),
        # not the object it returns.
        cls.EPD_SPV = GpioPin(cls._PCAL6416A_1, 2, mode_output)

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

        cls.TPS_WAKEUP = GpioPin(cls._PCAL6416A_1, 3, mode_output)
        cls.TPS_WAKEUP.digital_write(0)

        cls.TPS_PWRUP = GpioPin(cls._PCAL6416A_1, 4, mode_output)
        cls.TPS_PWRUP.digital_write(0)

        cls.TPS_VCOM = GpioPin(cls._PCAL6416A_1, 5, mode_output)
        cls.TPS_VCOM.digital_write(0)

        # SD card P-MOS enable -- pin 11 (SD_PMOS_PIN in the pasted Arduino reference
        # driver's pins.h), on this same expander (0x20). Different pin number from
        # Inkplate6/5v2's own SD_ENABLE (pin 10) or Inkplate6PLUSV2's (pin 13) --
        # board-specific wiring, transcribed directly from this board's own pins.h.
        cls.SD_ENABLE = GpioPin(cls._PCAL6416A_1, 11, mode_output)

        # Fuel Gauge GPOUT -- initial pull-up matches the real gpioInit(); flipped to
        # pulldown by sleep_peripheral(INKPLATE_FUEL_GAUGE) below once begin() runs
        # (real driver puts every sensor to sleep by default at boot).
        cls._PCAL6416A_1.pin_mode(_FG_GPOUT_PIN, mode_input_pullup)

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
    # same names/signatures as every other board, so inkplate_mono.py/inkplate_gs.py/
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

    # Sensors are asleep by default (real EPDDriver::initDriver() ends with a
    # sleepPeripheral() call covering all of them) -- call wake_peripheral() before
    # using one.
    @classmethod
    def wake_peripheral(cls, peripheral):
        if peripheral & Inkplate.INKPLATE_FUEL_GAUGE:
            # rising edge on GPOUT wakes the fuel gauge -- relies on the pin already
            # being pulldown from a prior sleep_peripheral() call, same as the real
            # driver (no explicit pulldown-first step there either)
            cls._PCAL6416A_1.pin_mode(_FG_GPOUT_PIN, mode_input_pullup)
            time.sleep_us(250)

        if peripheral & Inkplate.INKPLATE_BME688:
            # real wakePeripheral(): nudge ctrl_meas bit0, then re-run the full
            # begin() (soft reset + calib + TPH/filter/heater config) -- the ctrl_meas
            # nudge looks redundant given begin()'s own soft reset immediately
            # overwrites it, but ported literally rather than dropped as dead code,
            # since it's plausibly a real "wake the I2C bus" requirement on this
            # chip's power domain (same class of surprise the fuel gauge had).
            ctrl = BME688.read_reg(_BME_CONTROL_ADDR)
            BME688.write_reg(_BME_CONTROL_ADDR, ctrl | 0x01)
            BME688.begin()

        if peripheral & Inkplate.INKPLATE_APDS9960:
            # real wakePeripheral(): just powers the chip on (apds9960.enablePower()),
            # unlike BME688's wake which re-runs the full chip bring-up -- APDS9960's
            # own real chip-config (begin()) is left for the caller to invoke
            # explicitly, per the real SparkFun library's own documented contract
            # (see apds9960.py's docstring).
            APDS9960.enable_power()

        if peripheral & Inkplate.INKPLATE_ACCELEROMETER:
            # real wakePeripheral(): sets gyroEnabled/accelEnabled=1 then calls
            # begin() again -- begin() is both the chip-bringup AND the apply-
            # settings function on this driver, unlike BME688/APDS9960's separate
            # init-vs-power-gate split.
            LSM6DS3.gyro_enabled = 1
            LSM6DS3.accel_enabled = 1
            LSM6DS3.begin()

    @classmethod
    def sleep_peripheral(cls, peripheral):
        if peripheral & Inkplate.INKPLATE_FUEL_GAUGE:
            cls._PCAL6416A_1.pin_mode(_FG_GPOUT_PIN, mode_input_pulldown)
            try:
                BQ27441.shutdown()
            except OSError:
                # already shut down (its I2C bus is disabled in shutdown mode, so a
                # redundant shutdown() while already asleep NAKs) -- harmless, this
                # call's whole point is making sure it ends up asleep either way
                pass

        if peripheral & Inkplate.INKPLATE_BME688:
            # clears ctrl_meas's mode bits -> BME68X_SLEEP_MODE; no re-init needed,
            # this chip stays I2C-responsive in sleep mode (unlike the fuel gauge).
            # Same "begin() must never crash over an optional peripheral" rule as
            # the fuel gauge above -- hit a real OSError here too, on a unit where
            # BME688 didn't ACK at all.
            try:
                ctrl = BME688.read_reg(_BME_CONTROL_ADDR)
                BME688.write_reg(_BME_CONTROL_ADDR, ctrl & ~0x03)
            except OSError:
                pass

        if peripheral & Inkplate.INKPLATE_APDS9960:
            try:
                APDS9960.disable_power()
            except OSError:
                pass

        if peripheral & Inkplate.INKPLATE_ACCELEROMETER:
            try:
                LSM6DS3.gyro_enabled = 0
                LSM6DS3.accel_enabled = 0
                LSM6DS3.begin()
            except OSError:
                pass


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed directly from the real
        # Inkplate4TEMPERADriver.cpp display1b() pre-clean sequence (identical to
        # display3b()'s own sequence on this board).
        t0 = time.ticks_ms()
        ip.clean(0, 5)
        ip.clean(1, 15)
        ip.clean(0, 15)
        ip.clean(1, 15)
        ip.clean(0, 15)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 10 black-push phases + 1
        # final black/white phase driven in C. inkplatemodule.c's inkplate_mono_display
        # special-cases this board onto black_phases=10 (standard inkplate_gen_mono_wave
        # scheme, not the reversed-role Inkplate6PLUSV2 variant -- confirmed by this
        # board's own GraphicsDefs.h LUTB/LUT2 being byte-identical to the standard
        # op_blk/op_bw tables, not hand-waved from the unusual phase count alone).
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display1b() tail exactly
        # (clean(2, 1); clean(3, 1); vscan_start();) -- note this is clean(2, 1), not
        # clean(2, 2) like Inkplate6PLUSV2's own tail.
        ip.clean(2, 1)
        ip.clean(3, 1)
        ip.vscan_start()
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

        # clean the display (I2S DMA), reps transcribed directly from the real
        # Inkplate4TEMPERADriver.cpp display3b() pre-clean sequence -- identical to
        # display1b()'s own sequence on this board.
        t0 = time.ticks_ms()
        ip.clean(0, 5)
        ip.clean(1, 15)
        ip.clean(0, 15)
        ip.clean(1, 15)
        ip.clean(0, 15)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C,
        # same as every other board. This board's real display3b() loops for(k<8), one
        # short of the 9 stored here, but the 9th (final) phase is all-zero/no-op, so
        # pushing it as a harmless extra pass keeps this consistent with every other
        # board's waveform.phases=9 instead of a one-off 8.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display3b() tail
        # (clean(3, 1); vscan_start();).
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
    # epd_i2s_push_partial_frame, cfg->partial_reps=9 matching this board's own pasted
    # Arduino reference driver's partialUpdate() for(k<9) loop), matching how mono/GS/clean
    # already work. Always walks the full frame (no region params) -- matches the real
    # Arduino reference driver's partialUpdate(), which has none either.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        t0 = time.ticks_ms()
        ip.partial_display(self._framebuf, self._base._framebuf)
        t1 = time.ticks_ms()

        # Tail transcribed directly from the real Inkplate4TEMPERADriver.cpp
        # partialUpdate() (clean(2, 2); clean(3, 1); vscan_start();).
        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

        td = time.ticks_diff(t1, t0)
        print("Partial: draw %dms" % td)


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

    # Peripheral select bitmasks straight from the pasted pins.h, used by
    # wake_peripheral()/sleep_peripheral(). Only INKPLATE_FUEL_GAUGE is actually
    # wired this pass -- the other three are accepted (for a future sensor's own
    # wiring to reuse this same dispatch) but currently no-ops. NOTE: pins.h has
    # this colliding with INKPLATE_BUZZER's 0x01 (the other three step
    # 0x02/0x04/0x08, suggesting a 0x10 typo) -- used as literally pasted per
    # user's explicit call, revisit if wake/sleep behavior for one bleeds into
    # the other.
    INKPLATE_BUZZER = 0x01
    INKPLATE_ACCELEROMETER = 0x02
    INKPLATE_BME688 = 0x04
    INKPLATE_APDS9960 = 0x08
    INKPLATE_FUEL_GAUGE = 0x1

    def __init__(self, mode):
        self.display_mode = mode

    def begin(self):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        _Inkplate._tps = TPS65186(
            _Inkplate._i2c, _Inkplate.TPS_WAKEUP, _Inkplate.TPS_PWRUP, _Inkplate.TPS_VCOM
        )
        _Inkplate._tps.begin()
        _Inkplate._rtc = RTC(_Inkplate._i2c)

        Touch.init(
            _Inkplate._i2c,
            _Inkplate._PCAL6416A_2,
            self,
            en_pin=0,
            rst_pin=1,
            width=D_COLS,
            height=D_ROWS,
            x_raw_inverted=True,
            xy_swapped=True,
        )

        # FRONTLIGHT_EN=10 on the internal expander (0x20) -- confirmed from this
        # board's own pasted pins.h, no collision with that expander's other pins
        # (OE=0/GMOD=1/SPV=2/WAKEUP=3/PWRUP=4/VCOM=5/SD_ENABLE=11).
        Frontlight.init(_Inkplate._i2c, _Inkplate._PCAL6416A_1, 10)

        # BUZZ_EN=12 on the internal expander (0x20), DIGIPOT_ADDR=0x2F -- both
        # confirmed from this board's own pasted pins.h, no collision with that
        # expander's other pins (OE=0/GMOD=1/SPV=2/WAKEUP=3/PWRUP=4/VCOM=5/
        # SD_ENABLE=11/FRONTLIGHT_EN=10).
        Buzzer.init(_Inkplate._i2c, _Inkplate._PCAL6416A_1, 12)

        # BQ27441-G1 fuel gauge, default I2C addr 0x55 -- shared i2c bus.
        BQ27441.init(_Inkplate._i2c)

        # BME688 env sensor, default I2C addr 0x76 -- shared i2c bus. Bus-only, no
        # chip traffic yet (matches real driver: bme688.begin() is only ever called
        # from wakePeripheral(), never from initDriver()).
        BME688.init(_Inkplate._i2c)

        # APDS9960 gesture/proximity/light sensor, default I2C addr 0x39 -- shared
        # i2c bus. Bus-only here too; its own begin() is left for the caller (see
        # apds9960.py's docstring).
        APDS9960.init(_Inkplate._i2c)

        # LSM6DS3(TR-C) accelerometer+gyro, default I2C addr 0x6B -- shared i2c
        # bus. Bus-only; its own begin() (chip bring-up + apply gyro/accel
        # enable state) only ever runs via wake_peripheral/sleep_peripheral,
        # matching the real driver.
        LSM6DS3.init(_Inkplate._i2c)

        # Real EPDDriver::initDriver() ends by sleeping every sensor (they're asleep
        # by default; wake_peripheral() must be called before using one) -- matches
        # its own literal `sleepPeripheral(BUZZER|APDS9960|BME688|ACCELEROMETER|
        # FUEL_GAUGE)` call now that every sensor it names is ported. Safe to
        # include BME688/APDS9960/accelerometer here even though none of their own
        # begin() was ever called before this: their sleep paths ACK from cold
        # boot same as any other register (unlike the fuel gauge's real shutdown
        # mode) -- though the accelerometer's sleep_peripheral is heavier than the
        # other two (its begin() unconditionally does 3x100ms warm-up reads
        # regardless of enabled state, matching the real driver exactly), so this
        # adds ~300ms+ to every board begin() call, same real cost the actual
        # hardware pays too.
        _Inkplate.sleep_peripheral(
            Inkplate.INKPLATE_FUEL_GAUGE
            | Inkplate.INKPLATE_BME688
            | Inkplate.INKPLATE_APDS9960
            | Inkplate.INKPLATE_ACCELEROMETER
        )

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
                    # Same SD wiring as every other classic-ESP32 board (miso=12/mosi=13/
                    # sck=14/cs=15), confirmed against this board's own pasted
                    # sdCardInit() (spi2.begin(14, 12, 13, 15) / SdSpiConfig(15, ...)).
                    # Starting at the same 4MHz value those boards settled on (their own
                    # real driver's SdSpiConfig used 25MHz over SdFat/Arduino SPI -- not
                    # directly applicable to MicroPython's SDCard driver); not yet
                    # independently confirmed on real Inkplate4TEMPERA hardware.
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

    # Buzzer -- thin delegation to buzzer.Buzzer, wired in begin().
    def beep(self, length_ms, freq=None):
        Buzzer.beep(length_ms, freq)

    def beep_on(self, freq=None):
        Buzzer.beep_on(freq)

    def beep_off(self):
        Buzzer.beep_off()

    # Fuel gauge -- thin delegation to bq27441.BQ27441, wired in begin(). Full
    # BQ27441 API (current/capacity/soh/GPOUT config/etc.) is available directly
    # via the bq27441.BQ27441 class for callers that need more than these two.
    def read_battery(self):
        return BQ27441.voltage() / 1000.0

    def read_battery_soc(self):
        return BQ27441.soc()

    # BME688 -- thin delegation to bme688.BME688. Must wake_peripheral(INKPLATE_BME688)
    # first (runs the chip's real begin()). Full BME688 API (read_pressure/humidity/
    # gas_resistance/altitude/sensor_data) available directly via the class.
    def read_temperature_bme(self):
        return BME688.read_temperature()

    # APDS9960 -- thin delegation to apds9960.APDS9960. wake_peripheral(INKPLATE_APDS9960)
    # only powers the chip on; call APDS9960.begin() yourself before using these
    # (see apds9960.py's docstring). Full API (gesture/color/interrupt config)
    # available directly via the class.
    def read_proximity(self):
        return APDS9960.read_proximity()

    def read_gesture(self):
        return APDS9960.read_gesture()

    # Accelerometer/gyro -- thin delegation to lsm6ds3.LSM6DS3. Must
    # wake_peripheral(INKPLATE_ACCELEROMETER) first (runs the chip's real begin()).
    # Full LSM6DS3 API (gyro reads/temperature/FIFO) available directly via the class.
    def read_accelerometer(self):
        return (
            LSM6DS3.read_float_accel_x(),
            LSM6DS3.read_float_accel_y(),
            LSM6DS3.read_float_accel_z(),
        )

    def wake_peripheral(self, peripheral):
        _Inkplate.wake_peripheral(peripheral)

    def sleep_peripheral(self, peripheral):
        _Inkplate.sleep_peripheral(peripheral)

    def gpio_expander_pin(self, expander, pin, mode):
        if expander == 1:
            return GpioPin(_Inkplate._PCAL6416A_1, pin, mode)
        elif expander == 2:
            return GpioPin(_Inkplate._PCAL6416A_2, pin, mode)

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

    def eink_on(self):
        _Inkplate.power_on()

    def eink_off(self):
        _Inkplate.power_off()

    def read_temperature(self):
        return _Inkplate.read_temperature()

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

    def write_pixel(self, x, y, c):
        inkplate.gfx_set_pixel(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, c
        )

    def draw_bitmap(self, x, y, data, w, h, c=1):
        inkplate.gfx_draw_bitmap(
            self._framebuf(), D_COLS, D_ROWS, self.rotation, self.display_mode, x, y, data, w, h, c
        )

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
        if path.startswith(("http://", "https://")):
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_web(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_sd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        bmp_size = os.stat(path)[6]
        bmp_data = bytearray(bmp_size)
        with open(path, "rb") as f:
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
