"""MicroPython driver for the Inkplate 5V2 e-paper display."""

import time
import micropython
import os
import inkplate
from machine import ADC, I2C, Pin, SDCard
from uarray import array
from pcal6416a import *
from micropython import const
import gfx_standard_font_01 as montserrat_black
import gc


import machine

machine.freq(240000000)
# Raw display constants for Inkplate 5V2
D_ROWS = const(720)
D_COLS = const(1280)

# Lookup mask to clear just that pixel's 4 bits (GS4_HMSB, 2 pixels/byte)
pixel_mask_glut = bytearray(b"\xf0\x0f")  # precomputed masks

TPS65186_addr = const(0x48)  # I2C address

# Bit masks used by the (still-Python) byte2gpio table and clean(); the CL/LE/CKV/SPH
# pulse sequencing itself now lives in C (firmware/usermods/inkplate/epd_bitbang.c),
# selected via inkplate.select_board() below.
EPD_DATA = const(0x0E8C0030)  # EPD_D0..EPD_D7
EPD_CL = const(0x00000001)  # in W1Tx0

# Inkplate provides access to the pins of the Inkplate 5V2 as well as to low-level
# display functions.

RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04


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
        # This panel scans columns opposite to Inkplate6/10's -- same trait
        # write_pixel_viper below compensates for, but that only covers draw_pixel/
        # draw_bitmap. gfx_* (shapes/lines/text) goes through gfx.c's gfx_set_pixel
        # instead, which needs the same flip (HIL-confirmed on basic_bw.py's logo).
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

        if len(_Inkplate.byte2gpio) == 0:
            _Inkplate.gen_byte2gpio()

    # _expander_write_cb is invoked from C (epd_bitbang.c, via expander_bridge.c) to
    # toggle a PCAL6416A-controlled line (currently only SPV) -- only one expander on
    # this board, unlike Inkplate6/6V2's two.
    @classmethod
    def _expander_write_cb(cls, addr, pin, value):
        if addr == cls._PCAL6416A.addr:
            cls._PCAL6416A.digital_write(pin, value)
        else:
            raise ValueError("no expander at addr {:#x}".format(addr))

    @classmethod
    def begin(cls):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        cls.ipg = InkplateGS2()
        cls.ipm = InkplateMono()
        cls.ipp = InkplatePartial(cls.ipm)

    # Read the battery voltage. Note that the result depends on the ADC
    # calibration, and be a bit off.
    @classmethod
    def read_battery(cls):
        cls.VBAT_EN.digital_write(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(5)
        value = cls.VBAT.read()
        cls.VBAT_EN.digital_write(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    # Read panel temperature. I varies +- 2 degree
    @classmethod
    def read_temperature(cls):
        # Power on so TPS is visible on I2C
        cls.power_on()

        # start temperature measurement and wait 5 ms
        cls._i2c.writeto_mem(TPS65186_addr, 0x0D, bytes((0x80,)))
        time.sleep_ms(5)

        # request temperature data from panel
        cls._i2c.writeto(TPS65186_addr, bytearray((0x00,)))
        cls._temperature = cls._i2c.readfrom(TPS65186_addr, 1)

        cls.power_off()
        # convert data from bytes to integer
        cls.temperatureInt = int.from_bytes(cls._temperature, "big", True)
        return cls.temperatureInt

    # _tps65186_write writes an 8-bit value to a register
    @classmethod
    def _tps65186_write(cls, reg, v):
        cls._i2c.writeto_mem(TPS65186_addr, reg, bytes((v,)))

    # _tps65186_read reads an 8-bit value from a register
    @classmethod
    def _tps65186_read(cls, reg):
        cls._i2c.readfrom_mem(TPS65186_addr, reg, 1)[0]

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE)
    @classmethod
    def power_on(cls):
        if cls._on:
            return
        cls._on = True
        # turn on power regulator

        cls.TPS_WAKEUP.digital_write(1)
        cls.TPS_PWRUP.digital_write(1)
        cls.TPS_VCOM.digital_write(1)

        # enable all rails
        cls._tps65186_write(0x01, 0x3F)  # ???
        time.sleep_ms(40)
        cls._tps65186_write(0x0D, 0x80)  # ???
        time.sleep_ms(2)
        cls._temperature = cls._tps65186_read(1)
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

        # turn off power regulator
        cls.TPS_PWRUP.digital_write(0)
        cls.TPS_WAKEUP.digital_write(0)
        cls.TPS_VCOM.digital_write(0)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start/vscan_write/vscan_end/fill_screen are implemented in C
    # (firmware/usermods/inkplate/epd_bitbang.c), config-driven via board_config_t --
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
    def rtc_dec_to_bcd(cls, val):
        return (val // 10 * 16) + (val % 10)

    @classmethod
    def rtc_bcd_to_dec(cls, val):
        return (val // 16 * 10) + (val % 16)

    @classmethod
    def rtc_set_time(cls, rtc_hour, rtc_minute, rtc_second):
        data = bytearray(
            [
                RTC_RAM_by,
                170,  # Write in RAM 170 to know that RTC is set
                cls.rtc_dec_to_bcd(rtc_second),
                cls.rtc_dec_to_bcd(rtc_minute),
                cls.rtc_dec_to_bcd(rtc_hour),
            ]
        )

        cls._i2c.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        rtc_year = rtc_yr - 2000

        data = bytearray(
            [
                RTC_RAM_by,
                170,  # Write in RAM 170 to know that RTC is set
            ]
        )

        cls._i2c.writeto(RTC_I2C_ADDR, data)

        data = bytearray(
            [
                RTC_DAY_ADDR,
                cls.rtc_dec_to_bcd(rtc_day),
                cls.rtc_dec_to_bcd(rtc_weekday),
                cls.rtc_dec_to_bcd(rtc_month),
                cls.rtc_dec_to_bcd(rtc_year),
            ]
        )

        cls._i2c.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_get_rtc_data(cls):
        cls._i2c.writeto(RTC_I2C_ADDR, bytearray([RTC_SECOND_ADDR]))
        data = cls._i2c.readfrom(RTC_I2C_ADDR, 7)

        rtc_second = cls.rtc_bcd_to_dec(data[0] & 0x7F)  # Ignore bit 7
        rtc_minute = cls.rtc_bcd_to_dec(data[1] & 0x7F)
        rtc_hour = cls.rtc_bcd_to_dec(data[2] & 0x3F)  # Ignore bits 7 & 6
        rtc_day = cls.rtc_bcd_to_dec(data[3] & 0x3F)
        rtc_weekday = cls.rtc_bcd_to_dec(data[4] & 0x07)  # Ignore bits 7,6,5,4 & 3
        rtc_month = cls.rtc_bcd_to_dec(data[5] & 0x1F)  # Ignore bits 7,6 & 5
        rtc_year = cls.rtc_bcd_to_dec(data[6]) + 2000

        return {
            "second": rtc_second,
            "minute": rtc_minute,
            "hour": rtc_hour,
            "day": rtc_day,
            "weekday": rtc_weekday,
            "month": rtc_month,
            "year": rtc_year,
        }


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
        w = 1280  # physical width
        h = 720  # physical height

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

        # Inkplate5V2's panel scans columns opposite to Inkplate6/10's -- flip physical
        # column after the rotation remap so logical left-to-right stays left-to-right
        # on screen. HIL-confirmed: basic_bw.py's Soldered logo read backwards without
        # this, correct with it.
        px = w - 1 - px

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
            byte_index = py * 640 + (px >> 1)

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
