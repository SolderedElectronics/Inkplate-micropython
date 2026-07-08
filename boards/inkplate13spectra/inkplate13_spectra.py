"""MicroPython driver for the Inkplate 13 SPECTRA e-paper display.

Ported from the Arduino Inkplate13Driver implementation.
"""

import time
import os
from machine import ADC, I2C, SPI, Pin, SDCard
from micropython import const
from pcal6416a import *
from gfx import GFX
import machine

machine.freq(240000000)

# Connections between ESP32-S3 and Spectra133 Epaper
EPAPER_RST_PIN = const(4)
EPAPER_DC_PIN = const(14)
EPAPER_CS_M_PIN = const(42)  # Master chip select
EPAPER_CS_S_PIN = const(39)  # Slave chip select
EPAPER_BUSY_PIN = const(7)
EPAPER_SPI_MOSI = const(40)
EPAPER_SPI_MISO = const(41)
EPAPER_SPI_SCK = const(38)
EPAPER_PWR_EN = const(21)
EPAPER_BS0 = const(6)
EPAPER_BS1 = const(5)

pixel_mask_glut = [0xF, 0xF0]

# Spectra133 register addresses
SPECTRA133_REG_PSR = const(0x00)
SPECTRA133_REG_PWR = const(0x01)
SPECTRA133_REG_POF = const(0x02)
SPECTRA133_REG_PON = const(0x04)
SPECTRA133_REG_BTST_N = const(0x05)
SPECTRA133_REG_BTST_P = const(0x06)
SPECTRA133_REG_DTM = const(0x10)
SPECTRA133_REG_DRF = const(0x12)
SPECTRA133_REG_PLL = const(0x30)
SPECTRA133_REG_TSC = const(0x40)
SPECTRA133_REG_CDI = const(0x50)
SPECTRA133_REG_TCON = const(0x60)
SPECTRA133_REG_TRES = const(0x61)
SPECTRA133_REG_AN_TM = const(0x74)
SPECTRA133_REG_AGID = const(0x86)
SPECTRA133_REG_BUCK_BOOST_VDDN = const(0xB0)
SPECTRA133_REG_TFT_VCOM_POWER = const(0xB1)
SPECTRA133_REG_EN_BUF = const(0xB6)
SPECTRA133_REG_BOOST_VDDP_EN = const(0xB7)
SPECTRA133_REG_CCSET = const(0xE0)
SPECTRA133_REG_PWS = const(0xE3)
SPECTRA133_REG_CMD66 = const(0xF0)

# Spectra133 register values (from manufacturer)
REG_PSR_V = bytes([0xDF, 0x6B])
REG_PWR_V = bytes([0x0F, 0x00, 0x28, 0x2C, 0x28, 0x38])
REG_POF_V = bytes([0x00])
REG_DRF_V = bytes([0x00])
REG_PLL_V = bytes([0x08])
REG_CDI_V = bytes([0xF7])
REG_TCON_V = bytes([0x03, 0x03])
REG_TRES_V = bytes([0x04, 0xB0, 0x03, 0x20])
REG_CMD66_V = bytes([0x49, 0x55, 0x13, 0x5D, 0x05, 0x10])
REG_EN_BUF_V = bytes([0x07])
REG_CCSET_V = bytes([0x01])
REG_PWS_V = bytes([0x22])
REG_AN_TM_V = bytes([0xC0, 0x1C, 0x1C, 0xCC, 0xCC, 0xCC, 0x15, 0x15, 0x55])
REG_AGID_V = bytes([0x10])
REG_BTST_P_V = bytes([0xD8, 0x18])
REG_BOOST_VDDP_EN_V = bytes([0x01])
REG_BTST_N_V = bytes([0xD8, 0x18])
REG_BUCK_BOOST_VDDN_V = bytes([0x01])
REG_TFT_VCOM_POWER_V = bytes([0x02])

# Epaper resolution
D_COLS = const(1200)
D_ROWS = const(1600)

# Chip select targets for dual-driver architecture
CHIP_MASTER = const(1)
CHIP_SLAVE = const(2)
CHIP_BOTH = const(3)

# User pins on PCAL6416A for Inkplate COLOR
IO_PIN_A0 = const(0)
IO_PIN_A1 = const(1)
IO_PIN_A2 = const(2)
IO_PIN_A3 = const(3)
IO_PIN_A4 = const(4)
IO_PIN_A5 = const(5)
IO_PIN_A6 = const(6)
IO_PIN_A7 = const(7)

IO_PIN_B0 = const(8)
IO_PIN_B1 = const(9)
IO_PIN_B2 = const(10)
IO_PIN_B3 = const(11)
IO_PIN_B4 = const(12)
IO_PIN_B5 = const(13)
IO_PIN_B6 = const(14)
IO_PIN_B7 = const(15)

RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04


class Inkplate:
    # Color constants - values are panel color indices
    # User passes 0-5, _color_palette maps to actual panel values
    BLACK = const(0)
    WHITE = const(1)
    YELLOW = const(2)
    RED = const(3)
    BLUE = const(4)
    GREEN = const(5)

    # Maps user color index (0-5) to panel register value
    _color_palette = [0, 1, 2, 3, 5, 6]

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    text_size = 1

    _panel_state = False

    _framebuf = None

    @classmethod
    def begin(cls):
        cls.wire = I2C(0)
        cls._PCAL6416A = PCAL6416A(cls.wire)

        # Initialize SPI with Spectra133 pins at 10MHz
        cls.spi = SPI(
            2,
            baudrate=10000000,
            polarity=0,
            phase=0,
            firstbit=SPI.MSB,
            sck=Pin(EPAPER_SPI_SCK),
            mosi=Pin(EPAPER_SPI_MOSI),
            miso=Pin(EPAPER_SPI_MISO),
        )

        # Initialize panel control pins
        cls.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
        cls.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT)
        cls.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT)
        cls.EPAPER_CS_M_PIN = Pin(EPAPER_CS_M_PIN, Pin.OUT)
        cls.EPAPER_CS_S_PIN = Pin(EPAPER_CS_S_PIN, Pin.OUT)
        cls.EPAPER_PWR_EN = Pin(EPAPER_PWR_EN, Pin.OUT)
        cls.EPAPER_BS0 = Pin(EPAPER_BS0, Pin.OUT)
        cls.EPAPER_BS1 = Pin(EPAPER_BS1, Pin.OUT)

        cls.VBAT = ADC(Pin(1))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)
        cls.VBAT_EN = GpioPin(cls._PCAL6416A, 9, mode_output)
        cls.VBAT_EN.digital_write(0)

        cls.cursor = [0, 0]
        cls.textColor = 0
        cls.textWrapping = 1

        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, 10, mode_output)

        # Discharge panel capacitors first
        cls.set_panel_pins_to_low()

        # Allocate framebuffer (4bpp, 2 pixels per byte)
        # Single C-level bytes multiply + bytearray copy - no Python loop
        cls._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))

        # Set default rotation (landscape, matching Arduino initDriver)
        cls.rotation = 1
        cls._width = D_ROWS
        cls._height = D_COLS

        cls.GFX = GFX(
            cls._width,
            cls._height,
            cls.write_pixel,
            cls.write_fast_hline,
            cls.write_fast_vline,
            cls.write_fill_rect,
            None,
            None,
        )
        # Physical framebuffer row width for direct-write functions (text rendering)
        cls.GFX.phys_row_bytes = D_COLS // 2
        # Color palette for mapping user indices to panel values in text rendering
        cls.GFX.color_palette = cls._color_palette
        # Sync rotation so text rendering applies the correct transform
        cls.GFX.rotation = cls.rotation

        cls.set_pcal_for_low_power()

        cls._panel_state = False

        return True

    def init_sd_card(self, fast_boot=False):
        self.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(slot=3, miso=Pin(13), mosi=Pin(11), sck=Pin(12), cs=Pin(10)),
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
        self.SD_ENABLE.digital_write(1)
        time.sleep_ms(5)

    def sd_card_wake(self):
        self.SD_ENABLE.digital_write(0)
        time.sleep_ms(5)

    @classmethod
    def set_pcal_for_low_power(cls):
        for x in range(16):
            cls._PCAL6416A.pin_mode(int(x), mode_output)
            cls._PCAL6416A.digital_write(int(x), 0)

    @classmethod
    def get_panel_state(cls):
        return cls._panel_state

    @classmethod
    def set_panel_pins_to_low(cls):
        """Discharge panel capacitors by driving all pins low."""
        cls.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT, value=0)
        cls.EPAPER_CS_M_PIN = Pin(EPAPER_CS_M_PIN, Pin.OUT, value=0)
        cls.EPAPER_CS_S_PIN = Pin(EPAPER_CS_S_PIN, Pin.OUT, value=0)
        cls.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT, value=0)
        cls.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.OUT, value=0)
        cls.EPAPER_PWR_EN = Pin(EPAPER_PWR_EN, Pin.OUT, value=0)
        cls.EPAPER_BS0 = Pin(EPAPER_BS0, Pin.OUT, value=0)
        cls.EPAPER_BS1 = Pin(EPAPER_BS1, Pin.OUT, value=0)

    @classmethod
    def set_io(cls):
        """Configure GPIOs and SPI for panel communication."""
        cls.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT, value=1)
        cls.EPAPER_CS_M_PIN = Pin(EPAPER_CS_M_PIN, Pin.OUT, value=1)
        cls.EPAPER_CS_S_PIN = Pin(EPAPER_CS_S_PIN, Pin.OUT, value=1)
        cls.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT, value=0)
        cls.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN, Pin.PULL_UP)
        cls.EPAPER_PWR_EN = Pin(EPAPER_PWR_EN, Pin.OUT, value=0)
        cls.EPAPER_BS0 = Pin(EPAPER_BS0, Pin.OUT, value=0)
        cls.EPAPER_BS1 = Pin(EPAPER_BS1, Pin.OUT, value=1)

        # Re-init SPI after pin reconfiguration
        cls.spi = SPI(
            2,
            baudrate=10000000,
            polarity=0,
            phase=0,
            firstbit=SPI.MSB,
            sck=Pin(EPAPER_SPI_SCK),
            mosi=Pin(EPAPER_SPI_MOSI),
            miso=Pin(EPAPER_SPI_MISO),
        )

    @classmethod
    def reset_panel(cls):
        """Hardware reset of the panel."""
        cls.EPAPER_RST_PIN.value(0)
        time.sleep_ms(100)
        cls.EPAPER_RST_PIN.value(1)
        time.sleep_ms(100)

    @classmethod
    def wait_for_busy(cls):
        """Wait until the panel signals ready (BUSY pin goes high)."""
        while not cls.EPAPER_BUSY_PIN.value():
            time.sleep_ms(1)

    @classmethod
    def screen_init(cls):
        """Send manufacturer register init sequence to the panel."""
        cls.send_command(SPECTRA133_REG_AN_TM, REG_AN_TM_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_CMD66, REG_CMD66_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PSR, REG_PSR_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PLL, REG_PLL_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_CDI, REG_CDI_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_TCON, REG_TCON_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_AGID, REG_AGID_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PWS, REG_PWS_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_CCSET, REG_CCSET_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_TRES, REG_TRES_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PWR, REG_PWR_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_EN_BUF, REG_EN_BUF_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BTST_P, REG_BTST_P_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BOOST_VDDP_EN, REG_BOOST_VDDP_EN_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BTST_N, REG_BTST_N_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BUCK_BOOST_VDDN, REG_BUCK_BOOST_VDDN_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_TFT_VCOM_POWER, REG_TFT_VCOM_POWER_V, CHIP_MASTER)

    @classmethod
    def set_panel_state(cls, state):
        """Power on/off the panel. When powering on, performs full init sequence."""
        if state == cls._panel_state:
            return

        if state:
            # Power up sequence
            cls.set_panel_pins_to_low()
            time.sleep_ms(50)

            # Configure GPIOs
            cls.set_io()

            # Enable power
            cls.EPAPER_PWR_EN.value(1)
            time.sleep_ms(100)

            # Hardware reset
            cls.reset_panel()
            time.sleep_ms(100)

            # Send init registers
            cls.screen_init()

            # Power on command
            cls.send_command(SPECTRA133_REG_PON, None, CHIP_BOTH)
            cls.wait_for_busy()
        else:
            # Power off sequence
            cls.send_command(SPECTRA133_REG_POF, REG_POF_V, CHIP_BOTH)
            cls.wait_for_busy()

            # Set pins to input to save power
            cls.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.IN)
            cls.EPAPER_CS_M_PIN = Pin(EPAPER_CS_M_PIN, Pin.IN)
            cls.EPAPER_CS_S_PIN = Pin(EPAPER_CS_S_PIN, Pin.IN)
            cls.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.IN)
            cls.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
            cls.EPAPER_PWR_EN = Pin(EPAPER_PWR_EN, Pin.IN)

            # Disable power
            Pin(EPAPER_PWR_EN, Pin.OUT, value=0)

        cls._panel_state = state

    @classmethod
    def send_command(cls, cmd, data=None, chip_id=CHIP_BOTH):
        """Send a command (and optional data) to master, slave, or both chips."""
        # Assert chip select(s)
        if chip_id & CHIP_SLAVE:
            cls.EPAPER_CS_S_PIN.value(0)
        if chip_id & CHIP_MASTER:
            cls.EPAPER_CS_M_PIN.value(0)

        # Send command byte
        cls.spi.write(bytes([cmd]))

        # Send data bytes if provided
        if data is not None:
            cls.spi.write(data)

        # Release chip select(s)
        if chip_id & CHIP_SLAVE:
            cls.EPAPER_CS_S_PIN.value(1)
        if chip_id & CHIP_MASTER:
            cls.EPAPER_CS_M_PIN.value(1)

    @classmethod
    def clear_display(cls):
        if cls._framebuf is None:
            cls._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))
        else:
            cls._framebuf[:] = b"\x11" * len(cls._framebuf)

    @classmethod
    def display(cls, leave_on=False):
        """Update display with framebuffer data using dual-chip architecture."""
        # Power up the panel
        cls.set_panel_state(True)

        mv = memoryview(cls._framebuf)
        half_row = D_COLS // 4  # 300 bytes per half-row

        # Send data to master chip (left side of screen)
        cls.EPAPER_CS_M_PIN.value(0)
        cls.EPAPER_CS_S_PIN.value(1)
        cls.spi.write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2)
            cls.spi.write(mv[row_start : row_start + half_row])
        cls.EPAPER_CS_M_PIN.value(1)

        # Send data to slave chip (right side of screen)
        cls.EPAPER_CS_M_PIN.value(1)
        cls.EPAPER_CS_S_PIN.value(0)
        cls.wait_for_busy()
        cls.spi.write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2) + half_row
            cls.spi.write(mv[row_start : row_start + half_row])
        cls.EPAPER_CS_S_PIN.value(1)

        # Deselect both chips
        cls.EPAPER_CS_S_PIN.value(1)
        cls.EPAPER_CS_M_PIN.value(1)
        cls.wait_for_busy()

        # Force display refresh on both chips
        cls.send_command(SPECTRA133_REG_DRF, REG_DRF_V, CHIP_BOTH)
        cls.wait_for_busy()

        # Power off if not requested to leave on
        if not leave_on:
            cls.set_panel_state(False)

    @classmethod
    def gpio_expander_pin(cls, pin, mode):
        return GpioPin(cls._PCAL6416A, pin, mode)

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

        cls.wire.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        rtc_year = rtc_yr - 2000

        data = bytearray(
            [
                RTC_RAM_by,
                170,  # Write in RAM 170 to know that RTC is set
            ]
        )

        cls.wire.writeto(RTC_I2C_ADDR, data)

        data = bytearray(
            [
                RTC_DAY_ADDR,
                cls.rtc_dec_to_bcd(rtc_day),
                cls.rtc_dec_to_bcd(rtc_weekday),
                cls.rtc_dec_to_bcd(rtc_month),
                cls.rtc_dec_to_bcd(rtc_year),
            ]
        )

        cls.wire.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_get_rtc_data(cls):
        cls.wire.writeto(RTC_I2C_ADDR, bytearray([RTC_SECOND_ADDR]))
        data = cls.wire.readfrom(RTC_I2C_ADDR, 7)

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

    @classmethod
    def clean(cls):
        """Clear the physical display by sending all-white data."""
        cls.set_panel_state(True)

        half_row = D_COLS // 4  # 300 bytes per half-row
        white_half = b"\x11" * half_row

        # Send white data to master chip (left side)
        cls.EPAPER_CS_M_PIN.value(0)
        cls.EPAPER_CS_S_PIN.value(1)
        cls.spi.write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            cls.spi.write(white_half)
        cls.EPAPER_CS_M_PIN.value(1)

        # Send white data to slave chip (right side)
        cls.EPAPER_CS_M_PIN.value(1)
        cls.EPAPER_CS_S_PIN.value(0)
        cls.wait_for_busy()
        cls.spi.write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            cls.spi.write(white_half)
        cls.EPAPER_CS_S_PIN.value(1)

        # Deselect both
        cls.EPAPER_CS_S_PIN.value(1)
        cls.EPAPER_CS_M_PIN.value(1)
        cls.wait_for_busy()

        # Force display refresh
        cls.send_command(SPECTRA133_REG_DRF, REG_DRF_V, CHIP_BOTH)
        cls.wait_for_busy()

        cls.set_panel_state(False)

    @classmethod
    def width(cls):
        return cls._width

    @classmethod
    def height(cls):
        return cls._height

    # Arduino compatibility functions
    @classmethod
    def set_rotation(cls, x):
        cls.rotation = x % 4
        if cls.rotation == 0 or cls.rotation == 2:
            cls.GFX.width = D_COLS
            cls.GFX.height = D_ROWS
            cls._width = D_COLS
            cls._height = D_ROWS
        elif cls.rotation == 1 or cls.rotation == 3:
            cls.GFX.width = D_ROWS
            cls.GFX.height = D_COLS
            cls._width = D_ROWS
            cls._height = D_COLS
        cls.GFX.rotation = cls.rotation

    @classmethod
    def get_rotation(cls):
        return cls.rotation

    @classmethod
    def draw_pixel(cls, x, y, c):
        cls.start_write()
        cls.write_pixel(x, y, c)
        cls.end_write()

    @classmethod
    def start_write(cls):
        pass

    @classmethod
    @micropython.native
    def write_pixel(cls, x, y, c):
        w = cls.width()
        h = cls.height()

        if x < 0 or y < 0 or x >= w or y >= h:
            return
        if c > 5:
            return

        # Map user color index to panel color value
        c = cls._color_palette[c]

        r = cls.rotation
        if r == 0:
            x = w - x - 1
            y = h - y - 1
        elif r == 1:
            x, y = y, w - x - 1
        elif r == 3:
            x, y = h - y - 1, x
        # r == 2: no change needed

        idx = (D_COLS * y) >> 1
        shift = (x & 1) * 4
        mask = pixel_mask_glut[x & 1]

        cls._framebuf[idx + (x >> 1)] = (cls._framebuf[idx + (x >> 1)] & mask) | (c << (4 - shift))

    @classmethod
    def write_fill_rect(cls, x, y, w, h, c):
        for j in range(w):
            for i in range(h):
                cls.write_pixel(x + j, y + i, c)

    @classmethod
    def write_fast_vline(cls, x, y, h, c):
        for i in range(h):
            cls.write_pixel(x, y + i, c)

    @classmethod
    def write_fast_hline(cls, x, y, w, c):
        for i in range(w):
            cls.write_pixel(x + i, y, c)

    @classmethod
    def set_text_color(cls, c):
        cls.textColor = c

    @classmethod
    def write_line(cls, x0, y0, x1, y1, c):
        cls.GFX.line(x0, y0, x1, y1, c)

    @classmethod
    def end_write(cls):
        pass

    @classmethod
    def draw_fast_vline(cls, x, y, h, c):
        cls.start_write()
        cls.write_fast_vline(x, y, h, c)
        cls.end_write()

    @classmethod
    def draw_fast_hline(cls, x, y, w, c):
        cls.start_write()
        cls.write_fast_hline(x, y, w, c)
        cls.end_write()

    @classmethod
    def fill_rect(cls, x, y, w, h, c):
        cls.start_write()
        cls.write_fill_rect(x, y, w, h, c)
        cls.end_write()

    @classmethod
    def fill_screen(cls, c):
        cls.fill_rect(0, 0, cls.width(), cls.height(), c)

    @classmethod
    def draw_line(cls, x0, y0, x1, y1, c):
        cls.start_write()
        cls.write_line(x0, y0, x1, y1, c)
        cls.end_write()

    @classmethod
    def draw_rect(cls, x, y, w, h, c):
        cls.GFX.rect(x, y, w, h, c)

    @classmethod
    def draw_circle(cls, x, y, r, c):
        cls.GFX.circle(x, y, r, c)

    @classmethod
    def fill_circle(cls, x, y, r, c):
        cls.GFX.fill_circle(x, y, r, c)

    @classmethod
    def draw_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        cls.GFX.triangle(x0, y0, x1, y1, x2, y2, c)

    @classmethod
    def fill_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        cls.GFX.fill_triangle(x0, y0, x1, y1, x2, y2, c)

    @classmethod
    def draw_round_rect(cls, x, y, q, h, r, c):
        cls.GFX.round_rect(x, y, q, h, r, c)

    @classmethod
    def fill_round_rect(cls, x, y, q, h, r, c):
        cls.GFX.fill_round_rect(x, y, q, h, r, c)

    @classmethod
    def set_text_wrapping(cls, state: bool):
        cls.textWrapping = state

    @classmethod
    def set_display_mode(cls, mode):
        cls.displayMode = mode

    @classmethod
    def select_display_mode(cls, mode):
        cls.displayMode = mode

    @classmethod
    def get_display_mode(cls):
        return cls.displayMode

    @classmethod
    def set_text_size(cls, s):
        cls.text_size = s

    @classmethod
    def set_font(cls, f):
        cls.GFX.font_family = f
        cls.GFX.font = cls.GFX.font_family._font

    def reset_cursor(self):
        self.cursor = [0, 0]

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    def print_text(self, x, y, s):
        self.GFX._print_text(
            self._framebuf,
            x,
            y,
            s,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )

    def println(self, text):
        self.cursor, line_height = self.GFX._print_text(
            self._framebuf,
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
        self.cursor, line_height = self.GFX._print_text(
            self._framebuf,
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

    def read_battery(self):
        self.VBAT_EN.digital_write(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(1)
        value = self.VBAT.read()
        self.VBAT_EN.digital_write(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    @classmethod
    def draw_bitmap(cls, x, y, data, w, h, c=BLACK):
        byte_width = (w + 7) // 8
        byte = 0
        cls.start_write()
        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byte_width + i // 8]
                if byte & 0x80:
                    cls.write_pixel(x + i, y + j, c)
        cls.end_write()

    def draw_color_image(self, x, y, width, height, image):
        for i in range(0, len(image)):
            # Unpack the byte into two pixel values
            pixel_value1 = (image[i] & 0b11110000) >> 4
            pixel_value2 = image[i] & 0b00001111

            # Calculate the x and y coordinates of the pixels
            x1 = (2 * i) % width
            y1 = (2 * i) // width
            x2 = (2 * i + 1) % width
            y2 = (2 * i + 1) // width

            # Check if the coordinates are within the image bounds
            if x1 < width and y1 < height:
                self.write_pixel(x1 + x, y1 + y, pixel_value1)
            if x2 < width and y2 < height:
                self.write_pixel(x2 + x, y2 + y, pixel_value2)

    def rtc_get_data(self):
        return self.rtc_get_rtc_data()

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
            except Exception as e:
                print(e)
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]

            # 4. Decode image
            decoded = decoder.decode(jpeg_data)

            Inkplate.write_image(
                self._framebuf,
                x0,
                y0,
                width,
                height,
                decoded,
                invert,
                dither,
                kernel_type,
            )

            gc.collect()

        except Exception as e:
            print("\nJPEG Decode error:", e)
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
        invert: bool,
        dither: bool,
        kernel_type: int,
    ):
        # Physical framebuffer: 1200 columns x 1600 rows, 4bpp
        _phys_width = const(1200)
        _bytes_per_row = const(_phys_width // 2)  # 600 bytes per physical row
        # Logical screen dimensions (rotation 1: landscape)
        _screen_width = const(1600)
        _screen_height = const(1200)

        # Dithering kernels (dx, dy, wt) — weights will be pre-scaled (<<6) to avoid divides
        fs_dx = (1, -1, 0, 1)
        fs_dy = (0, 1, 1, 1)
        fs_wt = (7, 3, 5, 1)
        fs_div = 16

        jjn_dx = (1, 2, -2, -1, 0, 1, 2)
        jjn_dy = (0, 0, 1, 1, 1, 1, 1)
        jjn_wt = (7, 5, 3, 5, 7, 5, 3)
        jjn_div = 48

        stucki_dx = (1, 2, -2, -1, 0, 1, 2)
        stucki_dy = (0, 0, 1, 1, 1, 1, 1)
        stucki_wt = (8, 4, 2, 4, 8, 4, 2)
        stucki_div = 42

        burkes_dx = (1, 2, -2, -1, 0, 1, 2)
        burkes_dy = (0, 0, 1, 1, 1, 1, 1)
        burkes_wt = (8, 4, 2, 4, 8, 4, 2)
        burkes_div = 32

        # Palette flattened: 6 Spectra colors
        # Panel values: 0=black, 1=white, 2=yellow, 3=red, 5=blue, 6=green

        draw_width: int = width if (x0 + width) <= _screen_width else _screen_width - x0
        draw_height: int = height if (y0 + height) <= _screen_height else _screen_height - y0

        inv_mask: int = 0x0F if invert else 0x00

        # Select kernel and pre-scale weights by 64 (>>6 later)
        dx0: int = 0
        dx1: int = 0
        dx2: int = 0
        dx3: int = 0
        dx4: int = 0
        dx5: int = 0
        dx6: int = 0
        dy0: int = 0
        dy1: int = 0
        dy2: int = 0
        dy3: int = 0
        dy4: int = 0
        dy5: int = 0
        dy6: int = 0

        # Prepare dithering
        kernel_len: int = 0
        if dither:
            errbuf_size: int = (
                draw_width * 3
            )  # RGB error per pixel (signed byte in [-128,127] encoded as 0..255)
            error_current = bytearray(errbuf_size)
            error_next = bytearray(errbuf_size)
            error_current_ptr = ptr8(error_current)
            error_next_ptr = ptr8(error_next)

            # Select kernel and pre-scale weights by 64 (>>6 later)
            # Select kernel and pre-scale weights by 64 (>>6 later)
            if kernel_type == 1:
                # Jarvis, Judice, Ninke
                dx0 = int(jjn_dx[0])
                dy0 = int(jjn_dy[0])
                dx1 = int(jjn_dx[1])
                dy1 = int(jjn_dy[1])
                dx2 = int(jjn_dx[2])
                dy2 = int(jjn_dy[2])
                dx3 = int(jjn_dx[3])
                dy3 = int(jjn_dy[3])
                dx4 = int(jjn_dx[4])
                dy4 = int(jjn_dy[4])
                dx5 = int(jjn_dx[5])
                dy5 = int(jjn_dy[5])
                dx6 = int(jjn_dx[6])
                dy6 = int(jjn_dy[6])
                coeff0: int = (int(jjn_wt[0]) << 6) // jjn_div
                coeff1: int = (int(jjn_wt[1]) << 6) // jjn_div
                coeff2: int = (int(jjn_wt[2]) << 6) // jjn_div
                coeff3: int = (int(jjn_wt[3]) << 6) // jjn_div
                coeff4: int = (int(jjn_wt[4]) << 6) // jjn_div
                coeff5: int = (int(jjn_wt[5]) << 6) // jjn_div
                coeff6: int = (int(jjn_wt[6]) << 6) // jjn_div
                kernel_len: int = 7

            elif kernel_type == 2:
                # Stucki
                dx0 = int(stucki_dx[0])
                dy0 = int(stucki_dy[0])
                dx1 = int(stucki_dx[1])
                dy1 = int(stucki_dy[1])
                dx2 = int(stucki_dx[2])
                dy2 = int(stucki_dy[2])
                dx3 = int(stucki_dx[3])
                dy3 = int(stucki_dy[3])
                dx4 = int(stucki_dx[4])
                dy4 = int(stucki_dy[4])
                dx5 = int(stucki_dx[5])
                dy5 = int(stucki_dy[5])
                dx6 = int(stucki_dx[6])
                dy6 = int(stucki_dy[6])
                coeff0: int = (int(stucki_wt[0]) << 6) // stucki_div
                coeff1: int = (int(stucki_wt[1]) << 6) // stucki_div
                coeff2: int = (int(stucki_wt[2]) << 6) // stucki_div
                coeff3: int = (int(stucki_wt[3]) << 6) // stucki_div
                coeff4: int = (int(stucki_wt[4]) << 6) // stucki_div
                coeff5: int = (int(stucki_wt[5]) << 6) // stucki_div
                coeff6: int = (int(stucki_wt[6]) << 6) // stucki_div
                kernel_len: int = 7

            elif kernel_type == 3:
                # Burkes
                dx0 = int(burkes_dx[0])
                dy0 = int(burkes_dy[0])
                dx1 = int(burkes_dx[1])
                dy1 = int(burkes_dy[1])
                dx2 = int(burkes_dx[2])
                dy2 = int(burkes_dy[2])
                dx3 = int(burkes_dx[3])
                dy3 = int(burkes_dy[3])
                dx4 = int(burkes_dx[4])
                dy4 = int(burkes_dy[4])
                dx5 = int(burkes_dx[5])
                dy5 = int(burkes_dy[5])
                dx6 = int(burkes_dx[6])
                dy6 = int(burkes_dy[6])
                coeff0: int = (int(burkes_wt[0]) << 6) // burkes_div
                coeff1: int = (int(burkes_wt[1]) << 6) // burkes_div
                coeff2: int = (int(burkes_wt[2]) << 6) // burkes_div
                coeff3: int = (int(burkes_wt[3]) << 6) // burkes_div
                coeff4: int = (int(burkes_wt[4]) << 6) // burkes_div
                coeff5: int = (int(burkes_wt[5]) << 6) // burkes_div
                coeff6: int = (int(burkes_wt[6]) << 6) // burkes_div
                kernel_len: int = 7

            else:
                # Floyd–Steinberg
                dx0 = int(fs_dx[0])
                dy0 = int(fs_dy[0])
                dx1 = int(fs_dx[1])
                dy1 = int(fs_dy[1])
                dx2 = int(fs_dx[2])
                dy2 = int(fs_dy[2])
                dx3 = int(fs_dx[3])
                dy3 = int(fs_dy[3])
                coeff0: int = (int(fs_wt[0]) << 6) // fs_div
                coeff1: int = (int(fs_wt[1]) << 6) // fs_div
                coeff2: int = (int(fs_wt[2]) << 6) // fs_div
                coeff3: int = (int(fs_wt[3]) << 6) // fs_div
                kernel_len: int = 4

        else:
            # Dummy pointers to satisfy types, not used
            error_current_ptr = ptr8(bytearray(0))
            error_next_ptr = ptr8(bytearray(0))

        # Dithering error diffusion helper — defined once, called per-pixel when dithering
        @micropython.viper
        def _accum(
            error_current_ptr: ptr8,
            error_next_ptr: ptr8,
            nx: int,
            ny: int,
            row: int,
            draw_width: int,
            draw_height: int,
            dyv: int,
            k: int,
            cr: int,
            cg: int,
            cb: int,
        ):
            if nx < 0 or nx >= draw_width or ny < 0 or ny >= draw_height:
                return
            target: ptr8 = error_next_ptr if dyv else error_current_ptr
            tpos: int = nx * 3
            tr: int = target[tpos]
            if tr > 127:
                tr -= 256
            tg: int = target[tpos + 1]
            if tg > 127:
                tg -= 256
            tb: int = target[tpos + 2]
            if tb > 127:
                tb -= 256
            tr += (cr * k) >> 6
            tg += (cg * k) >> 6
            tb += (cb * k) >> 6
            if tr < -128:
                tr = -128
            elif tr > 127:
                tr = 127
            if tg < -128:
                tg = -128
            elif tg > 127:
                tg = 127
            if tb < -128:
                tb = -128
            elif tb > 127:
                tb = 127
            target[tpos] = tr + 256 if tr < 0 else tr
            target[tpos + 1] = tg + 256 if tg < 0 else tg
            target[tpos + 2] = tb + 256 if tb < 0 else tb

        # Pre-compute the starting phys_y for col=0 (constant across all rows)
        base_phys_y: int = _screen_width - 1 - x0

        row: int = 0
        while row < draw_height:
            img_row_start: int = row * width * 2

            # Rotation 1: phys_x = y0 + row (constant for entire row)
            phys_x: int = y0 + row
            phys_x_half: int = phys_x >> 1
            nibble_odd: int = phys_x & 1

            # fb_idx for col=0; decrements by _bytes_per_row per col
            fb_idx: int = base_phys_y * _bytes_per_row + phys_x_half

            col: int = 0
            while col < draw_width:
                idx: int = img_row_start + (col * 2)
                pixel: int = imagedata[idx] | (imagedata[idx + 1] << 8)

                # RGB565 -> RGB888 (bit expand)
                r_: int = (pixel >> 8) & 0xF8
                g_: int = (pixel >> 3) & 0xFC
                b_: int = (pixel << 3) & 0xF8
                r_ |= r_ >> 5
                g_ |= g_ >> 6
                b_ |= b_ >> 5

                if dither:
                    epos: int = col * 3
                    er: int = error_current_ptr[epos]
                    if er > 127:
                        er -= 256
                    eg: int = error_current_ptr[epos + 1]
                    if eg > 127:
                        eg -= 256
                    eb: int = error_current_ptr[epos + 2]
                    if eb > 127:
                        eb -= 256

                    r_ += er
                    g_ += eg
                    b_ += eb
                    if r_ < 0:
                        r_ = 0
                    elif r_ > 255:
                        r_ = 255
                    if g_ < 0:
                        g_ = 0
                    elif g_ > 255:
                        g_ = 255
                    if b_ < 0:
                        b_ = 0
                    elif b_ > 255:
                        b_ = 255

                # Unrolled nearest-color search over 6 Spectra palette entries
                best_idx: int = 0
                dr: int = r_ - 0
                dg: int = g_ - 0
                db: int = b_ - 0
                best_dist: int = dr * dr + dg * dg + db * db

                dr = r_ - 255
                dg = g_ - 255
                db = b_ - 255
                dist: int = dr * dr + dg * dg + db * db
                if dist < best_dist:
                    best_dist = dist
                    best_idx = 1

                dr = r_ - 255
                dg = g_ - 255
                db = b_ - 0
                dist = dr * dr + dg * dg + db * db
                if dist < best_dist:
                    best_dist = dist
                    best_idx = 2

                dr = r_ - 255
                dg = g_ - 0
                db = b_ - 0
                dist = dr * dr + dg * dg + db * db
                if dist < best_dist:
                    best_dist = dist
                    best_idx = 3

                dr = r_ - 0
                dg = g_ - 0
                db = b_ - 255
                dist = dr * dr + dg * dg + db * db
                if dist < best_dist:
                    best_dist = dist
                    best_idx = 5

                dr = r_ - 0
                dg = g_ - 255
                db = b_ - 0
                dist = dr * dr + dg * dg + db * db
                if dist < best_dist:
                    best_dist = dist
                    best_idx = 6

                val: int = best_idx ^ inv_mask

                # Write to framebuffer using pre-computed index and nibble position
                fb_val: int = framebuf[fb_idx]
                if nibble_odd:
                    framebuf[fb_idx] = (fb_val & 0xF0) | val
                else:
                    framebuf[fb_idx] = (fb_val & 0x0F) | (val << 4)

                if dither:
                    if best_idx == 0:
                        pr = 0
                        pg = 0
                        pb = 0
                    elif best_idx == 1:
                        pr = 255
                        pg = 255
                        pb = 255
                    elif best_idx == 2:
                        pr = 255
                        pg = 255
                        pb = 0
                    elif best_idx == 3:
                        pr = 255
                        pg = 0
                        pb = 0
                    elif best_idx == 5:
                        pr = 0
                        pg = 0
                        pb = 255
                    else:
                        pr = 0
                        pg = 255
                        pb = 0

                    drq: int = r_ - pr
                    dgq: int = g_ - pg
                    dbq: int = b_ - pb

                    nx0: int = col + dx0
                    dy0: int = dy0
                    _accum(
                        error_current_ptr,
                        error_next_ptr,
                        nx0,
                        row + dy0,
                        row,
                        draw_width,
                        draw_height,
                        dy0,
                        coeff0,
                        drq,
                        dgq,
                        dbq,
                    )

                    nx1: int = col + dx1
                    dy1: int = dy1
                    _accum(
                        error_current_ptr,
                        error_next_ptr,
                        nx1,
                        row + dy1,
                        row,
                        draw_width,
                        draw_height,
                        dy1,
                        coeff1,
                        drq,
                        dgq,
                        dbq,
                    )

                    nx2: int = col + dx2
                    dy2: int = dy2
                    _accum(
                        error_current_ptr,
                        error_next_ptr,
                        nx2,
                        row + dy2,
                        row,
                        draw_width,
                        draw_height,
                        dy2,
                        coeff2,
                        drq,
                        dgq,
                        dbq,
                    )

                    nx3: int = col + dx3
                    dy3: int = dy3
                    _accum(
                        error_current_ptr,
                        error_next_ptr,
                        nx3,
                        row + dy3,
                        row,
                        draw_width,
                        draw_height,
                        dy3,
                        coeff3,
                        drq,
                        dgq,
                        dbq,
                    )

                    if kernel_len == 7:
                        nx4: int = col + dx4
                        dy4: int = dy4
                        _accum(
                            error_current_ptr,
                            error_next_ptr,
                            nx4,
                            row + dy4,
                            row,
                            draw_width,
                            draw_height,
                            dy4,
                            coeff4,
                            drq,
                            dgq,
                            dbq,
                        )

                        nx5: int = col + dx5
                        dy5: int = dy5
                        _accum(
                            error_current_ptr,
                            error_next_ptr,
                            nx5,
                            row + dy5,
                            row,
                            draw_width,
                            draw_height,
                            dy5,
                            coeff5,
                            drq,
                            dgq,
                            dbq,
                        )

                        nx6: int = col + dx6
                        dy6: int = dy6
                        _accum(
                            error_current_ptr,
                            error_next_ptr,
                            nx6,
                            row + dy6,
                            row,
                            draw_width,
                            draw_height,
                            dy6,
                            coeff6,
                            drq,
                            dgq,
                            dbq,
                        )

                # Advance to next col: phys_y decreases by 1, so fb_idx drops by one row
                fb_idx -= _bytes_per_row
                col += 1

            if dither:
                tmp = error_current_ptr
                error_current_ptr = error_next_ptr
                error_next_ptr = tmp
                i2: int = 0
                while i2 < errbuf_size:
                    error_next_ptr[i2] = 0
                    i2 += 1

            row += 1

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        with open(path, "rb") as f:
            png_data = f.read()

        width, height, png_data = Inkplate.png_to_rgb565(png_data, len(png_data))

        Inkplate.write_image(
            self._framebuf, x0, y0, width, height, png_data, invert, dither, kernel_type
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

            width, height, png_data = Inkplate.png_to_rgb565(png_data, len(png_data))

            Inkplate.write_image(
                self._framebuf,
                x0,
                y0,
                width,
                height,
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
            except Exception as e:
                print(e)
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]

            # 4. Decode image
            decoded = decoder.decode(jpeg_data)

            Inkplate.write_image(
                self._framebuf,
                x0,
                y0,
                width,
                height,
                decoded,
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

    _PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    @staticmethod
    @micropython.viper
    def png_to_rgb565(png_data: ptr8, png_len: int):
        import deflate
        import io
        import array
        from uctypes import addressof, bytearray_at

        # --- Signature check ---
        if (
            png_data[0] != 0x89
            or png_data[1] != 0x50
            or png_data[2] != 0x4E
            or png_data[3] != 0x47
            or png_data[4] != 0x0D
            or png_data[5] != 0x0A
            or png_data[6] != 0x1A
            or png_data[7] != 0x0A
        ):
            raise ValueError("Invalid PNG signature")

        # --- Parse chunks (your original logic) ---
        pos: int = 8
        width: int = 0
        height: int = 0
        color_type: int = 0
        idat_data = bytearray()

        while pos + 8 <= png_len:
            chunk_len: int = (
                (png_data[pos] << 24)
                | (png_data[pos + 1] << 16)
                | (png_data[pos + 2] << 8)
                | png_data[pos + 3]
            )

            is_ihdr = (
                png_data[pos + 4] == 0x49
                and png_data[pos + 5] == 0x48
                and png_data[pos + 6] == 0x44
                and png_data[pos + 7] == 0x52
            )

            is_idat = (
                png_data[pos + 4] == 0x49
                and png_data[pos + 5] == 0x44
                and png_data[pos + 6] == 0x41
                and png_data[pos + 7] == 0x54
            )

            is_iend = (
                png_data[pos + 4] == 0x49
                and png_data[pos + 5] == 0x45
                and png_data[pos + 6] == 0x4E
                and png_data[pos + 7] == 0x44
            )

            chunk_start: int = pos + 8

            if is_ihdr:
                width = (
                    (png_data[chunk_start] << 24)
                    | (png_data[chunk_start + 1] << 16)
                    | (png_data[chunk_start + 2] << 8)
                    | png_data[chunk_start + 3]
                )
                height = (
                    (png_data[chunk_start + 4] << 24)
                    | (png_data[chunk_start + 5] << 16)
                    | (png_data[chunk_start + 6] << 8)
                    | png_data[chunk_start + 7]
                )
                color_type = png_data[chunk_start + 9]
                if color_type != 2 and color_type != 6:
                    raise ValueError("Unsupported PNG color type")

            elif is_idat:
                # Original safe byte-by-byte copy
                idat_chunk = bytearray(chunk_len)
                i: int = 0
                while i < chunk_len:
                    idat_chunk[i] = png_data[chunk_start + i]
                    i += 1
                idat_data += idat_chunk

            elif is_iend:
                break

            pos += chunk_len + 12

        if width == 0 or height == 0:
            raise ValueError("PNG missing IHDR chunk")
        if not idat_data:
            raise ValueError("PNG missing IDAT chunk")

        # --- Setup decoding ---
        bpp: int = 3 if color_type == 2 else 4
        row_size: int = width * bpp
        stride: int = row_size + 1

        rgb565_data = array.array("H", bytearray(width * height * 2))
        rgb565_ptr = ptr16(addressof(rgb565_data))

        idat_mv = bytearray_at(addressof(idat_data), len(idat_data))
        dstream = deflate.DeflateIO(io.BytesIO(idat_mv))

        cur_buf = bytearray(row_size)
        prev_buf = bytearray(row_size)
        cur = ptr8(addressof(cur_buf))
        prev = ptr8(addressof(prev_buf))

        # zero previous row
        i: int = 0
        while i < row_size:
            prev[i] = 0
            i += 1

        # --- Main loop ---
        y: int = 0
        while y < height:
            raw = dstream.read(stride)
            if not raw or int(len(raw)) != stride:
                raise ValueError("Invalid PNG row data")

            raw_ptr = ptr8(addressof(raw))
            filt: int = raw_ptr[0]
            rp = ptr8(int(raw_ptr) + 1)

            # --- Filtering ---
            x: int = 0
            while x < row_size:
                v: int = rp[x]
                if filt == 1:  # Sub
                    if x >= bpp:
                        v = (v + cur[x - bpp]) & 0xFF
                elif filt == 2:  # Up
                    v = (v + prev[x]) & 0xFF
                elif filt == 3:  # Average
                    a = cur[x - bpp] if x >= bpp else 0
                    b = prev[x]
                    v = (v + ((a + b) >> 1)) & 0xFF
                elif filt == 4:  # Paeth
                    a = cur[x - bpp] if x >= bpp else 0
                    b = prev[x]
                    c = prev[x - bpp] if x >= bpp else 0
                    p = a + b - c
                    pa = p - a if p >= a else a - p
                    pb = p - b if p >= b else b - p
                    pc = p - c if p >= c else c - p
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    v = (v + pred) & 0xFF
                cur[x] = v
                x += 1

            # --- Convert to RGB565 ---
            row_off: int = y * width
            if bpp == 3:  # RGB
                x = 0
                while x < width:
                    i = x * 3
                    r = cur[i]
                    g = cur[i + 1]
                    b = cur[i + 2]
                    rgb565_ptr[row_off + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    x += 1
            else:  # RGBA
                x = 0
                while x < width:
                    i = x * 4
                    r = cur[i]
                    g = cur[i + 1]
                    b = cur[i + 2]
                    a = cur[i + 3]
                    if a < 255:
                        r = (r * a) // 255
                        g = (g * a) // 255
                        b = (b * a) // 255
                    rgb565_ptr[row_off + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    x += 1

            # swap buffers
            tmp = cur
            cur = prev
            prev = tmp

            y += 1

        return (width, height, rgb565_data)

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        gc.collect()
        with open(path, "rb") as f:
            bmp_data = f.read()

        width, height, bmp_data = Inkplate.bmp24_to_rgb565(bmp_data, len(bmp_data))

        Inkplate.write_image(
            self._framebuf, x0, y0, width, height, bmp_data, invert, dither, kernel_type
        )
        del bmp_data
        gc.collect()

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
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
            width, height, bmp_data = Inkplate.bmp24_to_rgb565(bmp_data, len(bmp_data))

            Inkplate.write_image(
                self._framebuf,
                x0,
                y0,
                width,
                height,
                bmp_data,
                invert,
                dither,
                kernel_type,
            )
            del bmp_data
            gc.collect()
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()

    @staticmethod
    @micropython.viper
    def bmp24_to_rgb565(bmp_data: ptr8, bmp_len: int):
        # keep imports inside the function per your environment
        from uctypes import addressof

        @micropython.viper
        def le32_and_sign(data: ptr8, off: int):
            b0: int = data[off]
            b1: int = data[off + 1]
            b2: int = data[off + 2]
            b3: int = data[off + 3]
            uval: int = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
            top_down: int = 0
            if b3 & 0x80:  # negative
                top_down = 1
                # absolute value: two’s complement, but we can do (0 - uval)
                uval = -uval
            return uval, top_down

        # --- File header checks (14 bytes) ---
        # 'BM'
        if bmp_len < 54 or bmp_data[0] != 0x42 or bmp_data[1] != 0x4D:
            raise ValueError("Invalid BMP signature")

        # Little-endian helpers (inline)
        # le32 at offset 'o'
        o: int = 10
        pixel_ofs: int = (
            bmp_data[o] | (bmp_data[o + 1] << 8) | (bmp_data[o + 2] << 16) | (bmp_data[o + 3] << 24)
        )

        # --- DIB header (assume BITMAPINFOHEADER >= 40 bytes) ---
        dib_sz: int = (
            bmp_data[14] | (bmp_data[15] << 8) | (bmp_data[16] << 16) | (bmp_data[17] << 24)
        )
        if dib_sz < 40:
            raise ValueError("Unsupported DIB header")

        # width (int32 le)
        w_off: int = 18
        width: int = (
            bmp_data[w_off]
            | (bmp_data[w_off + 1] << 8)
            | (bmp_data[w_off + 2] << 16)
            | (bmp_data[w_off + 3] << 24)
        )
        if width <= 0:
            raise ValueError("Unsupported BMP width")

        # height (int32 le, may be negative for top-down)
        h_off: int = 22
        b0: int = bmp_data[h_off]
        b1: int = bmp_data[h_off + 1]
        b2: int = bmp_data[h_off + 2]
        b3: int = bmp_data[h_off + 3]
        height_le: int = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

        top_down: int = 0
        if b3 & 0x80:  # check sign bit
            top_down = 1
            abs_height: int = -height_le  # safe negation, no big mask
        else:
            abs_height = height_le

        if abs_height <= 0:
            raise ValueError("Unsupported BMP height")

        # planes (must be 1)
        planes: int = bmp_data[26] | (bmp_data[27] << 8)
        if planes != 1:
            raise ValueError("Invalid planes")

        # bpp (must be 24)
        bpp: int = bmp_data[28] | (bmp_data[29] << 8)
        if bpp != 24:
            raise ValueError("Only 24-bit BMP supported")

        # compression (must be BI_RGB = 0)
        comp: int = bmp_data[30] | (bmp_data[31] << 8) | (bmp_data[32] << 16) | (bmp_data[33] << 24)
        if comp != 0:
            raise ValueError("Compressed BMP not supported")

        # row stride with 4-byte padding: ((width*3 + 3) & ~3)
        bytes_per_row: int = width * 3
        stride: int = (bytes_per_row + 3) // 4 * 4

        # bounds check: pixel data must fit in file
        total_data: int = stride * abs_height
        if pixel_ofs + total_data > bmp_len:
            raise ValueError("BMP pixel data truncated")

        # --- Prepare output ---
        out_sz: int = width * abs_height * 2
        outbuf = bytearray(out_sz)
        outp: ptr16 = ptr16(addressof(outbuf))

        # constants for RGB565 pack
        rmask: int = 0xF8
        gmask: int = 0xFC

        # --- Iterate rows/pixels ---
        y: int = 0
        while y < abs_height:
            # source row selection (BMP is bottom-up unless top_down)
            src_y: int = y if top_down == 1 else (abs_height - 1 - y)
            src_base: int = pixel_ofs + src_y * stride

            x: int = 0
            while x < width:
                px_off: int = src_base + x * 3
                # BGR order in BMP
                b: int = bmp_data[px_off]
                g: int = bmp_data[px_off + 1]
                r: int = bmp_data[px_off + 2]

                # pack to RGB565
                rgb565: int = ((r & rmask) << 8) | ((g & gmask) << 3) | (b >> 3)

                out_index: int = y * width + x
                outp[out_index] = rgb565

                x += 1
            y += 1

        return (width, abs_height, outbuf)


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
