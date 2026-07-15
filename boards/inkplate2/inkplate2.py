"""MicroPython driver for the Inkplate 2 e-paper display."""

import time
from machine import I2C, Pin
from micropython import const
from gfx import GFX

import machine
import inkplate

machine.freq(240000000)

# RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C spi_panel
# transport (firmware/usermods/inkplate/epd_spi.c, docs/REFACTOR-PLAN.md Phase 9 step 31)
# -- no Python-side pin constants needed.

pixel_mask_lut = [0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80]
pixel_mask_glut = [0xF, 0xF0]

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
    text_size = 1

    _panel_state = False

    cursor = [0, 0]

    @classmethod
    def begin(cls):
        cls.wire = I2C(0, scl=Pin(22), sda=Pin(21))

        # RST/DC/CS/BUSY/CLK/DIN + the SPI peripheral itself are owned by the C
        # spi_panel transport from here on (firmware/usermods/inkplate/epd_spi.c,
        # docs/REFACTOR-PLAN.md Phase 9 step 31) -- no more machine.SPI/Pin objects for
        # the panel itself.
        inkplate.select_spi_panel("inkplate2")
        inkplate.spi_panel_init()

        cls._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        cls._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        cls.text_color = 1
        cls.textWrapping = 1

        cls.GFX = GFX(
            E_INK_HEIGHT,
            E_INK_WIDTH,
            cls.write_pixel,
            cls.write_fast_hline,
            cls.write_fast_vline,
            cls.write_fill_rect,
            None,
            None,
        )

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
        if cls.rotation == 0 or cls.rotation == 2:
            cls.GFX.width = E_INK_WIDTH
            cls.GFX.height = E_INK_HEIGHT
            cls._width = E_INK_WIDTH
            cls._height = E_INK_HEIGHT
        elif cls.rotation == 1 or cls.rotation == 3:
            cls.GFX.width = E_INK_HEIGHT
            cls.GFX.height = E_INK_WIDTH
            cls._width = E_INK_HEIGHT
            cls._height = E_INK_WIDTH

    @classmethod
    def get_rotation(cls):
        return cls.rotation

    @classmethod
    def draw_pixel(cls, x, y, c):
        cls.write_pixel(x, y, c)

    @classmethod
    @micropython.native
    def write_pixel(cls, x, y, c):
        # Bounds check
        if not (0 <= x < cls.width() and 0 <= y < cls.height()):
            return
        if c > 2:
            return

        # Rotate coordinates
        if cls.rotation == 3:
            x, y = y, cls.width() - x - 1
        elif cls.rotation == 0:
            x, y = cls.width() - x - 1, cls.height() - y - 1
        elif cls.rotation == 1:
            x, y = cls.height() - y - 1, x

        # Compute position in frame buffer
        _x_sub = x % 8
        _x = x // 8
        _position = (E_INK_WIDTH // 8) * y + _x

        # Precompute LUT mask
        mask = pixel_mask_lut[7 - _x_sub]

        # Clear the bits in both buffers
        cls._framebuf_BW[_position] |= mask
        cls._framebuf_RED[_position] |= mask

        # Apply color
        if c < 2:
            # Black or white: clear bit in BW buffer accordingly
            cls._framebuf_BW[_position] &= ~(c << (7 - _x_sub))
        else:
            # Red pixel: clear bit in RED buffer
            cls._framebuf_RED[_position] &= ~mask

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
    def write_line(cls, x0, y0, x1, y1, c):
        cls.GFX.line(x0, y0, x1, y1, c)

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
    def set_text_color(cls, c):
        cls.text_color = c

    @classmethod
    def set_text_size(cls, s):
        cls.text_size = s

    @classmethod
    def set_font(cls, f):
        cls.GFX.font_family = f
        cls.GFX.font = cls.GFX.font_family._font

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    def set_text_wrapping(self, state: bool):
        self.textWrapping = state

    def print_text(self, x, y, s, c=1):
        self.GFX._print_text(
            self._framebuf_BW,
            x,
            y,
            s,
            self.text_size,
            c,
            text_wrap=self.textWrapping,
            bpp=1,
        )

    def println(self, text):
        self.cursor, line_height = self.GFX._print_text(
            self._framebuf_BW,
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.text_color,
            text_wrap=self.textWrapping,
            bpp=1,
        )
        self.cursor[1] += line_height
        self.cursor[0] = 0

    def print(self, text):
        self.cursor, _ = self.GFX._print_text(
            self._framebuf_BW,
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.text_color,
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

    @classmethod
    def draw_bitmap(cls, x, y, data, w, h, c=BLACK):
        byte_width = (w + 7) // 8
        byte = 0

        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byte_width + i // 8]
                if byte & 0x80:
                    cls.write_pixel(x + i, y + j, c)

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
                print(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()

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
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()

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


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
