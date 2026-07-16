"""MicroPython driver for the Inkplate 13 SPECTRA e-paper display.

Ported from the Arduino Inkplate13Driver implementation.
"""

import time
import os
from machine import ADC, I2C, SDCard, Pin
from micropython import const
from pcal6416a import *
from gfx import GFX
import machine
import inkplate

machine.freq(240000000)

# RST/DC/CS_M/CS_S/BUSY/CLK/DIN, PWR_EN, BS0/BS1 and the SPI peripheral itself are owned
# by the C dual-chip spi transport (firmware/usermods/inkplate/epd_spi.c's epd_spi_dual_*
# functions, docs/REFACTOR-PLAN.md Phase 9 step 31) -- no Python-side pin constants
# needed for the panel.

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

# RGB565 scratch buffer for inkplate.jpeg_draw_palette/png_draw_palette's dithering
# pass -- see boards/inkplate6color/inkplate6_color.py's identical constants for
# the full reasoning (docs/REFACTOR-PLAN.md Phase 10 step 32's followup).
_DITHER_SCRATCH_W = max(D_COLS, 1200)
_DITHER_SCRATCH_H = max(D_ROWS, 825)
_DITHER_SCRATCH_BYTES = _DITHER_SCRATCH_W * _DITHER_SCRATCH_H * 2

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

        # RST/DC/CS_M/CS_S/BUSY/CLK/DIN/PWR_EN/BS0/BS1 + the SPI peripheral itself are
        # owned by the C dual-chip spi transport from here on
        # (firmware/usermods/inkplate/epd_spi.c, docs/REFACTOR-PLAN.md Phase 9 step 31)
        # -- no more machine.SPI/Pin objects for the panel itself.
        inkplate.select_spi_panel("inkplate13spectra")

        # Discharge panel capacitors first, matching the real Arduino reference driver's
        # initDriver() -- setIO() (which brings up the SPI bus itself) only runs later,
        # on the first set_panel_state(True).
        cls.set_panel_pins_to_low()

        cls.VBAT = ADC(Pin(1))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)
        cls.VBAT_EN = GpioPin(cls._PCAL6416A, 9, mode_output)
        cls.VBAT_EN.digital_write(0)

        cls.cursor = [0, 0]
        cls.textColor = 0
        cls.textWrapping = 1

        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, 10, mode_output)

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
        inkplate.spi_dual_pins_low()

    @classmethod
    def set_io(cls):
        """Configure GPIOs and SPI for panel communication."""
        inkplate.spi_dual_power_up_io()

    @classmethod
    def reset_panel(cls):
        """Hardware reset of the panel.

        Reuses the single-chip family's epd_spi_reset() (100ms low / 200ms recovery)
        rather than a dual-chip-specific 100ms/100ms pulse -- the real Arduino reference
        driver's own resetPanel() only asks for 100ms/100ms, and a longer recovery delay
        can't hurt, same reasoning already applied to Inkplate2's reset pulse width
        (docs/REFACTOR-PLAN.md Phase 9 step 31).
        """
        inkplate.spi_panel_reset()

    @classmethod
    def wait_for_busy(cls):
        """Wait until the panel signals ready (BUSY pin goes high)."""
        inkplate.spi_panel_wait_busy(1, 0)

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

            # Configure GPIOs (also (re)inits the SPI bus/device, matching the real
            # Arduino reference driver's setIO(), which reconstructs its SPI object here
            # too -- see epd_spi_dual_power_up_io()'s own comment)
            cls.set_io()

            # Enable power
            inkplate.spi_dual_set_power(1)
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

            # Float DC/CS_M/CS_S/RST/BUSY/PWR_EN to save power (BS0/BS1 deliberately left
            # alone, matching the real Arduino reference driver -- see
            # epd_spi_dual_power_down_io()'s own comment).
            inkplate.spi_dual_power_down_io()

        cls._panel_state = state

    @classmethod
    def send_command(cls, cmd, data=None, chip_id=CHIP_BOTH):
        """Send a command (and optional data) to master, slave, or both chips."""
        inkplate.spi_dual_select(chip_id)
        inkplate.spi_dual_write(bytes([cmd]))
        if data is not None:
            inkplate.spi_dual_write(data)
        inkplate.spi_dual_deselect(chip_id)

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
        inkplate.spi_dual_select(CHIP_MASTER)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2)
            inkplate.spi_dual_write(mv[row_start : row_start + half_row])
        inkplate.spi_dual_deselect(CHIP_MASTER)

        # Send data to slave chip (right side of screen)
        cls.wait_for_busy()
        inkplate.spi_dual_select(CHIP_SLAVE)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2) + half_row
            inkplate.spi_dual_write(mv[row_start : row_start + half_row])
        inkplate.spi_dual_deselect(CHIP_SLAVE)

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
        inkplate.spi_dual_select(CHIP_MASTER)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            inkplate.spi_dual_write(white_half)
        inkplate.spi_dual_deselect(CHIP_MASTER)

        # Send white data to slave chip (right side)
        cls.wait_for_busy()
        inkplate.spi_dual_select(CHIP_SLAVE)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            inkplate.spi_dual_write(white_half)
        inkplate.spi_dual_deselect(CHIP_SLAVE)

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

    def draw_jpg_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        with open(path, "rb") as f:
            jpg_data = f.read()
        inkplate.jpeg_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, jpg_data
        )
        gc.collect()

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        with open(path, "rb") as f:
            png_data = f.read()
        scratch = bytearray(_DITHER_SCRATCH_BYTES) if dither else None
        inkplate.png_draw_palette(
            self._framebuf,
            None,
            self.rotation,
            x0,
            y0,
            invert,
            dither,
            kernel_type,
            png_data,
            scratch,
        )
        del scratch
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

            scratch = bytearray(_DITHER_SCRATCH_BYTES) if dither else None
            inkplate.png_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                png_data,
                scratch,
            )
            del scratch
            gc.collect()
        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()

    def draw_jpg_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=20)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            jpg_data = response.content
            response.close()

            inkplate.jpeg_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                jpg_data,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_jpg_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        gc.collect()
        with open(path, "rb") as f:
            bmp_data = f.read()

        inkplate.bmp_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, bmp_data
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

            inkplate.bmp_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                bmp_data,
            )
            del bmp_data
            gc.collect()
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
