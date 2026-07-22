"""MicroPython driver for the Inkplate 7SPECTRA e-paper display."""

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

# RST/DC/CS/BUSY/CLK/DIN and the SPI peripheral itself are owned by the C spi_panel
# transport (firmware/usermods/inkplate/display/epd_spi.c), same single-chip path as
# Inkplate6COLOR/Inkplate2. PWR_EN/BS0/BS1 are NOT modeled in spi_panel_config_t for this
# board (see spi_panel_config_inkplate7spectra's own comment in spi_panel_config.c) --
# reusing Inkplate13SPECTRA's dual-chip transport for them would also configure pin_cs2
# (0/GPIO0 for a chip_count == 1 board) as a bogus second chip-select. They're plain
# ESP32 GPIOs driven directly from here instead.
PWR_EN_PIN = const(21)
BS0_PIN = const(6)
BS1_PIN = const(5)

# microSD card SPI pins -- separate bus from the panel (HSPI/SPI2_HOST, slot=3), same
# pin numbers as Inkplate13SPECTRA's own SD wiring (same eval board).
SD_SPI_CLK = const(12)
SD_SPI_MISO = const(13)
SD_SPI_MOSI = const(11)
SD_SPI_CS = const(10)

# Battery ADC pin.
BATT_ADC_PIN = const(1)
# Battery-MOSFET pin on the internal PCAL6416A expander.
BATT_MOSFET_PIN = const(9)

# Spectra73 register addresses (vendor Arduino Inkplate7SPECTRADriver pins.h naming).
REG_PSR = const(0x00)
REG_PWR = const(0x01)
REG_POF = const(0x02)
REG_PFS = const(0x03)
REG_PON = const(0x04)
REG_BTST1 = const(0x05)
REG_BTST2 = const(0x06)
REG_BTST3 = const(0x08)
REG_DTM = const(0x10)
REG_DRF = const(0x12)
REG_IPC = const(0x13)
REG_PLL = const(0x30)
REG_TSE = const(0x41)
REG_CDI = const(0x50)
REG_TCON = const(0x60)
REG_TRES = const(0x61)
REG_VDCS = const(0x82)
REG_T_VDCS = const(0x84)
REG_AGID = const(0x86)
REG_CCSET = const(0xE0)
REG_PWS = const(0xE3)
REG_TSSET = const(0xE6)
REG_CMDH = const(0xAA)

# Register values (vendor-provided, manufacturer-tuned).
REG_CMDH_V = bytes([0x49, 0x55, 0x20, 0x08, 0x09, 0x18])
REG_PWR_V = bytes([0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A])
REG_PSR_V = bytes([0x5F, 0x69])
REG_PFS_V = bytes([0x00, 0x54, 0x00, 0x44])
REG_BTST1_V = bytes([0x40, 0x1F, 0x1F, 0x2C])
REG_BTST2_V = bytes([0x6F, 0x1F, 0x16, 0x25])
REG_BTST3_V = bytes([0x6F, 0x1F, 0x1F, 0x22])
REG_IPC_V = bytes([0x00, 0x04])
REG_PLL_V = bytes([0x02])
REG_TSE_V = bytes([0x00])
REG_CDI_V = bytes([0x3F])
REG_TCON_V = bytes([0x02, 0x00])
REG_TRES_V = bytes([0x03, 0x20, 0x01, 0xE0])
REG_VDCS_V = bytes([0x1E])
REG_T_VDCS_V = bytes([0x01])
REG_AGID_V = bytes([0x00])
REG_PWS_V = bytes([0x2F])
REG_CCSET_V = bytes([0x00])
REG_TSSET_V = bytes([0x00])
REG_POF_V = bytes([0x00])
REG_DRF_V = bytes([0x00])

# Epaper resolution (native controller resolution -- already landscape, unlike
# Inkplate13SPECTRA's portrait-native panel, so no default-rotation width/height swap is
# needed here).
D_COLS = const(800)
D_ROWS = const(480)

# User pins on PCAL6416A.
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


# Only one Inkplate() instance is ever created, so state lives on the instance rather
# than the class. draw_bmp/png/jpg_from_sd/_from_web and draw_color_image come from
# shared/mixins/inkplate_image_palette_mixin.py, shared with inkplate6color/
# inkplate13spectra.
class Inkplate(ImagePaletteMixin):
    # Color constants -- values are panel color indices.
    BLACK = const(0)
    WHITE = const(1)
    YELLOW = const(2)
    RED = const(3)
    BLUE = const(4)
    GREEN = const(5)

    # Maps user color index (0-5) to panel register value. Indices 4/5 (BLUE/GREEN) map
    # to 5/6, not 4/5 -- this is the real panel encoding (confirmed against the vendor
    # Arduino driver's colorPalette[]), identical to Inkplate13SPECTRA's own
    # _color_palette since both use the same GDEP-family 6-color controller.
    _color_palette = [0, 1, 2, 3, 5, 6]

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    # Board rotation 0 is a full 180-degree flip in the vendor driver (panel is mounted
    # rotated 180 degrees inside the enclosure) -- same convention as Inkplate6COLOR, so
    # gfx_rotation uses the same +2 offset. NOT the same as Inkplate13SPECTRA, whose
    # offset is inverted (2 - rotation) for its own unrelated reasons.
    _gfx_rotation = 2
    text_size = 1

    _panel_state = False

    _framebuf = None

    def begin(self):
        self.wire = I2C(0)
        self._PCAL6416A = PCAL6416A(self.wire)
        self._rtc = RTC(self.wire)

        # RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C
        # spi_panel transport from here on (firmware/usermods/inkplate/display/
        # epd_spi.c) -- no machine.SPI/Pin objects needed for those.
        inkplate.select_spi_panel("inkplate7spectra")
        inkplate.spi_panel_init()

        # PWR_EN/BS0/BS1 aren't part of spi_panel_config_t for this board -- own them
        # here as plain GPIOs instead. Idle low, matching the vendor driver's
        # setPanelPinsToLow()/setIO() idle levels.
        self._pwr_en = Pin(PWR_EN_PIN, Pin.OUT, value=0)
        self._bs0 = Pin(BS0_PIN, Pin.OUT, value=0)
        self._bs1 = Pin(BS1_PIN, Pin.OUT, value=0)

        # This panel's 4bpp framebuffer packs even physical x into the high nibble, the
        # opposite of gfx_set_pixel's default. Session-constant, set once here.
        inkplate.gfx_set_gs4_nibble_swap(True)

        self.VBAT = ADC(Pin(BATT_ADC_PIN))
        self.VBAT.atten(ADC.ATTN_11DB)
        self.VBAT.width(ADC.WIDTH_12BIT)

        self.SD_ENABLE = GpioPin(self._PCAL6416A, IO_PIN_B2, mode_output)

        self.cursor = [0, 0]
        self.textColor = 0
        self.textWrapping = 1

        # Allocate framebuffer (4bpp, 2 pixels per byte).
        self._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))

        self.font_family = montserrat_black
        self.font = self.font_family._font

        self.set_pcal_for_low_power()

        self._panel_state = False

        return True

    def init_sd_card(self, fast_boot=False):
        self.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(SD_SPI_MISO),
                    mosi=Pin(SD_SPI_MOSI),
                    sck=Pin(SD_SPI_CLK),
                    cs=Pin(SD_SPI_CS),
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

    def get_panel_state(self):
        return self._panel_state

    def set_panel_pins_to_low(self):
        """Discharge panel capacitors before a power-state transition.

        Only touches the pins this board owns directly (RST/PWR_EN/BS0/BS1) -- unlike
        the vendor driver, DC/CS/BUSY stay under the C epd_spi_init() transport's
        control rather than being re-driven here, since that transport already keeps
        them in a defined idle state continuously (see epd_spi_init()'s own comment).
        Assumed equivalent for capacitor discharge purposes; verify on real hardware if
        display() ever refuses to refresh after a power-down, the same failure mode the
        vendor driver's own comment on this step warns about.
        """
        inkplate.spi_panel_set_rst(0)
        self._pwr_en.value(0)
        self._bs0.value(0)
        self._bs1.value(0)

    def set_io(self):
        """Re-assert this panel's fixed interface-select straps (4-wire SPI mode)."""
        self._bs0.value(0)
        self._bs1.value(0)

    def reset_panel(self):
        """Hardware reset of the panel.

        Reuses the single-chip family's epd_spi_reset() (100ms low / 200ms recovery)
        rather than the vendor driver's shorter 10ms/20ms pulse; a longer recovery delay
        does not hurt, same rationale as Inkplate13SPECTRA's own reset_panel().
        """
        inkplate.spi_panel_reset()

    def wait_for_busy(self):
        inkplate.spi_panel_wait_busy(1, 0)

    def send_command(self, command, data=None):
        inkplate.spi_panel_send_command(command)
        if data is not None:
            inkplate.spi_panel_send_data(data)

    def screen_init(self):
        """Send manufacturer register init sequence to the panel."""
        self.send_command(REG_CMDH, REG_CMDH_V)
        self.send_command(REG_PWR, REG_PWR_V)
        self.send_command(REG_PSR, REG_PSR_V)
        self.send_command(REG_PFS, REG_PFS_V)
        self.send_command(REG_BTST1, REG_BTST1_V)
        self.send_command(REG_BTST2, REG_BTST2_V)
        self.send_command(REG_BTST3, REG_BTST3_V)
        self.send_command(REG_IPC, REG_IPC_V)
        self.send_command(REG_PLL, REG_PLL_V)
        self.send_command(REG_TSE, REG_TSE_V)
        self.send_command(REG_CDI, REG_CDI_V)
        self.send_command(REG_TCON, REG_TCON_V)
        self.send_command(REG_TRES, REG_TRES_V)
        self.send_command(REG_VDCS, REG_VDCS_V)
        self.send_command(REG_T_VDCS, REG_T_VDCS_V)
        self.send_command(REG_AGID, REG_AGID_V)
        self.send_command(REG_PWS, REG_PWS_V)
        self.send_command(REG_CCSET, REG_CCSET_V)
        self.send_command(REG_TSSET, REG_TSSET_V)

    def set_panel_state(self, state):
        """Power on/off the panel. When powering on, performs full init sequence."""
        if state == self._panel_state:
            return

        if state:
            # Power up sequence.
            self.set_panel_pins_to_low()
            time.sleep_ms(50)

            self.set_io()

            self._pwr_en.value(1)
            time.sleep_ms(100)

            self.reset_panel()
            self.wait_for_busy()

            self.screen_init()

            self.send_command(REG_PON)
            self.wait_for_busy()
        else:
            # Power off sequence.
            self.send_command(REG_POF, REG_POF_V)
            self.wait_for_busy()

            self._pwr_en.value(0)

        self._panel_state = state

    def clear_display(self):
        if self._framebuf is None:
            self._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))
        else:
            self._framebuf[:] = b"\x11" * len(self._framebuf)

    def display(self, leave_on=False):
        self.set_panel_state(True)

        inkplate.spi_panel_send_command(REG_DTM)
        inkplate.spi_panel_send_data(self._framebuf)

        self.send_command(REG_DRF, REG_DRF_V)
        self.wait_for_busy()

        if not leave_on:
            self.set_panel_state(False)

    def clean(self):
        """Clear the physical display by sending all-white data."""
        self.set_panel_state(True)

        inkplate.spi_panel_send_command(REG_DTM)
        inkplate.spi_panel_send_data(b"\x11" * (D_COLS * D_ROWS // 2))

        self.send_command(REG_DRF, REG_DRF_V)
        self.wait_for_busy()

        self.set_panel_state(False)

    def gpio_expander_pin(self, pin, mode):
        return GpioPin(self._PCAL6416A, pin, mode)

    # Same PCF85263-style RTC chip every other board wires; delegates to
    # shared/drivers/rtc.py.
    def rtc_set_time(self, rtc_hour, rtc_minute, rtc_second):
        self._rtc.set_time(rtc_hour, rtc_minute, rtc_second)

    def rtc_set_date(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        self._rtc.set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtc_get_rtc_data(self):
        return self._rtc.get_data()

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

    # Maps a user color index (0-5) to the panel's real register value, or None if out
    # of range. Every gfx_* wrapper below does this once per call instead of once per
    # pixel.
    def _map_color(self, c):
        if c > 5:
            return None
        return self._color_palette[c]

    def write_pixel(self, x, y, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_set_pixel(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, c)

    def write_fill_rect(self, x, y, w, h, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_rect(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, h, c)

    def write_fast_vline(self, x, y, h, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_vline(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, h, c)

    def write_fast_hline(self, x, y, w, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_hline(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, c)

    def set_text_color(self, c):
        self.textColor = c

    def write_line(self, x0, y0, x1, y1, c):
        c = self._map_color(c)
        if c is None:
            return
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
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_rect(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, w, h, c)

    def draw_circle(self, x, y, r, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_circle(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, r, c)

    def fill_circle(self, x, y, r, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_circle(self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, r, c)

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_triangle(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_triangle(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    def draw_round_rect(self, x, y, q, h, r, c):
        c = self._map_color(c)
        if c is None:
            return
        inkplate.gfx_round_rect(
            self._framebuf, D_COLS, D_ROWS, self._gfx_rotation, 1, x, y, q, h, r, c
        )

    def fill_round_rect(self, x, y, q, h, r, c):
        c = self._map_color(c)
        if c is None:
            return
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

    # Color goes through _color_palette once here instead of once per pixel, like every
    # other gfx_* wrapper on this board.
    def _print_text(self, framebuf, x0, y0, string, size, color, text_wrap=False):
        display_width = self._width
        color = self._color_palette[min(max(color, 0), 5)]

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
        # Some board revisions wire a P-MOS-only divider (reads high when idle), newer
        # ones P-MOS+N-MOS (reads low when idle) -- probe which before toggling it,
        # mirroring the vendor driver's readBattery().
        self._PCAL6416A.pin_mode(BATT_MOSFET_PIN, mode_input)
        state = self._PCAL6416A.digital_read(BATT_MOSFET_PIN)
        self._PCAL6416A.pin_mode(BATT_MOSFET_PIN, mode_output)
        self._PCAL6416A.digital_write(BATT_MOSFET_PIN, 0 if state else 1)

        time.sleep_ms(5)
        value = self.VBAT.read()

        self._PCAL6416A.digital_write(BATT_MOSFET_PIN, 1 if state else 0)

        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    def draw_bitmap(self, x, y, data, w, h, c=BLACK):
        c = self._map_color(c)
        if c is None:
            return
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
