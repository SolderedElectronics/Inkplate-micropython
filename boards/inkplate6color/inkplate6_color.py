"""MicroPython driver for the Inkplate 6COLOR e-paper display."""

import time
import os
from machine import ADC, I2C, Pin, SDCard
from micropython import const
from pcal6416a import *
from gfx import GFX
import machine
import inkplate

machine.freq(240000000)
# ===== Constants that change between the Inkplate 6 and 10

# RST/DC/CS/BUSY/CLK/DIN pins are owned by the C spi_panel transport now (see
# firmware/usermods/inkplate/spi_panel_config.c) -- no Python-side pin constants needed.
VBAT_PIN = const(35)

# Timeout for init of epaper(1.5 sec in this case)
# INIT_TIMEOUT 1500

pixel_mask_glut = [0xF, 0xF0]

# Epaper registers
PANEL_SET_REGISTER = 0x00
POWER_SET_REGISTER = 0x01
POWER_OFF_SEQ_SET_REGISTER = 0x03
POWER_OFF_REGISTER = 0x04
BOOSTER_SOFTSTART_REGISTER = 0x06
DEEP_SLEEP_REGISTER = 0x07
DATA_START_TRANS_REGISTER = 0x10
DATA_STOP_REGISTER = 0x11
DISPLAY_REF_REGISTER = 0x12
IMAGE_PROCESS_REGISTER = 0x13
PLL_CONTROL_REGISTER = 0x30
TEMP_SENSOR_REGISTER = 0x40
TEMP_SENSOR_EN_REGISTER = 0x41
TEMP_SENSOR_WR_REGISTER = 0x42
TEMP_SENSOR_RD_REGISTER = 0x43
VCOM_DATA_INTERVAL_REGISTER = 0x50
LOW_POWER_DETECT_REGISTER = 0x51
RESOLUTION_SET_REGISTER = 0x61
STATUS_REGISTER = 0x71
VCOM_VALUE_REGISTER = 0x81
VCM_DC_SET_REGISTER = 0x02

# Epaper resolution and colors
D_COLS = const(600)
D_ROWS = const(448)

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
    BLACK = const(0b00000000)  # 0
    WHITE = const(0b00000001)  # 1
    GREEN = const(0b00000010)  # 2
    BLUE = const(0b00000011)  # 3
    RED = const(0b00000100)  # 4
    YELLOW = const(0b00000101)  # 5
    ORANGE = const(0b00000110)  # 6

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    text_size = 1

    _panel_state = False

    _framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    @classmethod
    def begin(cls):
        cls.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        cls._PCAL6416A = PCAL6416A(cls.wire)

        # RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C
        # spi_panel transport from here on (firmware/usermods/inkplate/epd_spi.c,
        # docs/refactor_plan.md Phase 9 step 30) -- no more machine.SPI/Pin objects for
        # the panel itself.
        inkplate.select_spi_panel("inkplate6color")
        inkplate.spi_panel_init()

        cls.VBAT = ADC(Pin(35))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)
        cls.VBAT_EN = GpioPin(cls._PCAL6416A, 9, mode_output)
        cls.VBAT_EN.digital_write(0)

        # SD_PMOS_PIN (pins.h) -- internal-expander pin 10, active-low P-MOS gate, same
        # pin/polarity/expander-vs-external split every parallel-bus board already uses
        # for its own SD_ENABLE (e.g. boards/inkplate10/inkplate10.py).
        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, IO_PIN_B2, mode_output)

        cls.cursor = [0, 0]

        cls.textColor = 0

        cls.textWrapping = 1

        cls.framebuf = bytearray(D_ROWS * D_COLS // 2)

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
        cls.GFX.phys_row_bytes = D_COLS // 2
        cls.GFX.rotation = cls.rotation

        cls.reset_panel()

        if not inkplate.spi_panel_wait_busy(1, 10000):
            return False

        cls.send_command(PANEL_SET_REGISTER)
        cls.send_data(b"\xef\x08")
        cls.send_command(POWER_SET_REGISTER)
        cls.send_data(b"\x37\x00\x23\x23")
        cls.send_command(POWER_OFF_SEQ_SET_REGISTER)
        cls.send_data(b"\x00")
        cls.send_command(BOOSTER_SOFTSTART_REGISTER)
        cls.send_data(b"\xc7\xc7\x1d")
        cls.send_command(PLL_CONTROL_REGISTER)
        cls.send_data(b"\x3c")
        cls.send_command(TEMP_SENSOR_REGISTER)
        cls.send_data(b"\x00")
        cls.send_command(VCOM_DATA_INTERVAL_REGISTER)
        cls.send_data(b"\x37")
        cls.send_command(0x60)
        cls.send_data(b"\x20")
        cls.send_command(RESOLUTION_SET_REGISTER)
        cls.send_data(b"\x02\x58\x01\xc0")
        cls.send_command(0xE3)
        cls.send_data(b"\xaa")

        time.sleep_ms(100)

        cls.send_command(0x50)
        cls.send_data(b"\x37")

        cls.set_pcal_for_low_power()

        cls._panel_state = True

        return True

    def init_sd_card(self, fast_boot=False):
        # SD's machine.SDCard(slot=3) runs on HSPI/SPI2_HOST; the panel (epd_spi.c) runs
        # on VSPI/SPI3_HOST -- two genuinely separate ESP32 SPI peripherals, so no claim/
        # release dance is needed here (see epd_spi.c's EPD_SPI_HOST comment for how this
        # was confirmed against the real ports/esp32/machine_sdcard.c source, after an
        # earlier misreading of that same source wrongly concluded the two collided).
        self.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # 4MHz, same value every parallel-bus board settled on after hitting
                    # real hangs/mount failures at higher speeds on this same SPI-mode SD
                    # driver (docs/refactor_plan.md Phase 7 step 21/Phase 8 step 26) --
                    # not independently reverified on Inkplate6COLOR, but there's no
                    # reason to expect this board's SD wiring to behave differently.
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
    def get_panel_deep_sleep_state(cls):
        return cls._panel_state

    @classmethod
    def set_panel_deep_sleep(cls, state: bool) -> bool:
        if not state:
            # Wake the panel from deep sleep. Pin config/CS+DC idle levels are owned by
            # the C spi_panel transport (epd_spi_init(), already called from begin()) --
            # only the reset+reinit sequence needs repeating here.
            time.sleep_ms(100)

            cls.reset_panel()

            if not inkplate.spi_panel_wait_busy(1, 1500):
                return False

            # Send initialization commands
            cls.send_command(PANEL_SET_REGISTER)
            cls.send_data(bytearray([0xEF, 0x08]))

            cls.send_command(POWER_SET_REGISTER)
            cls.send_data(bytearray([0x37, 0x00, 0x05, 0x05]))

            cls.send_command(POWER_OFF_SEQ_SET_REGISTER)
            cls.send_data(bytearray([0x00]))

            cls.send_command(BOOSTER_SOFTSTART_REGISTER)
            cls.send_data(bytearray([0xC7, 0xC7, 0x1D]))

            cls.send_command(TEMP_SENSOR_EN_REGISTER)
            cls.send_data(bytearray([0x00]))

            cls.send_command(VCOM_DATA_INTERVAL_REGISTER)
            cls.send_data(bytearray([0x37]))

            cls.send_command(0x60)
            cls.send_data(bytearray([0x20]))

            cls.send_command(RESOLUTION_SET_REGISTER)
            cls.send_data(bytearray([0x02, 0x58, 0x01, 0xC0]))

            cls.send_command(0xE3)
            cls.send_data(bytearray([0xAA]))

            time.sleep_ms(100)
            cls.send_command(VCOM_DATA_INTERVAL_REGISTER)
            cls.send_data(bytearray([0x37]))

            return True
        else:
            # Put the panel to deep sleep
            time.sleep_ms(10)
            cls.send_command(DEEP_SLEEP_REGISTER)
            cls.send_data(bytearray([0xA5]))
            time.sleep_ms(100)

            # Hold RST asserted low while asleep (matches the real Arduino reference
            # driver's setPanelDeepSleep(true) -- lower power than leaving it floating
            # or driven high).
            inkplate.spi_panel_set_rst(0)

            return True

    @classmethod
    def reset_panel(cls):
        inkplate.spi_panel_reset()

    @classmethod
    def send_command(cls, command):
        inkplate.spi_panel_send_command(command)

    @classmethod
    def send_data(cls, data):
        inkplate.spi_panel_send_data(data)

    @classmethod
    def clear_display(cls):
        cls._framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    @classmethod
    @micropython.native
    def display(cls):
        cls.set_panel_deep_sleep(False)

        cls.send_command(0x61)
        cls.send_data(b"\x02\x58\x01\xc0")

        cls.send_command(0x10)
        cls.send_data(cls._framebuf)

        cls.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        cls.send_command(DISPLAY_REF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        cls.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(0, 0)

        time.sleep_ms(200)

        cls.set_panel_deep_sleep(True)

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
        if not cls._panel_state:
            return

        cls.send_command(0x61)
        cls.send_data(b"\x02\x58\x01\xc0")

        cls.send_command(0x10)
        cls.send_data(bytearray(0x11 for x in range(D_COLS * D_ROWS // 2)))

        cls.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        cls.send_command(DISPLAY_REF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        cls.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(0, 0)

        time.sleep_ms(200)

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

        r = cls.rotation
        if r == 0:
            x = w - x - 1
            y = h - y - 1
        elif r == 1:
            x, y = h - y - 1, x
        elif r == 3:
            x, y = y, w - x - 1
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

    @classmethod
    def read_battery(cls):
        cls.VBAT_EN.digital_write(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(5)
        value = cls.VBAT.read()
        cls.VBAT_EN.digital_write(0)
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
        # No scratch buffer passed: png_draw_palette only needs one for a rare
        # Adam7-interlaced source (dithers non-interlaced PNGs -- the common case --
        # inline, per pixel, no whole-image buffer at all). Pre-allocating one here
        # unconditionally used to reliably MemoryError on real Inkplate6COLOR
        # hardware for completely ordinary photos (docs/refactor_plan.md Phase 7
        # step 21's follow-up) -- worse than the rare case this was meant to serve.
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
            None,
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

            # See draw_png_from_sd's identical comment on why no scratch buffer.
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
                None,
            )
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
