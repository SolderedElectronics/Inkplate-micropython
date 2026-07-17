"""MicroPython driver for the Inkplate 6COLOR e-paper display."""

import time
import os
from machine import ADC, I2C, Pin, SDCard
from micropython import const
from pcal6416a import *
from rtc import RTC
from inkplate_image_palette_mixin import ImagePaletteMixin
import gfx_standard_font_01 as montserrat_black
import machine
import inkplate

machine.freq(240000000)
# ===== Constants that change between the Inkplate 6 and 10

# RST/DC/CS/BUSY/CLK/DIN pins are owned by the C spi_panel transport
# (firmware/usermods/inkplate/spi_panel_config.c); no Python-side pin constants needed.
VBAT_PIN = const(35)

# Timeout for init of epaper (1.5 sec in this case).

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


# Class-level attributes (rotation, _panel_state, _framebuf, etc.) assume a single
# Inkplate() instance is ever created.
# draw_bmp/png/jpg_from_sd/_from_web and draw_color_image come from
# shared/mixins/inkplate_image_palette_mixin.py.
class Inkplate(ImagePaletteMixin):
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
    # gfx_* calls use a rotation numbering offset by 2 from this board's own `rotation`
    # (board rotation 0 is physically what gfx.c's rotation-remap calls rotation 2) --
    # see set_rotation(). Kept separate from `rotation` itself since the SPI palette
    # image-decode path (draw_bmp_from_web etc.) still expects this board's native
    # rotation numbering unchanged.
    _gfx_rotation = 2
    text_size = 1

    _panel_state = False

    _framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    def begin(self):
        self.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        self._PCAL6416A = PCAL6416A(self.wire)
        self._rtc = RTC(self.wire)

        # RST/DC/CS/BUSY/CLK/DIN and the SPI peripheral itself are owned by the C
        # spi_panel transport (firmware/usermods/inkplate/epd_spi.c); no more
        # machine.SPI/Pin objects for the panel itself.
        inkplate.select_spi_panel("inkplate6color")
        inkplate.spi_panel_init()

        # This panel's 4bpp framebuffer packs even physical x into the high nibble,
        # the opposite of gfx_set_pixel's default; the swap is a session-constant
        # flag, set once here.
        inkplate.gfx_set_gs4_nibble_swap(True)

        self.VBAT = ADC(Pin(35))
        self.VBAT.atten(ADC.ATTN_11DB)
        self.VBAT.width(ADC.WIDTH_12BIT)
        self.VBAT_EN = GpioPin(self._PCAL6416A, 9, mode_output)
        self.VBAT_EN.digital_write(0)

        # Internal-expander pin 10 (IO_PIN_B2) drives an active-low P-MOS gate for
        # SD card power.
        self.SD_ENABLE = GpioPin(self._PCAL6416A, IO_PIN_B2, mode_output)

        self.cursor = [0, 0]

        self.textColor = 0

        self.textWrapping = 1

        self.framebuf = bytearray(D_ROWS * D_COLS // 2)

        self.font_family = montserrat_black
        self.font = self.font_family._font

        self.reset_panel()

        if not inkplate.spi_panel_wait_busy(1, 10000):
            return False

        self.send_command(PANEL_SET_REGISTER)
        self.send_data(b"\xef\x08")
        self.send_command(POWER_SET_REGISTER)
        self.send_data(b"\x37\x00\x23\x23")
        self.send_command(POWER_OFF_SEQ_SET_REGISTER)
        self.send_data(b"\x00")
        self.send_command(BOOSTER_SOFTSTART_REGISTER)
        self.send_data(b"\xc7\xc7\x1d")
        self.send_command(PLL_CONTROL_REGISTER)
        self.send_data(b"\x3c")
        self.send_command(TEMP_SENSOR_REGISTER)
        self.send_data(b"\x00")
        self.send_command(VCOM_DATA_INTERVAL_REGISTER)
        self.send_data(b"\x37")
        self.send_command(0x60)
        self.send_data(b"\x20")
        self.send_command(RESOLUTION_SET_REGISTER)
        self.send_data(b"\x02\x58\x01\xc0")
        self.send_command(0xE3)
        self.send_data(b"\xaa")

        time.sleep_ms(100)

        self.send_command(0x50)
        self.send_data(b"\x37")

        self.set_pcal_for_low_power()

        self._panel_state = True

        return True

    def init_sd_card(self, fast_boot=False):
        # SD's machine.SDCard(slot=3) runs on HSPI/SPI2_HOST; the panel (epd_spi.c) runs
        # on VSPI/SPI3_HOST. Two separate ESP32 SPI peripherals, so no claim/release
        # dance is needed here.
        self.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15),
                    # 4MHz avoids hangs/mount failures seen at higher speeds with this
                    # SPI-mode SD driver.
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

    def set_pcal_for_low_power(self):
        for x in range(16):
            self._PCAL6416A.pin_mode(int(x), mode_output)
            self._PCAL6416A.digital_write(int(x), 0)

    def get_panel_deep_sleep_state(self):
        return self._panel_state

    def set_panel_deep_sleep(self, state: bool) -> bool:
        if not state:
            # Wake the panel from deep sleep. Pin config/CS+DC idle levels are owned by
            # the C spi_panel transport (epd_spi_init(), already called from begin()) --
            # only the reset+reinit sequence needs repeating here.
            time.sleep_ms(100)

            self.reset_panel()

            if not inkplate.spi_panel_wait_busy(1, 1500):
                return False

            self.send_command(PANEL_SET_REGISTER)
            self.send_data(bytearray([0xEF, 0x08]))

            self.send_command(POWER_SET_REGISTER)
            self.send_data(bytearray([0x37, 0x00, 0x05, 0x05]))

            self.send_command(POWER_OFF_SEQ_SET_REGISTER)
            self.send_data(bytearray([0x00]))

            self.send_command(BOOSTER_SOFTSTART_REGISTER)
            self.send_data(bytearray([0xC7, 0xC7, 0x1D]))

            self.send_command(TEMP_SENSOR_EN_REGISTER)
            self.send_data(bytearray([0x00]))

            self.send_command(VCOM_DATA_INTERVAL_REGISTER)
            self.send_data(bytearray([0x37]))

            self.send_command(0x60)
            self.send_data(bytearray([0x20]))

            self.send_command(RESOLUTION_SET_REGISTER)
            self.send_data(bytearray([0x02, 0x58, 0x01, 0xC0]))

            self.send_command(0xE3)
            self.send_data(bytearray([0xAA]))

            time.sleep_ms(100)
            self.send_command(VCOM_DATA_INTERVAL_REGISTER)
            self.send_data(bytearray([0x37]))

            return True
        else:
            time.sleep_ms(10)
            self.send_command(DEEP_SLEEP_REGISTER)
            self.send_data(bytearray([0xA5]))
            time.sleep_ms(100)

            # Hold RST asserted low while asleep; lower power than leaving it floating
            # or driven high.
            inkplate.spi_panel_set_rst(0)

            return True

    def reset_panel(self):
        inkplate.spi_panel_reset()

    def send_command(self, command):
        inkplate.spi_panel_send_command(command)

    def send_data(self, data):
        inkplate.spi_panel_send_data(data)

    def clear_display(self):
        self._framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    @micropython.native
    def display(self):
        self.set_panel_deep_sleep(False)

        self.send_command(0x61)
        self.send_data(b"\x02\x58\x01\xc0")

        self.send_command(0x10)
        self.send_data(self._framebuf)

        self.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        self.send_command(DISPLAY_REF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        self.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(0, 0)

        time.sleep_ms(200)

        self.set_panel_deep_sleep(True)

    def gpio_expander_pin(self, pin, mode):
        return GpioPin(self._PCAL6416A, pin, mode)

    # PCF85263-style RTC chip.
    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        self._rtc.set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        self._rtc.set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_rtc_data(self):
        return self._rtc.get_data()

    def clean(self):
        if not self._panel_state:
            return

        self.send_command(0x61)
        self.send_data(b"\x02\x58\x01\xc0")

        self.send_command(0x10)
        self.send_data(bytearray(0x11 for x in range(D_COLS * D_ROWS // 2)))

        self.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        self.send_command(DISPLAY_REF_REGISTER)
        inkplate.spi_panel_wait_busy(1, 0)

        self.send_command(POWER_OFF_REGISTER)
        inkplate.spi_panel_wait_busy(0, 0)

        time.sleep_ms(200)

    def width(self):
        return self._width

    def height(self):
        return self._height

    def set_rotation(self, x):
        self.rotation = x % 4
        self._gfx_rotation = (self.rotation + 2) % 4
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
        inkplate.gfx_set_pixel(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, c)

    def write_fill_rect(self, x, y, w, h, c):
        inkplate.gfx_fill_rect(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, h, c)

    def write_fast_vline(self, x, y, h, c):
        inkplate.gfx_vline(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, h, c)

    def write_fast_hline(self, x, y, w, c):
        inkplate.gfx_hline(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, c)

    def set_text_color(self, c):
        self.textColor = c

    def write_line(self, x0, y0, x1, y1, c):
        inkplate.gfx_line(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x0, y0, x1, y1, c)

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
        inkplate.gfx_rect(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, h, c)

    def draw_circle(self, x, y, r, c):
        inkplate.gfx_circle(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, r, c)

    def fill_circle(self, x, y, r, c):
        inkplate.gfx_fill_circle(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, r, c)

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_triangle(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_fill_triangle(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    def draw_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_round_rect(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, q, h, r, c
        )

    def fill_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_fill_round_rect(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, q, h, r, c
        )

    def set_text_wrapping(self, state: bool):
        self.textWrapping = state

    def set_display_mode(self, mode):
        self.displayMode = mode

    def get_display_mode(self):
        return self.displayMode

    def set_text_size(self, s):
        self.text_size = s

    def set_font(self, f):
        self.font_family = f
        self.font = self.font_family._font

    def reset_cursor(self):
        self.cursor = [0, 0]

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    def _print_text(self, framebuf, x0, y0, string, size, color, text_wrap=False):
        display_width = self._width
        color = min(max(color, 0), 5)

        x = int(x0)
        y = int(y0)
        line_height = 0

        def blit(cx, cy, char_data, ch_w, ch_h):
            inkplate.gfx_draw_char(
                framebuf,
                D_COLS,
                D_ROWS,
                self._gfx_rotation,
                1,
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
            self._framebuf,
            x,
            y,
            s,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )

    def println(self, text):
        self.cursor, line_height = self._print_text(
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
        self.cursor, line_height = self._print_text(
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
        char_width = 6 * self.text_size  # Rough estimate
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
        # Probably unnecessary since MicroPython is slow, but delay anyway.
        time.sleep_ms(5)
        value = self.VBAT.read()
        self.VBAT_EN.digital_write(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    def draw_bitmap(self, x, y, data, w, h, c=BLACK):
        inkplate.gfx_draw_bitmap(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, data, w, h, c
        )

    def rtc_get_data(self):
        return self.rtc_get_rtc_data()


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
