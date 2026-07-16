"""MicroPython driver for the Inkplate 2 e-paper display."""

import time
from machine import I2C, Pin
from micropython import const
import gfx_standard_font_01 as montserrat_black

import machine
import inkplate

machine.freq(240000000)

# RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C spi_panel
# transport (firmware/usermods/inkplate/epd_spi.c, docs/refactor_plan.md Phase 9 step 31)
# -- no Python-side pin constants needed.

# ePaper resolution
# For Inkplate2 height and width are swapped in relation to the default rotation
E_INK_HEIGHT = 212
E_INK_WIDTH = 104

E_INK_NUM_PIXELS = E_INK_HEIGHT * E_INK_WIDTH
E_INK_BUFFER_SIZE = E_INK_NUM_PIXELS // 8

# From the real Arduino reference driver's pins.h BUSY_TIMEOUT_MS -- used for the
# init-wake (command 0x04) and sleep (command 0x02) busy-waits. display()'s own
# post-refresh wait uses a separate, longer timeout (see DISPLAY_REFRESH_TIMEOUT_MS)
# matching the reference driver's own distinct inline value there.
busy_timeout_ms = 1000

# From the real Arduino reference driver's display(): waitForEpd(60000) after sending
# the refresh command (0x12) -- a full panel refresh takes far longer than the
# init/sleep BUSY_TIMEOUT_MS above.
display_refresh_timeout_ms = 60000


class Inkplate:
    # Colors
    WHITE = 0b00000000
    BLACK = 0b00000001
    RED = 0b00000010

    _width = E_INK_WIDTH
    _height = E_INK_HEIGHT

    text_color = BLACK

    rotation = 0
    # gfx_* calls use a rotation numbering offset by 2 from this board's own `rotation`
    # (board rotation 0 is physically what gfx.c's rotation-remap calls rotation 2, same
    # offset as Inkplate6COLOR) -- see set_rotation(). Recomputed there; begin() below
    # never sets `rotation` directly, only via set_rotation(), so this default is
    # overwritten before first use.
    _gfx_rotation = 2
    text_size = 1

    _panel_state = False

    cursor = [0, 0]

    @classmethod
    def begin(cls):
        cls.wire = I2C(0, scl=Pin(22), sda=Pin(21))

        # RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C
        # spi_panel transport from here on (firmware/usermods/inkplate/epd_spi.c,
        # docs/refactor_plan.md Phase 9 step 31) -- no more machine.SPI/Pin objects for
        # the panel itself.
        inkplate.select_spi_panel("inkplate2")
        inkplate.spi_panel_init()

        cls._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        cls._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        cls.text_color = 1
        cls.textWrapping = 1

        cls.font_family = montserrat_black
        cls.font = cls.font_family._font

        # Wake the panel and init it
        if not (cls.set_panel_deep_sleep_state(False)):
            return False

        # Put it back to sleep
        cls.set_panel_deep_sleep_state(True)

        # 3 is the default rotation for Inkplate 2
        cls.set_rotation(3)

        cls.text_size = 1

        return True

    @classmethod
    def get_panel_deep_sleep_state(cls):
        return cls._panel_state

    @classmethod
    def set_panel_deep_sleep_state(cls, state):
        # False wakes the panel up
        # True puts it to sleep
        #
        # Pin config/CS+DC idle levels and the SPI bus itself are owned by the C
        # spi_panel transport (epd_spi_init(), already called once from begin()) --
        # only the reset+reinit / sleep-register sequence needs repeating here, same
        # convention as boards/inkplate6color/inkplate6_color.py's own
        # set_panel_deep_sleep().
        if not state:
            cls.reset_panel()

            # Reinit the panel
            cls.send_command(0x04)
            if not inkplate.spi_panel_wait_busy(1, busy_timeout_ms):
                return False

            cls.send_command(0x00)
            cls.send_data(b"\x0f")
            cls.send_data(b"\x89")
            cls.send_command(0x61)
            cls.send_data(b"\x68")
            cls.send_data(b"\x00")
            cls.send_data(b"\xd4")
            cls.send_command(0x50)
            cls.send_data(b"\x77")

            cls._panel_state = True

            return True

        else:
            # Put the panel to sleep
            cls.send_command(0x50)
            cls.send_data(b"\xf7")
            cls.send_command(0x02)
            inkplate.spi_panel_wait_busy(1, busy_timeout_ms)
            cls.send_command(0x07)
            cls.send_data(b"\xa5")

            time.sleep_ms(1)

            # Hold RST asserted low while asleep (matches the real Arduino reference
            # driver's setPanelDeepSleep(true) -- lower power than leaving it floating
            # or driven high).
            inkplate.spi_panel_set_rst(0)

            cls._panel_state = False

            return False

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
        cls._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        cls._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))

    @classmethod
    def display(cls):
        # Wake the display
        cls.set_panel_deep_sleep_state(False)

        # Write b/w pixels
        cls.send_command(0x10)
        cls.send_data(cls._framebuf_BW)

        # Write red pixels
        cls.send_command(0x13)
        cls.send_data(cls._framebuf_RED)

        # Stop transfer
        cls.send_command(0x11)
        cls.send_data(b"\x00")

        # Refresh
        cls.send_command(0x12)
        time.sleep_us(500)
        inkplate.spi_panel_wait_busy(1, display_refresh_timeout_ms)

        # Put the display back to sleep
        cls.set_panel_deep_sleep_state(True)

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
        cls._gfx_rotation = (cls.rotation + 2) % 4
        if cls.rotation == 0 or cls.rotation == 2:
            cls._width = E_INK_WIDTH
            cls._height = E_INK_HEIGHT
        elif cls.rotation == 1 or cls.rotation == 3:
            cls._width = E_INK_HEIGHT
            cls._height = E_INK_WIDTH

    @classmethod
    def get_rotation(cls):
        return cls.rotation

    @classmethod
    def draw_pixel(cls, x, y, c):
        cls.write_pixel(x, y, c)

    # Maps a user color (WHITE=0/BLACK=1/RED=2) to independent 1bpp draw values for the
    # BW and RED planes -- this board's own pre-refactor write_pixel forced both planes'
    # bits high, then cleared exactly one plane's bit depending on c (BLACK clears BW,
    # RED clears RED, WHITE clears neither). Returns None if c is out of range (mirrors
    # the original per-pixel bounds check).
    @classmethod
    def _plane_colors(cls, c):
        if c > 2:
            return None
        return (0 if c == 1 else 1), (0 if c == 2 else 1)

    @classmethod
    def write_pixel(cls, x, y, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_set_pixel(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, bw
        )
        inkplate.gfx_set_pixel(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, red
        )

    @classmethod
    def write_fill_rect(cls, x, y, w, h, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_fill_rect(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, h, bw
        )
        inkplate.gfx_fill_rect(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, h, red
        )

    @classmethod
    def write_fast_vline(cls, x, y, h, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_vline(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, h, bw
        )
        inkplate.gfx_vline(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, h, red
        )

    @classmethod
    def write_fast_hline(cls, x, y, w, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_hline(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, bw
        )
        inkplate.gfx_hline(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, red
        )

    @classmethod
    def write_line(cls, x0, y0, x1, y1, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_line(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x0, y0, x1, y1, bw
        )
        inkplate.gfx_line(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x0, y0, x1, y1, red
        )

    @classmethod
    def end_write(cls):
        pass

    @classmethod
    def draw_fast_vline(cls, x, y, h, c):
        cls.write_fast_vline(x, y, h, c)

    @classmethod
    def draw_fast_hline(cls, x, y, w, c):
        cls.write_fast_hline(x, y, w, c)

    @classmethod
    def fill_rect(cls, x, y, w, h, c):
        cls.write_fill_rect(x, y, w, h, c)

    @classmethod
    def fill_screen(cls, c):
        cls.fill_rect(0, 0, cls.width(), cls.height(), c)

    @classmethod
    def draw_line(cls, x0, y0, x1, y1, c):
        cls.write_line(x0, y0, x1, y1, c)

    @classmethod
    def draw_rect(cls, x, y, w, h, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_rect(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, h, bw
        )
        inkplate.gfx_rect(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, w, h, red
        )

    @classmethod
    def draw_circle(cls, x, y, r, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_circle(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, r, bw
        )
        inkplate.gfx_circle(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, r, red
        )

    @classmethod
    def fill_circle(cls, x, y, r, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_fill_circle(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, r, bw
        )
        inkplate.gfx_fill_circle(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, r, red
        )

    @classmethod
    def draw_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_triangle(
            cls._framebuf_BW,
            E_INK_WIDTH,
            E_INK_HEIGHT,
            cls._gfx_rotation,
            0,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            bw,
        )
        inkplate.gfx_triangle(
            cls._framebuf_RED,
            E_INK_WIDTH,
            E_INK_HEIGHT,
            cls._gfx_rotation,
            0,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            red,
        )

    @classmethod
    def fill_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_fill_triangle(
            cls._framebuf_BW,
            E_INK_WIDTH,
            E_INK_HEIGHT,
            cls._gfx_rotation,
            0,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            bw,
        )
        inkplate.gfx_fill_triangle(
            cls._framebuf_RED,
            E_INK_WIDTH,
            E_INK_HEIGHT,
            cls._gfx_rotation,
            0,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            red,
        )

    @classmethod
    def draw_round_rect(cls, x, y, q, h, r, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_round_rect(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, q, h, r, bw
        )
        inkplate.gfx_round_rect(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, q, h, r, red
        )

    @classmethod
    def fill_round_rect(cls, x, y, q, h, r, c):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_fill_round_rect(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, q, h, r, bw
        )
        inkplate.gfx_fill_round_rect(
            cls._framebuf_RED, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, q, h, r, red
        )

    @classmethod
    def set_text_color(cls, c):
        cls.text_color = c

    @classmethod
    def set_text_size(cls, s):
        cls.text_size = s

    @classmethod
    def set_font(cls, f):
        cls.font_family = f
        cls.font = cls.font_family._font

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    def set_text_wrapping(self, state: bool):
        self.textWrapping = state

    # Ported from this board's own gfx.py GFX._print_text/_draw_char_dual_buf, with the
    # per-char blit routed through inkplate.gfx_draw_char (once per plane, like every
    # other gfx_* wrapper on this board) instead of a write_pixel-per-subpixel Python
    # loop. Color clamps to 0-2 rather than rejecting out of range, matching the
    # original gfx.py behavior (unlike write_pixel/_plane_colors, which reject).
    def _print_text(self, x0, y0, string, size, color, text_wrap=False):
        display_width = self._width
        color = min(max(color, 0), 2)
        bw = 0 if color == 1 else 1
        red = 0 if color == 2 else 1

        x = int(x0)
        y = int(y0)
        line_height = 0

        def blit(cx, cy, char_data, ch_w, ch_h):
            inkplate.gfx_draw_char(
                self._framebuf_BW,
                E_INK_WIDTH,
                E_INK_HEIGHT,
                self._gfx_rotation,
                0,
                cx,
                cy,
                char_data,
                ch_w,
                ch_h,
                size,
                bw,
            )
            inkplate.gfx_draw_char(
                self._framebuf_RED,
                E_INK_WIDTH,
                E_INK_HEIGHT,
                self._gfx_rotation,
                0,
                cx,
                cy,
                char_data,
                ch_w,
                ch_h,
                size,
                red,
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

    def print_text(self, x, y, s, c=1):
        self._print_text(x, y, s, self.text_size, c, text_wrap=self.textWrapping)

    def println(self, text):
        self.cursor, line_height = self._print_text(
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.text_color,
            text_wrap=self.textWrapping,
        )
        self.cursor[1] += line_height
        self.cursor[0] = 0

    def print(self, text):
        self.cursor, _ = self._print_text(
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.text_color,
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
    def draw_bitmap(cls, x, y, data, w, h, c=BLACK):
        colors = cls._plane_colors(c)
        if colors is None:
            return
        bw, red = colors
        inkplate.gfx_draw_bitmap(
            cls._framebuf_BW, E_INK_WIDTH, E_INK_HEIGHT, cls._gfx_rotation, 0, x, y, data, w, h, bw
        )
        inkplate.gfx_draw_bitmap(
            cls._framebuf_RED,
            E_INK_WIDTH,
            E_INK_HEIGHT,
            cls._gfx_rotation,
            0,
            x,
            y,
            data,
            w,
            h,
            red,
        )

    @classmethod
    def draw_color_bitmap(cls, x, y, w, h, buf):
        scaled_w = int(-(-(w / 4.0) // 1))
        for i in range(h):
            for j in range(scaled_w):
                cls.write_pixel(4 * j + x, i + y, (buf[scaled_w * i + j] & 0xC0) >> 6)
                if 4 * j + x + 1 < w:
                    cls.write_pixel(4 * j + x + 1, i + y, (buf[scaled_w * i + j] & 0x30) >> 4)
                if 4 * j + x + 2 < w:
                    cls.write_pixel(4 * j + x + 2, i + y, (buf[scaled_w * i + j] & 0x0C) >> 2)
                if 4 * j + x + 3 < w:
                    cls.write_pixel(4 * j + x + 3, i + y, (buf[scaled_w * i + j] & 0x03))

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
            raise ValueError("Draw Image error: URL could not be parsed.")

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
                self._framebuf_BW,
                self._framebuf_RED,
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

    def draw_png_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()

            # No scratch buffer passed: png_draw_palette only needs one for a rare
            # Adam7-interlaced source (dithers non-interlaced PNGs -- the common
            # case -- inline, per pixel, no whole-image buffer at all).
            # Pre-allocating one here unconditionally used to reliably MemoryError
            # on real Inkplate6COLOR hardware for completely ordinary photos
            # (docs/refactor_plan.md Phase 7 step 21's follow-up) -- worse than the
            # rare case this was meant to serve.
            inkplate.png_draw_palette(
                self._framebuf_BW,
                self._framebuf_RED,
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
            raise

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
                raise ValueError(f"HTTP Error {response.status_code}")

            bmp_data = response.content
            response.close()
            inkplate.bmp_draw_palette(
                self._framebuf_BW,
                self._framebuf_RED,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                bmp_data,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()
            raise


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
