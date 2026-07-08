# MicroPython driver for Inkplate 5V2
# By Soldered Electronics
# Based on the original contribution by https://github.com/tve
import time
import micropython
import os
from machine import ADC, I2C, Pin, SDCard
from uarray import array
from pcal6416a import *
from micropython import const
import gc
import machine

machine.freq(240000000)
from gfx import GFX
# ===== Constants that change between the Inkplate 5 and 10

# Raw display constants for Inkplate 5
D_ROWS = const(720)
D_COLS = const(1280)

# Waveforms for 2 bits per pixel grey-scale.
# Order of 4 values in each tuple: blk, dk-grey, light-grey, white
# Meaning of values: 0=dischg, 1=black, 2=white, 3=skip
# Uses "colors" 0 (black), 3, 5, and 7 (white) from 3-bit waveforms below

# add discharge to waveforms to try to fix them
WAVE_2B = (  # original mpy driver for Ink 6, differs from arduino driver below
    (0, 0, 0, 0),
    (0, 0, 0, 0),
    (0, 1, 1, 0),
    (0, 1, 1, 0),
    (1, 2, 1, 0),
    (1, 1, 2, 0),
    (1, 2, 2, 2),
)

# Lookup mask to clear just that pixel's 2 bits
pixel_mask_glut = bytearray(b"\xfc\xf3\xcf\x3f")  # precomputed masks
# Ink6 WAVEFORM3BIT from arduino driver
# {{0,1,1,0,0,1,1,0},{0,1,2,1,1,2,1,0},{1,1,1,2,2,1,0,0},{0,0,0,1,1,1,2,0},
#  {2,1,1,1,2,1,2,0},{2,2,1,1,2,1,2,0},{1,1,1,2,1,2,2,0},{0,0,0,0,0,0,2,0}};

TPS65186_addr = const(0x48)  # I2C address

# ESP32 GPIO set and clear registers to twiddle 32 gpio bits at once
# from esp-idf:
# define DR_REG_GPIO_BASE           0x3ff44000
# define GPIO_OUT_W1TS_REG          (DR_REG_GPIO_BASE + 0x0008)
# define GPIO_OUT_W1TC_REG          (DR_REG_GPIO_BASE + 0x000c)
ESP32_GPIO = const(0x3FF44000)  # ESP32 GPIO base
# register offsets from ESP32_GPIO
W1TS0 = const(2)  # offset for "write one to set" register for gpios 0..31
W1TC0 = const(3)  # offset for "write one to clear" register for gpios 0..31
W1TS1 = const(5)  # offset for "write one to set" register for gpios 32..39
W1TC1 = const(6)  # offset for "write one to clear" register for gpios 32..39
# bit masks in W1TS/W1TC registers
EPD_DATA = const(0x0E8C0030)  # EPD_D0..EPD_D7
EPD_CL = const(0x00000001)  # in W1Tx0
EPD_LE = const(0x00000004)  # in W1Tx0
EPD_CKV = const(0x00000001)  # in W1Tx1
EPD_SPH = const(0x00000002)  # in W1Tx1

# Some constants for the RTC
RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04


# Inkplate provides access to the pins of the Inkplate 5 as well as to low-level display
# functions.


class _Inkplate:
    @classmethod
    def init(cls, i2c):
        cls._i2c = i2c
        cls._PCAL6416A = PCAL6416A(i2c)
        # Display control lines
        cls.EPD_CL = Pin(0, Pin.OUT, value=0)
        cls.EPD_LE = Pin(2, Pin.OUT, value=0)
        cls.EPD_CKV = Pin(32, Pin.OUT, value=0)
        cls.EPD_SPH = Pin(33, Pin.OUT, value=1)

        cls.EPD_OE = GpioPin(cls._PCAL6416A, 0, mode_output)
        cls.EPD_GMODE = GpioPin(cls._PCAL6416A, 1, mode_output)
        cls.EPD_SPV = GpioPin(cls._PCAL6416A, 2, mode_output)
        # Display data lines - we only use the Pin class to init the pins
        Pin(4, Pin.OUT)
        Pin(5, Pin.OUT)
        Pin(18, Pin.OUT)
        Pin(19, Pin.OUT)
        Pin(23, Pin.OUT)
        Pin(25, Pin.OUT)
        Pin(26, Pin.OUT)
        Pin(27, Pin.OUT)
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
        cls.VBAT_EN.digital_write(0)

        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, 10, mode_output)
        cls.SD_ENABLE.digital_write(0)

        cls.VBAT = ADC(Pin(35))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)

        cls._on = False  # whether panel is powered on or not

        if len(_Inkplate.byte2gpio) == 0:
            _Inkplate.gen_byte2gpio()

    @classmethod
    def begin(cls):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        cls.ipg = InkplateGS2()
        cls.ipm = InkplateMono()
        cls.ipp = InkplatePartial(cls.ipm)

        cls.clear_display()

        cls.GFX = GFX(
            D_COLS,
            D_ROWS,
            cls.write_pixel,
            cls.write_fast_hline,
            cls.write_fast_vline,
            cls.write_fill_rect,
            None,
            None,
        )

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
        # convert data from bytes to integer
        cls.temperatureInt = int.from_bytes(cls._temperature, "big", True)

        cls.power_off()
        return cls.temperatureInt

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

    # power_off puts the display to sleep and cuts the power
    # TODO: also tri-state gpio pins to avoid current leakage during deep-sleep
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

    # vscan_start begins a vertical scan by toggling CKV and SPV
    # sleep_us calls are commented out 'cause MP is slow enough...
    @micropython.native
    @classmethod
    def vscan_start(cls):
        def ckv_pulse():
            cls.EPD_CKV(0)
            cls.EPD_CKV(1)

        # start a vertical scan pulse
        cls.EPD_CKV(1)  # time.sleep_us(7)
        cls.EPD_SPV.digital_write(0)  # time.sleep_us(10)
        ckv_pulse()  # time.sleep_us(8)
        cls.EPD_SPV.digital_write(1)  # time.sleep_us(10)
        # pulse through 3 scan lines that end up being invisible
        ckv_pulse()  # time.sleep_us(18)
        ckv_pulse()  # time.sleep_us(18)
        ckv_pulse()

    @classmethod
    def vscan_end(cls):
        cls.EPD_SPH(0)
        cls.EPD_LE(1)
        cls.EPD_LE(0)

    # vscan_write latches the row into the display pixels and moves to the next row
    @micropython.viper
    @staticmethod
    def vscan_write():
        # gpio register ptrs
        w1ts0 = ptr32(0x3FF44008)  # ESP32_GPIO + 0x08
        w1tc0 = ptr32(0x3FF4400C)  # ESP32_GPIO + 0x0C

        # constants
        epd_cl = 0x00000001  # EPD_CL
        epd_ckv = 0x00000001  # EPD_CKV
        epd_le = 0x00000004  # EPD_LE

        # clear/set clock
        w1ts0[0] = epd_cl
        w1tc0[0] = epd_cl

        # latch + increment scan
        w1tc0[3] = epd_ckv  # remove gate drive
        w1ts0[0] = epd_le  # pulse latch
        w1tc0[0] = epd_le
        w1ts0[0] = epd_le  # delay tiny bit
        w1tc0[0] = epd_le  # delay tiny bit
        w1ts0[3] = epd_ckv  # apply gate drive next row

    # fill_screen writes the same value to all bytes of the screen, it is used for cleaning
    @staticmethod
    @micropython.viper
    def fill_screen(data: int):
        # gpio register ptrs
        w1ts0 = ptr32(0x3FF44008)  # ESP32_GPIO + 0x08
        w1tc0 = ptr32(0x3FF4400C)  # ESP32_GPIO + 0x0C

        # constants
        off = 0x0E8C0031  # EPD_DATA | EPD_CL
        epd_cl = 0x00000001  # EPD_CL
        epd_sph = 0x00000002  # EPD_SPH
        epd_ckv = 0x00000001  # EPD_CKV
        epd_le = 0x00000004  # EPD_LE

        # setup data bus
        w1tc0[0] = off
        w1ts0[0] = data

        # ---- send all 720 rows ----
        for r in range(720):
            # send first byte of row with start-row signal
            w1tc0[3] = epd_sph  # (W1TC1-W1TC0=3)
            w1ts0[0] = epd_cl
            w1tc0[0] = epd_cl
            w1ts0[3] = epd_sph  # (W1TS1-W1TS0=3)

            # send remaining 160 bytes (1280 >> 3)
            i = 160
            while i > 0:
                # four toggles per byte
                w1ts0[0] = epd_cl
                w1tc0[0] = epd_cl
                w1ts0[0] = epd_cl
                w1tc0[0] = epd_cl
                i -= 1

            # latch row and increment
            w1tc0[3] = epd_ckv  # remove gate drive
            w1ts0[0] = epd_le  # pulse latch
            w1ts0[0] = epd_le  # delay tiny bit
            w1tc0[0] = epd_le
            w1tc0[0] = epd_le  # delay tiny bit
            w1ts0[3] = epd_ckv  # apply gate drive next row

    # clean fills the screen with one of the four possible pixel patterns
    @staticmethod
    @micropython.viper
    def clean(patt: int, rep: int):
        c = [0xAA, 0x55, 0x00, 0xFF][patt]
        data = int(_Inkplate.byte2gpio[c]) & ~EPD_CL
        i: int = 0
        while i < rep:
            _Inkplate.vscan_start()
            _Inkplate.fill_screen(data)
            _Inkplate.vscan_end()
            i += 1


# Inkplate display with 2 bits of gray scale (4 levels)

from inkplate_partial import *
from inkplate_mono import *
from inkplate_gs import *


# Inkplate wraper to make it more easy for use
class Inkplate:
    INKPLATE_1BIT = 0
    INKPLATE_2BIT = 1

    BLACK = 1
    WHITE = 0

    cursor = [0, 0]

    _width = D_COLS
    _height = D_ROWS

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    rotation = 0
    display_mode = 0
    text_size = 1

    def __init__(self, mode):
        if mode == 0:
            self.textColor = 1
        else:
            self.textColor = 0
        self.display_mode = mode

    def begin(self):
        _Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

        self.ipg = InkplateGS2()
        self.ipm = InkplateMono()
        self.ipp = InkplatePartial(self.ipm)

        self.fullUpdateThreshold = 10
        self.partialUpdateCounter = 0

        self.ipg.clear()
        self.ipm.clear()

        self.GFX = GFX(
            D_COLS,
            D_ROWS,
            self.write_pixel,
            self.write_fast_hline,
            self.write_fast_vline,
            self.write_fill_rect,
            None,
            None,
        )

        self.textWrapping = 1

    def init_sd_card(self, fast_boot=False):
        _Inkplate.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(slot=3, miso=Pin(12), mosi=Pin(13), sck=Pin(14), cs=Pin(15)),
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
        elif self.display_mode == 1:
            InkplateGS2.display(self.ipg._framebuf)

        self.ipp.start()  # making framebuffer copy for partial update

    def set_full_update_threshold(self, new_threshold):
        self.fullUpdateThreshold = new_threshold

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

    def clean(self):
        self.eink_on()
        _Inkplate.clean(0, 1)
        _Inkplate.clean(1, 12)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 11)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(1, 12)
        _Inkplate.clean(2, 1)
        _Inkplate.clean(0, 11)
        self.eink_off()

    def eink_on(self):
        _Inkplate.power_on()

    def eink_off(self):
        _Inkplate.power_off()

    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        return _Inkplate.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return _Inkplate.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_data(self):
        return _Inkplate.rtc_get_rtc_data()

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
        self.GFX.rotation = self.rotation
        if self.rotation == 0 or self.rotation == 2:
            self.GFX.width = D_COLS
            self.GFX.height = D_ROWS
            self._width = D_COLS
            self._height = D_ROWS
        elif self.rotation == 1 or self.rotation == 3:
            self.GFX.width = D_ROWS
            self.GFX.height = D_COLS
            self._width = D_ROWS
            self._height = D_COLS

    def get_rotation(self):
        return self.rotation

    def draw_pixel(self, x, y, c):
        self.write_pixel(x, y, c)

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
        if display_mode == 0:  # 1bpp
            idx = (py * w + px) >> 3  # 8 pixels per byte
            shift = px & 7
            if c:
                fb[idx] = fb[idx] | (1 << shift)
            else:
                fb[idx] = fb[idx] & ~(1 << shift)

        else:
            c &= 0x03

            # Find byte index
            byte_index = py * 320 + (px >> 2)

            # Which pixel inside this byte (0..3)
            pixel_index = px & 3
            shift = pixel_index * 2

            # Load current byte
            temp = fb[byte_index]

            # Clear and write the new pixel
            fb[byte_index] = (temp & int(pixel_mask_glut[pixel_index])) | (c << shift)

    @micropython.native
    def write_fill_rect(self, x, y, w, h, c):
        for j in range(w):
            for i in range(h):
                self.write_pixel(x + j, y + i, c)

    @micropython.native
    def write_fast_vline(self, x, y, h, c):
        for i in range(h):
            self.write_pixel(x, y + i, c)

    @micropython.native
    def write_fast_hline(self, x, y, w, c):
        for i in range(w):
            self.write_pixel(x + i, y, c)

    @micropython.native
    def write_line(self, x0, y0, x1, y1, c):
        self.GFX.line(x0, y0, x1, y1, c)

    @micropython.native
    def draw_fast_vline(self, x, y, h, c):
        self.write_fast_vline(x, y, h, c)

    @micropython.native
    def draw_fast_hline(self, x, y, w, c):
        self.write_fast_hline(x, y, w, c)

    @micropython.native
    def fill_rect(self, x, y, w, h, c):
        self.write_fill_rect(x, y, w, h, c)

    @micropython.native
    def fill_screen(self, c):
        self.fill_rect(0, 0, self.width(), self.height(), c)

    @micropython.native
    def draw_line(self, x0, y0, x1, y1, c):
        self.write_line(x0, y0, x1, y1, c)

    @micropython.native
    def draw_rect(self, x, y, w, h, c):
        self.GFX.rect(x, y, w, h, c)

    @micropython.native
    def draw_circle(self, x, y, r, c):
        self.GFX.circle(x, y, r, c)

    @micropython.native
    def fill_circle(self, x, y, r, c):
        self.GFX.fill_circle(x, y, r, c)

    @micropython.native
    def draw_triangle(self, x0, y0, x1, y1, x2, y2, c):
        self.GFX.triangle(x0, y0, x1, y1, x2, y2, c)

    @micropython.native
    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        self.GFX.fill_triangle(x0, y0, x1, y1, x2, y2, c)

    @micropython.native
    def draw_round_rect(self, x, y, q, h, r, c):
        self.GFX.round_rect(x, y, q, h, r, c)

    @micropython.native
    def fill_round_rect(self, x, y, q, h, r, c):
        self.GFX.fill_round_rect(x, y, q, h, r, c)

    def set_display_mode(self, mode):
        self.display_mode = mode

    def select_display_mode(self, mode):
        self.display_mode = mode

    def get_display_mode(self):
        return self.display_mode

    def set_text_size(self, s):
        self.text_size = s

    def set_font(self, f):
        self.GFX.font_family = f
        self.GFX.font = self.GFX.font_family._font

    def set_text_color(self, c):
        self.textColor = c

    def set_text_wrapping(self, state: bool):
        self.textWrapping = state

    def reset_cursor(self):
        self.cursor = [0, 0]

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    def print_text(self, x, y, s):
        if self.display_mode == Inkplate.INKPLATE_2BIT:
            self.GFX._print_text(
                self.ipg._framebuf,
                x,
                y,
                s,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=2,
            )
        else:
            self.GFX._print_text(
                self.ipm._framebuf,
                x,
                y,
                s,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=1,
            )

    def println(self, text):
        if self.display_mode == Inkplate.INKPLATE_2BIT:
            self.cursor, line_height = self.GFX._print_text(
                self.ipg._framebuf,
                self.cursor[0],
                self.cursor[1],
                text,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=2,
            )
        else:
            self.cursor, line_height = self.GFX._print_text(
                self.ipm._framebuf,
                self.cursor[0],
                self.cursor[1],
                text,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=1,
            )
        self.cursor[1] += line_height
        self.cursor[0] = 0

    def print(self, text):
        if self.display_mode == Inkplate.INKPLATE_2BIT:
            self.cursor, line_height = self.GFX._print_text(
                self.ipg._framebuf,
                self.cursor[0],
                self.cursor[1],
                text,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=2,
            )
        else:
            self.cursor, _ = self.GFX._print_text(
                self.ipm._framebuf,
                self.cursor[0],
                self.cursor[1],
                text,
                self.text_size,
                self.textColor,
                text_wrap=self.textWrapping,
                bpp=1,
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

    def draw_bitmap(self, x, y, data, w, h):
        byte_width = (w + 7) // 8
        byte = 0
        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byte_width + i // 8]
                if byte & 0x80:
                    self.write_pixel(x + i, y + j, self.textColor)

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
                self.draw_bmp_from_web(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_web(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            # Handle local file
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_sd(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_sd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")

    @staticmethod
    @micropython.viper
    def write_row(
        framebuf: ptr8,
        row: int,
        x0: int,
        width: int,
        rowdata: ptr8,
        invert: bool = False,
        dither: bool = False,
        display_mode: int = 1,
    ):
        __screen_width = const(1280)
        __screen_height = const(720)
        __bytes_per_row = const(300)  # For 4 pixels per byte mode
        __bytes_per_row_bw = const(150)  # For 8 pixels per byte mode

        # Safety checks with explicit type conversion
        row_val: int = int(row)
        x0_val: int = int(x0)
        width_val: int = int(width)

        if row_val < 0 or row_val >= __screen_height or x0_val < 0 or width_val <= 0:
            return

        # Calculate drawing boundaries
        draw_width: int = (
            width_val if (x0_val + width_val) <= __screen_width else __screen_width - x0_val
        )
        if draw_width <= 0:
            return

        # Inversion mask
        inv_mask: int = 0
        if display_mode == 0:
            inv_mask = 0x01 if invert else 0x00  # For 1-bit mode
        else:
            inv_mask = 0x03 if invert else 0x00  # For 2-bit mode

        # Initialize error buffers if dithering
        error_current = ptr8(bytearray(0))
        if dither:
            error_buf = bytearray(draw_width * 2)
            error_current = ptr8(error_buf)

        # Calculate framebuffer row position with explicit types
        fb_row_pos: int = 0
        if display_mode == 0:
            fb_row_pos = row_val * __bytes_per_row_bw + (x0_val // 8)
        else:
            fb_row_pos = row_val * __bytes_per_row + (x0_val // 4)

        col: int = 0
        while col < draw_width:
            if display_mode == 0:
                # 1-bit mode processing (8 pixels per byte)
                pix_grp: int = 8 if (col + 8) <= draw_width else draw_width - col
                packed: int = 0

                # Process each pixel in the group
                for i in range(int(pix_grp)):  # Explicit int conversion
                    # Safe array access
                    if (col + i) >= draw_width:
                        break

                    gray: int = int(rowdata[col + i])  # Explicit int conversion

                    # Apply dithering if enabled
                    if dither:
                        epos: int = (col + i) * 2
                        if epos + 1 < draw_width * 2:
                            err: int = int(error_current[epos]) | (
                                int(error_current[epos + 1]) << 8
                            )
                            if err & 0x8000:
                                err |= -65536
                            gray += err
                            gray = 255 if gray > 255 else (0 if gray < 0 else gray)

                    # Threshold to black or white and apply inversion
                    val: int = 0 if gray > 127 else 1
                    val ^= inv_mask

                    # Pack bits in proper order (MSB first)
                    packed |= val << i

                # Write to framebuffer with bounds checking
                fb_idx: int = fb_row_pos + (col // 8)
                if fb_idx >= 0 and fb_idx < (__bytes_per_row_bw * __screen_height):
                    if pix_grp == 8:
                        framebuf[fb_idx] = packed
                    else:
                        shift: int = 8 - int(pix_grp)  # Explicit int conversion here
                        mask: int = (0xFF >> shift) << shift
                        packed = (packed >> shift) << shift
                        old: int = int(framebuf[fb_idx])  # Explicit int conversion
                        framebuf[fb_idx] = (old & ~mask) | (packed & mask)
                col += 8

            else:
                # 2-bit mode processing (4 pixels per byte)
                pix_grp: int = 4 if (col + 4) <= draw_width else draw_width - col
                packed: int = 0

                for i in range(int(pix_grp)):  # Explicit int conversion
                    # Safe array access
                    if (col + i) >= draw_width:
                        break

                    gray: int = int(rowdata[col + i])  # Explicit int conversion

                    # Apply dithering if enabled
                    if dither:
                        epos: int = (col + i) * 2
                        if epos + 1 < draw_width * 2:
                            err: int = int(error_current[epos]) | (
                                int(error_current[epos + 1]) << 8
                            )
                            if err & 0x8000:
                                err |= -65536
                            gray += err
                            gray = 255 if gray > 255 else (0 if gray < 0 else gray)

                    # Convert to 2-bit value and apply inversion
                    val: int = (gray >> 6) ^ inv_mask
                    packed |= val << (i * 2)

                    # Calculate error for dithering
                    if dither and (col + i) < draw_width:
                        quant_val: int = val * 85
                        delta: int = gray - quant_val
                        epos = (col + i) * 2

                        # Floyd-Steinberg error diffusion with bounds checking
                        if col + i + 1 < draw_width:
                            # Right neighbor (7/16)
                            epos_right: int = epos + 2
                            if epos_right + 1 < draw_width * 2:
                                terr: int = int(error_current[epos_right]) | (
                                    int(error_current[epos_right + 1]) << 8
                                )
                                if terr & 0x8000:
                                    terr |= -65536
                                terr += (delta * 7) // 16
                                error_current[epos_right] = terr & 0xFF
                                error_current[epos_right + 1] = (terr >> 8) & 0xFF

                # Write to framebuffer with bounds checking
                fb_idx: int = fb_row_pos + (col // 4)
                if fb_idx >= 0 and fb_idx < (__bytes_per_row * __screen_height):
                    if pix_grp == 4:
                        framebuf[fb_idx] = packed
                    else:
                        mask: int = 0xFF >> (8 - int(pix_grp) * 2)  # Explicit int conversion
                        old: int = int(framebuf[fb_idx])  # Explicit int conversion
                        framebuf[fb_idx] = (old & ~mask) | (packed & mask)
                col += 4

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False):
        with open(path, "rb") as f:
            # Read BMP header
            header = f.read(54)
            if len(header) < 54 or header[0:2] != b"BM":
                raise ValueError("Not a valid BMP file")

            # Parse header information
            w = int.from_bytes(header[18:22], "little", True)
            h = int.from_bytes(header[22:26], "little", True)
            depth = int.from_bytes(header[28:30], "little")
            data_start = int.from_bytes(header[10:14], "little")

            if depth != 24:
                raise ValueError("Only 24-bit BMP files are supported")

            # Handle negative height (top-down BMP)
            flip_y = h > 0
            w = abs(w)
            h = abs(h)

            # Calculate drawing boundaries
            fb_width = min(w, self._width - x0)
            fb_height = min(h, self._height - y0)

            if fb_width <= 0 or fb_height <= 0:
                return  # Image would be drawn outside display area

            # BMP rows are padded to 4-byte boundaries
            row_size = (w * 3 + 3) & ~3

            # Prepare buffers
            temp_row = bytearray(fb_width)
            raw_buf = bytearray(row_size)

            # Seek to pixel data
            f.seek(data_start)

            display_mode = self.display_mode

            for row in range(h):
                bmp_y = h - 1 - row if flip_y else row
                if bmp_y >= fb_height:
                    f.readinto(raw_buf)  # Skip unused rows
                    continue

                # Read BMP row data
                f.readinto(raw_buf)

                # Convert to grayscale with optional dithering
                for col in range(fb_width):
                    i = col * 3
                    b = raw_buf[i]
                    g = raw_buf[i + 1]
                    r = raw_buf[i + 2]

                    # Calculate grayscale (faster integer approximation)
                    gray = (r * 77 + g * 151 + b * 28) >> 8  # ~= 0.299R + 0.587G + 0.114B

                    if invert:
                        gray = 255 - gray

                    # Store in temp row (will be processed by write_row)
                    temp_row[col] = gray

                # Write the row with optional dithering
                if display_mode == 1:
                    Inkplate.write_row(
                        self.ipg._framebuf,
                        y0 + bmp_y,
                        x0,
                        fb_width,
                        temp_row,
                        invert,
                        dither,
                        display_mode,
                    )
                elif display_mode == 0:
                    Inkplate.write_row(
                        self.ipm._framebuf,
                        y0 + bmp_y,
                        x0,
                        fb_width,
                        temp_row,
                        invert,
                        dither,
                        display_mode,
                    )

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False):
        """Display a BMP image downloaded from the web

        Args:
            bmp_data (bytes): Raw BMP file data
            x0 (int): X position to start drawing
            y0 (int): Y position to start drawing
            invert (bool): Whether to invert colors
            dither (bool): Whether to apply dithering
        """
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")

            bmp_data = response.content
            response.close()
            # Check if we have enough data for BMP headers
            if len(bmp_data) < 54:
                raise ValueError("Not enough data for BMP headers")

            # Check BMP signature
            if bmp_data[0:2] != b"BM":
                raise ValueError("Not a valid BMP file")

            # Parse header information using memoryview for efficiency
            header = memoryview(bmp_data)
            w = int.from_bytes(header[18:22], "little", True)
            h = int.from_bytes(header[22:26], "little", True)
            depth = int.from_bytes(header[28:30], "little")
            data_start = int.from_bytes(header[10:14], "little")

            if depth != 24:
                raise ValueError("Only 24-bit BMP files are supported")

            # Handle negative height (top-down BMP)
            flip_y = h > 0
            w = abs(w)
            h = abs(h)

            # Calculate drawing boundaries
            fb_width = min(w, self._width - x0)
            fb_height = min(h, self._height - y0)

            if fb_width <= 0 or fb_height <= 0:
                return  # Image would be drawn outside display area

            # BMP rows are padded to 4-byte boundaries
            row_size = (w * 3 + 3) & ~3

            # Prepare buffers
            temp_row = bytearray(fb_width)
            display_mode = self.display_mode

            # Get pixel data section
            if len(bmp_data) < data_start + row_size * h:
                raise ValueError("BMP data incomplete or corrupted")

            pixel_data = memoryview(bmp_data)[data_start:]

            for row in range(h):
                bmp_y = h - 1 - row if flip_y else row
                if bmp_y >= fb_height:
                    continue  # Skip unused rows

                # Get current row data
                row_start = row * row_size
                row_end = row_start + row_size
                raw_row = pixel_data[row_start:row_end]

                # Convert to grayscale with optional dithering
                for col in range(fb_width):
                    i = col * 3
                    b = raw_row[i]
                    g = raw_row[i + 1]
                    r = raw_row[i + 2]

                    # Fast grayscale conversion
                    gray = (r * 77 + g * 151 + b * 28) >> 8  # ~= 0.299R + 0.587G + 0.114B

                    if invert:
                        gray = 255 - gray

                    # Store in temp row
                    temp_row[col] = gray

                # Write the row with optional dithering
                target_framebuf = self.ipm._framebuf if display_mode == 0 else self.ipg._framebuf
                Inkplate.write_row(
                    target_framebuf,
                    y0 + bmp_y,
                    x0,
                    fb_width,
                    temp_row,
                    invert,
                    dither,
                    display_mode,
                )
                gc.collect()
        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()

    @staticmethod
    def decode_png_to_framebuffer(
        png_data, framebuf, x0, y0, invert=False, dither=False, display_mode=1
    ):
        import deflate
        import io
        from uctypes import addressof, bytearray_at

        _screen_width_ = const(1280)
        _screen_height_ = const(720)
        _bytes_per_row_ = const(320)  # For 4 pixels per byte mode
        _bytes_per_row_bw_ = const(160)  # For 8 pixels per byte mode

        @micropython.native
        def process_chunks(png_data):
            pos = 8  # Skip PNG signature
            ihdr = None
            idat_data = bytearray()
            while pos + 8 <= len(png_data):
                chunk_len = int.from_bytes(png_data[pos : pos + 4], "big")
                chunk_type = png_data[pos + 4 : pos + 8]
                chunk_start = pos + 8
                if chunk_type == b"IHDR":
                    ihdr = png_data[chunk_start : chunk_start + chunk_len]
                elif chunk_type == b"IDAT":
                    idat_data += png_data[chunk_start : chunk_start + chunk_len]
                elif chunk_type == b"IEND":
                    break
                pos += chunk_len + 12
            return ihdr, idat_data

        @micropython.viper
        def process_image(
            idat_data: ptr8,
            idat_len: int,
            framebuf: ptr8,
            width: int,
            height: int,
            bpp: int,
            x0: int,
            y0: int,
            invert: bool,
            dither: bool,
            display_mode: int,
        ):
            # Screen boundary checks
            draw_width: int = width if (x0 + width) <= _screen_width_ else _screen_width_ - x0
            draw_height: int = height if (y0 + height) <= _screen_height_ else _screen_height_ - y0

            if draw_width <= 0 or draw_height <= 0:
                return  # Nothing to draw

            # Pre-calculate constants
            inv_mask: int = 0x03 if invert and display_mode else 0x01 if invert else 0x00
            pixels_per_byte: int = 4 if display_mode else 8
            bytes_per_row: int = _bytes_per_row_ if display_mode else _bytes_per_row_bw_

            # Dithering setup
            if dither:
                errbuf_w: int = draw_width
                error_current_buf = bytearray(errbuf_w * 2)
                error_next_buf = bytearray(errbuf_w * 2)
                error_current = ptr8(addressof(error_current_buf))
                error_next = ptr8(addressof(error_next_buf))
                for i in range(errbuf_w * 2):
                    error_current[i] = 0
                    error_next[i] = 0

            # Image processing buffers
            row_size: int = width * bpp
            stride: int = row_size + 1
            cur_buf = bytearray(row_size)
            prev_buf = bytearray(row_size)
            cur = ptr8(addressof(cur_buf))
            prev = ptr8(addressof(prev_buf))
            for i in range(row_size):
                prev[i] = 0

            # Decompression
            idat_mv = bytearray_at(idat_data, idat_len)
            dstream = deflate.DeflateIO(io.BytesIO(idat_mv))

            for y in range(height):
                # Skip if this row is outside our draw area
                if y >= draw_height:
                    dstream.read(stride)  # Still need to read to advance
                    continue

                # Decompress and filter row
                raw = dstream.read(stride)
                if not raw:
                    break

                filt: int = int(raw[0])
                rp = ptr8(int(addressof(raw)) + 1)

                # Calculate framebuffer position
                fb_row_pos: int = (y0 + y) * bytes_per_row + (x0 // pixels_per_byte)

                # Process each pixel in row
                packed: int = 0
                pixels_in_packed: int = 0
                fb_idx: int = fb_row_pos

                for x in range(draw_width):
                    # Get pixel components with PNG filtering
                    px_pos: int = x * bpp
                    for k in range(bpp):
                        v: int = int(rp[px_pos + k])
                        if filt == 1:  # Sub
                            if px_pos >= bpp:
                                v = (v + cur[px_pos + k - bpp]) & 0xFF
                        elif filt == 2:  # Up
                            v = (v + prev[px_pos + k]) & 0xFF
                        elif filt == 3:  # Average
                            a: int = cur[px_pos + k - bpp] if px_pos >= bpp else 0
                            b: int = prev[px_pos + k]
                            v = (v + ((a + b) >> 1)) & 0xFF
                        elif filt == 4:  # Paeth
                            a = cur[px_pos + k - bpp] if px_pos >= bpp else 0
                            b = prev[px_pos + k]
                            c = prev[px_pos + k - bpp] if px_pos >= bpp else 0
                            p = a + b - c
                            pa = abs(p - a)
                            pb = abs(p - b)
                            pc = abs(p - c)
                            pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                            v = (v + pred) & 0xFF
                        cur[px_pos + k] = v

                    # Get color components
                    r: int = cur[px_pos]
                    g: int = cur[px_pos + 1] if bpp > 1 else r
                    b: int = cur[px_pos + 2] if bpp > 2 else r
                    alpha: int = cur[px_pos + 3] if bpp > 3 else 255

                    # Handle transparency and grayscale conversion
                    if alpha == 0:
                        gray: int = 255 if invert else 0
                    else:
                        if alpha < 255:
                            bg: int = 255 if invert else 0
                            r = (r * alpha + bg * (255 - alpha)) // 255
                            g = (g * alpha + bg * (255 - alpha)) // 255
                            b = (b * alpha + bg * (255 - alpha)) // 255
                        gray = (r * 77 + g * 151 + b * 28) >> 8

                    # Apply dithering if enabled
                    if dither:
                        epos: int = x * 2
                        err: int = int(error_current[epos]) | (int(error_current[epos + 1]) << 8)
                        if err & 0x8000:
                            err |= -65536
                        gray += err
                        gray = 255 if gray > 255 else (0 if gray < 0 else gray)

                    # Quantize based on display mode
                    if display_mode:
                        val: int = (gray >> 6) ^ inv_mask
                        packed |= val << (pixels_in_packed * 2)
                    else:
                        val: int = 0 if gray > 127 else 1
                        val ^= inv_mask
                        packed |= val << pixels_in_packed

                    pixels_in_packed += 1

                    # Error diffusion for dithering
                    if dither:
                        quant_val: int = val * 85 if display_mode else (val * 255)
                        delta: int = gray - quant_val

                        # Floyd-Steinberg dithering
                        if x + 1 < draw_width:
                            epos = (x + 1) * 2
                            terr: int = int(error_current[epos]) | (
                                int(error_current[epos + 1]) << 8
                            )
                            if terr & 0x8000:
                                terr |= -65536
                            terr += delta * 7 // 16
                            error_current[epos] = terr & 0xFF
                            error_current[epos + 1] = (terr >> 8) & 0xFF

                        if y + 1 < draw_height:
                            if x > 0:
                                epos = (x - 1) * 2
                                terr = int(error_next[epos]) | (int(error_next[epos + 1]) << 8)
                                if terr & 0x8000:
                                    terr |= -65536
                                terr += delta * 3 // 16
                                error_next[epos] = terr & 0xFF
                                error_next[epos + 1] = (terr >> 8) & 0xFF

                            epos = x * 2
                            terr = int(error_next[epos]) | (int(error_next[epos + 1]) << 8)
                            if terr & 0x8000:
                                terr |= -65536
                            terr += delta * 5 // 16
                            error_next[epos] = terr & 0xFF
                            error_next[epos + 1] = (terr >> 8) & 0xFF

                            if x + 1 < draw_width:
                                epos = (x + 1) * 2
                                terr = int(error_next[epos]) | (int(error_next[epos + 1]) << 8)
                                if terr & 0x8000:
                                    terr |= -65536
                                terr += delta * 1 // 16
                                error_next[epos] = terr & 0xFF
                                error_next[epos + 1] = (terr >> 8) & 0xFF

                    # Write packed pixels to framebuffer when we have a complete byte
                    if pixels_in_packed == pixels_per_byte or x == draw_width - 1:
                        if pixels_in_packed == pixels_per_byte:
                            framebuf[fb_idx] = packed
                        else:
                            # Handle partial bytes at row end
                            if display_mode:
                                shift = (pixels_per_byte - pixels_in_packed) * 2
                                mask = 0xFF >> shift
                                old = framebuf[fb_idx]
                                framebuf[fb_idx] = (old & ~mask) | ((packed << shift) & mask)
                            else:
                                shift = 8 - pixels_in_packed
                                mask = 0xFF >> shift
                                old = framebuf[fb_idx]
                                framebuf[fb_idx] = (old & ~mask) | ((packed << shift) & mask)

                        # Reset for next byte
                        packed = 0
                        pixels_in_packed = 0
                        fb_idx += 1

                # Swap error buffers for next row
                if dither:
                    tmp = error_current
                    error_current = error_next
                    error_next = tmp
                    for i in range(errbuf_w * 2):
                        error_next[i] = 0

                # Swap row buffers
                cur, prev = prev, cur

        try:
            # Fast PNG signature check
            if len(png_data) < 8 or png_data[1:4] != b"PNG":
                raise ValueError("Invalid PNG")

            ihdr, idat_data = process_chunks(png_data)
            if not ihdr:
                raise ValueError("Missing IHDR")
            if not idat_data:
                raise ValueError("No IDAT chunks")

            width = int.from_bytes(ihdr[0:4], "big")
            height = int.from_bytes(ihdr[4:8], "big")
            color_type = ihdr[9]
            bpp = 3 if color_type == 2 else 4

            # Process directly to framebuffer
            process_image(
                addressof(idat_data),
                len(idat_data),
                framebuf,
                width,
                height,
                bpp,
                x0,
                y0,
                invert,
                dither,
                display_mode,
            )

        except Exception as e:
            print("PNG decode error:", e)
            raise

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        with open(path, "rb") as f:
            png_data = f.read()
        if self.display_mode == 1:
            Inkplate.decode_png_to_framebuffer(
                png_data, self.ipg._framebuf, x0, y0, invert, dither, self.display_mode
            )
        elif self.display_mode == 0:
            Inkplate.decode_png_to_framebuffer(
                png_data, self.ipm._framebuf, x0, y0, invert, dither, self.display_mode
            )
        gc.collect()

    def draw_png_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()

            if self.display_mode == 1:
                Inkplate.decode_png_to_framebuffer(
                    png_data,
                    self.ipg._framebuf,
                    x0,
                    y0,
                    invert,
                    dither,
                    display_mode=self.display_mode,
                )
            elif self.display_mode == 0:
                Inkplate.decode_png_to_framebuffer(
                    png_data,
                    self.ipm._framebuf,
                    x0,
                    y0,
                    invert,
                    dither,
                    display_mode=self.display_mode,
                )
            gc.collect()

        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()

    def draw_jpg_from_sd(
        self, path, x0=0, y0=0, invert=False, dither: bool = False, kernel_type: int = 0
    ):
        import jpeg
        import gc

        try:
            # 1. Initialize decoder

            decoder = jpeg.Decoder(
                rotation=0,
                format="RGB565_LE",
                clipper_width=self._width,
                clipper_height=self._height,
            )

            # 2. Read file
            with open(path, "rb") as f:
                jpeg_data = f.read()

            # 3. Get image info before decoding
            try:
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            except Exception:
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]

            # 4. Decode image
            decoded = decoder.decode(jpeg_data)

            if self.display_mode == 1:
                Inkplate.write_image(
                    self.ipg._framebuf,
                    x0,
                    y0,
                    width,
                    height,
                    decoded,
                    invert,
                    dither,
                    kernel_type,
                    self.display_mode,
                )
            elif self.display_mode == 0:
                Inkplate.write_image(
                    self.ipm._framebuf,
                    x0,
                    y0,
                    width,
                    height,
                    decoded,
                    invert,
                    dither,
                    kernel_type,
                    self.display_mode,
                )

            gc.collect()

        except Exception as e:
            print("\nJPEG Decode error:", e)
            raise

    def draw_jpg_from_web(
        self, url, x0=0, y0=0, invert=False, dither: bool = False, kernel_type: int = 0
    ):
        import jpeg
        import gc
        import urequests

        try:
            # 1. Initialize decoder
            decoder = jpeg.Decoder(
                rotation=0,
                format="RGB565_LE",
                clipper_width=self._width,
                clipper_height=self._height,
            )

            # 2. Download the image (with timeout and basic error handling)
            response = urequests.get(url, timeout=20)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            jpeg_data = response.content
            response.close()

            try:
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            except Exception:
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]

            # 4. Decode image
            decoded = decoder.decode(jpeg_data)

            # 5. Display the image
            if self.display_mode == 1:
                Inkplate.write_image(
                    self.ipg._framebuf,
                    x0,
                    y0,
                    width,
                    height,
                    decoded,
                    invert,
                    dither,
                    kernel_type,
                    self.display_mode,
                )
            elif self.display_mode == 0:
                Inkplate.write_image(
                    self.ipm._framebuf,
                    x0,
                    y0,
                    width,
                    height,
                    decoded,
                    invert,
                    dither,
                    kernel_type,
                    self.display_mode,
                )

            # 6. Free memory
            gc.collect()

        except Exception as e:
            print("Error in draw_jpg_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    @staticmethod
    @micropython.viper
    def write_image(
        framebuf: ptr8,
        x0: int,
        y0: int,
        width: int,
        height: int,
        imagedata: ptr8,
        invert: bool = False,
        dither: bool = False,
        kernel_type: int = 0,
        display_mode: int = 1,
    ):
        _screen_width = const(1280)
        _screen_height = const(720)
        _bytes_per_row = const(320)
        _bytes_per_row_bw = const(160)

        # Predefined dithering kernels in ROM (faster access)
        fs_dx = ptr8(b"\x01\xff\x00\x01")
        fs_dy = ptr8(b"\x00\x01\x01\x01")
        fs_wt = ptr8(b"\x07\x03\x05\x01")

        jjn_dx = ptr8(b"\x01\x02\xfe\xff\x00\x01\x02")
        jjn_dy = ptr8(b"\x00\x00\x01\x01\x01\x01\x01")
        jjn_wt = ptr8(b"\x07\x05\x03\x05\x07\x05\x03")

        stucki_dx = ptr8(b"\x01\x02\xfe\xff\x00\x01\x02")
        stucki_dy = ptr8(b"\x00\x00\x01\x01\x01\x01\x01")
        stucki_wt = ptr8(b"\x08\x04\x02\x04\x08\x04\x02")

        burkes_dx = ptr8(b"\x01\x02\xfe\xff\x00\x01\x02")
        burkes_dy = ptr8(b"\x00\x00\x01\x01\x01\x01\x01")
        burkes_wt = ptr8(b"\x08\x04\x02\x04\x08\x04\x02")

        draw_width: int = width if (x0 + width) <= _screen_width else _screen_width - x0
        draw_height: int = height if (y0 + height) <= _screen_height else _screen_height - y0

        if display_mode == 0:
            inv_mask: int = 0x01 if invert else 0x00
        else:
            inv_mask: int = 0x03 if invert else 0x00

        # Dithering-specific optimizations
        if dither:
            errbuf_size: int = draw_width * 2
            error_current = ptr8(bytearray(errbuf_size))
            error_next = ptr8(bytearray(errbuf_size))

            # Select kernel with minimal branching
            if kernel_type == 1:
                dx_arr, dy_arr, wt_arr = jjn_dx, jjn_dy, jjn_wt
                kernel_len, divisor = 7, 48
            elif kernel_type == 2:
                dx_arr, dy_arr, wt_arr = stucki_dx, stucki_dy, stucki_wt
                kernel_len, divisor = 7, 42
            elif kernel_type == 3:
                dx_arr, dy_arr, wt_arr = burkes_dx, burkes_dy, burkes_wt
                kernel_len, divisor = 7, 32
            else:  # Floyd-Steinberg (default)
                dx_arr, dy_arr, wt_arr = fs_dx, fs_dy, fs_wt
                kernel_len, divisor = 4, 16

            # Precompute kernel bounds checks
        else:
            # Dummy pointers when not dithering
            error_current = ptr8(bytearray(0))
            error_next = ptr8(bytearray(0))

        for row in range(draw_height):
            if display_mode == 0:
                fb_row_pos: int = (y0 + row) * _bytes_per_row_bw + (x0 // 8)
            else:
                fb_row_pos: int = (y0 + row) * _bytes_per_row + (x0 // 4)

            img_row_start: int = row * width * 2

            col: int = 0
            while col < draw_width:
                if display_mode == 0:
                    # 1-bit mode processing (8 pixels per byte)
                    # Process groups of 8 pixels (1 byte) or less at row ends
                    pix_grp: int = 8 if (col + 8) <= draw_width else draw_width - col
                    packed: int = 0

                    # Process each pixel in the group
                    for i in range(pix_grp):
                        # Get pixel from source image (16-bit color)
                        idx: int = img_row_start + (col + i) * 2
                        pixel: int = imagedata[idx] | (imagedata[idx + 1] << 8)

                        # Convert to grayscale
                        r: int = ((pixel >> 11) & 0x1F) * 255 // 31
                        g: int = ((pixel >> 5) & 0x3F) * 255 // 63
                        b: int = (pixel & 0x1F) * 255 // 31
                        gray: int = (r * 299 + g * 587 + b * 114) // 1000

                        if dither:
                            epos: int = (col + i) * 2
                            err: int = int(error_current[epos]) | (
                                int(error_current[epos + 1]) << 8
                            )
                            if err & 0x8000:
                                err -= 65536
                            gray += err
                            gray = 255 if gray > 255 else (0 if gray < 0 else gray)

                        val: int = 0 if gray > 127 else 1
                        val ^= inv_mask
                        packed |= val << i

                    fb_idx = fb_row_pos + (col // 8)
                    if pix_grp == 8:
                        framebuf[fb_idx] = packed
                    else:
                        mask = 0xFF >> (8 - pix_grp)
                        framebuf[fb_idx] = (framebuf[fb_idx] & ~mask) | (packed & mask)
                    col += 8

                else:
                    # 2-bit mode processing - optimized dithering
                    pix_grp: int = 4 if (col + 4) <= draw_width else draw_width - col
                    packed: int = 0
                    for i in range(pix_grp):
                        idx: int = img_row_start + (col + i) * 2
                        pixel: int = imagedata[idx] | (imagedata[idx + 1] << 8)

                        r: int = ((pixel >> 11) & 0x1F) * 255 // 31
                        g: int = ((pixel >> 5) & 0x3F) * 255 // 63
                        b: int = (pixel & 0x1F) * 255 // 31
                        gray: int = (r * 77 + g * 151 + b * 28) >> 8

                        if dither:
                            epos: int = (col + i) * 2
                            err: int = error_current[epos] | (error_current[epos + 1] << 8)
                            if err & 0x8000:
                                err |= -65536
                            gray += err
                            if gray > 255:
                                gray = 255
                            elif gray < 0:
                                gray = 0

                        val: int = (gray >> 6) ^ inv_mask
                        packed |= val << (i * 2)

                        if dither:
                            quant_val = val * 85
                            delta = gray - quant_val
                            error_current[epos] = 0
                            error_current[epos + 1] = 0

                            for ka in range(int(kernel_len)):
                                dx: int = int(dx_arr[ka])
                                dy: int = int(dy_arr[ka])
                                wt: int = int(wt_arr[ka])
                                nx: int = col + i + dx
                                ny: int = row + dy
                                if 0 <= nx < draw_width and ny < draw_height:
                                    target = error_next if dy else error_current
                                    tpos: int = nx * 2
                                    terr: int = target[tpos] | (target[tpos + 1] << 8)
                                    if terr & 0x8000:
                                        terr |= -65536
                                    terr += (delta * wt) // int(divisor)
                                    if terr > 32767:
                                        terr = 32767
                                    elif terr < -32768:
                                        terr = -32768
                                    target[tpos] = terr & 0xFF
                                    target[tpos + 1] = (terr >> 8) & 0xFF

                    fb_idx = fb_row_pos + (col // 4)
                    if pix_grp == 4:
                        framebuf[fb_idx] = packed
                    else:
                        mask = 0xFF >> (8 - pix_grp * 2)
                        framebuf[fb_idx] = (framebuf[fb_idx] & ~mask) | (packed & mask)
                    col += 4

            if dither:
                # Swap buffers efficiently
                tmp = error_current
                error_current = error_next
                error_next = tmp
                # Clear next buffer in one pass
                for i in range(errbuf_size):
                    error_next[i] = 0


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
