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

    def draw_jpg_from_web(
        self, url, x0=0, y0=0, invert=False, dither: bool = False, kernel_type: int = 0
    ):
        import jpeg
        import urequests

        try:
            # 1. Initialize decoder
            decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")

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

            self.rgb565_to_2bpp(decoded, width, height, dither)

        except Exception as e:
            print("Error in draw_jpg_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def rgb565_to_2bpp(self, imagedata, width: int, height: int, dither: bool = True):
        row_bytes: int = -(-width // 4)
        outbuf = bytearray(row_bytes * height)

        if dither:
            # use a signed error buffer as ints to avoid overflow
            error_buffer = [0] * (width * height * 3)
        else:
            error_buffer = [0]  # dummy

        @micropython.viper
        def process_pixel(im: ptr8, out: ptr8, err: ptr32, w: int, h: int, do_dither: int):
            for y in range(h):
                for x in range(w):
                    idx = (y * w + x) * 2
                    pixel = im[idx] | (im[idx + 1] << 8)

                    r = ((pixel >> 11) & 0x1F) * 255 // 31
                    g = ((pixel >> 5) & 0x3F) * 255 // 63
                    b = (pixel & 0x1F) * 255 // 31

                    if do_dither:
                        e_idx = (y * w + x) * 3
                        r = int(min(255, int(max(0, r + err[e_idx]))))
                        g = int(min(255, int(max(0, g + err[e_idx + 1]))))
                        b = int(min(255, int(max(0, b + err[e_idx + 2]))))

                    # classify pixel
                    if r > int(max(g, b)) * 3 // 2 and r > 128:
                        c = 2  # red
                        new_r, new_g, new_b = 255, 0, 0
                    elif r + g + b < 384:
                        c = 0  # black
                        new_r, new_g, new_b = 0, 0, 0
                    else:
                        c = 1  # white
                        new_r, new_g, new_b = 255, 255, 255

                    # propagate error
                    if do_dither:
                        e_idx = (y * w + x) * 3
                        err_r = r - int(new_r)
                        err_g = g - int(new_g)
                        err_b = b - int(new_b)

                        if x + 1 < w:
                            e = (y * w + (x + 1)) * 3
                            err[e] += err_r * 7 // 16
                            err[e + 1] += err_g * 7 // 16
                            err[e + 2] += err_b * 7 // 16
                        if y + 1 < h:
                            if x > 0:
                                e = ((y + 1) * w + (x - 1)) * 3
                                err[e] += err_r * 3 // 16
                                err[e + 1] += err_g * 3 // 16
                                err[e + 2] += err_b * 3 // 16
                            e = ((y + 1) * w + x) * 3
                            err[e] += err_r * 5 // 16
                            err[e + 1] += err_g * 5 // 16
                            err[e + 2] += err_b * 5 // 16
                            if x + 1 < w:
                                e = ((y + 1) * w + (x + 1)) * 3
                                err[e] += err_r * 1 // 16
                                err[e + 1] += err_g * 1 // 16
                                err[e + 2] += err_b * 1 // 16

                    # pack 2bpp
                    byte_idx = int(y) * int(row_bytes) + int(x >> 2)
                    shift = (3 - (x & 3)) * 2
                    out[byte_idx] |= (c & 0x03) << shift

        # cast Python list to ptr32 for Viper signed access
        import array

        if dither:
            err_arr = array.array("i", error_buffer)
        else:
            err_arr = array.array("i", [0])

        process_pixel(imagedata, outbuf, err_arr, width, height, 1 if dither else 0)
        Inkplate.draw_color_image_viper(0, 0, width, height, outbuf)

    @staticmethod
    @micropython.viper
    def draw_color_image_viper(x: int, y: int, w: int, h: int, buf_obj):
        scaled_w = (w + 3) // 4
        buf = ptr8(buf_obj)
        for i in range(h):
            for j in range(w):
                byte_idx = (i * scaled_w) + (j >> 2)
                shift = (3 - (j & 3)) * 2
                pix = (buf[byte_idx] >> shift) & 0x03
                Inkplate.write_pixel(j + x, i + y, pix)

    def draw_png_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()

            Inkplate.decode_png_to_framebuffer(png_data, x0, y0, invert, dither)
            gc.collect()

        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()

    @staticmethod
    @micropython.native
    def decode_png_to_framebuffer(png_data, x0, y0, invert=False, dither=False):
        import deflate
        import io
        import array

        _screen_width_ = const(212)
        _screen_height_ = const(104)

        @micropython.native
        def parse_chunks(png_bytes):
            pos = 8
            ihdr = None
            idat_list = []
            plte = None
            while pos + 8 <= len(png_bytes):
                clen = int.from_bytes(png_bytes[pos : pos + 4], "big")
                ctype = png_bytes[pos + 4 : pos + 8]
                cstart = pos + 8
                cend = cstart + clen
                if ctype == b"IHDR":
                    ihdr = png_bytes[cstart:cend]
                elif ctype == b"PLTE":
                    plte = png_bytes[cstart:cend]
                elif ctype == b"IDAT":
                    idat_list.append(png_bytes[cstart:cend])
                elif ctype == b"IEND":
                    break
                pos = cend + 4
            return ihdr, b"".join(idat_list), plte

        def bytes_per_pixel(bit_depth, color_type):
            if bit_depth != 8:
                raise ValueError("Only 8-bit PNGs supported in this decoder path")
            if color_type == 0:
                return 1
            if color_type == 2:
                return 3
            if color_type == 4:
                return 2
            if color_type == 6:
                return 4
            if color_type == 3:
                raise ValueError("Indexed-color PNG not supported without PLTE palette handling")
            raise ValueError("Unsupported color type: %d" % color_type)

        if len(png_data) < 8 or png_data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG signature")

        ihdr, idat, plte = parse_chunks(png_data)
        if not ihdr:
            raise ValueError("Missing IHDR")
        if not idat:
            raise ValueError("No IDAT chunks")

        width = int.from_bytes(ihdr[0:4], "big")
        height = int.from_bytes(ihdr[4:8], "big")
        bit_depth = ihdr[8]
        color_type = ihdr[9]
        interlace = ihdr[12]

        if interlace != 0:
            raise ValueError("Interlaced PNG not supported in this path")

        bpp = bytes_per_pixel(bit_depth, color_type)

        draw_width = width if (x0 + width) <= _screen_width_ else _screen_width_ - x0
        draw_height = height if (y0 + height) <= _screen_height_ else _screen_height_ - y0
        if draw_width <= 0 or draw_height <= 0:
            return

        dstream = deflate.DeflateIO(io.BytesIO(idat))
        stride = 1 + width * bpp

        cur = bytearray(width * bpp)
        prev = bytearray(width * bpp)

        if dither:
            err_w = draw_width
            err_cur = array.array("h", [0] * err_w)
            err_nxt = array.array("h", [0] * err_w)

        inv_mask = 1 if invert else 0

        @micropython.native
        def apply_filter(raw, cur_row, prev_row, bpp_):
            f = raw[0]
            data = raw[1:]
            if f == 0:
                cur_row[:] = data
            elif f == 1:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    cur_row[i] = (data[i] + a) & 0xFF
            elif f == 2:
                for i in range(len(data)):
                    b = prev_row[i]
                    cur_row[i] = (data[i] + b) & 0xFF
            elif f == 3:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    b = prev_row[i]
                    cur_row[i] = (data[i] + ((a + b) >> 1)) & 0xFF
            elif f == 4:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    b = prev_row[i]
                    c = prev_row[i - bpp_] if i >= bpp_ else 0
                    p = a + b - c
                    pa = p - a
                    if pa < 0:
                        pa = -pa
                    pb = p - b
                    if pb < 0:
                        pb = -pb
                    pc = p - c
                    if pc < 0:
                        pc = -pc
                    if pa <= pb and pa <= pc:
                        pred = a
                    elif pb <= pc:
                        pred = b
                    else:
                        pred = c
                    cur_row[i] = (data[i] + pred) & 0xFF
            else:
                raise ValueError("Unknown PNG filter: %d" % f)

        for y in range(height):
            raw = dstream.read(stride)
            if not raw or len(raw) != stride:
                break
            apply_filter(raw, cur, prev, bpp)

            if y >= draw_height:
                cur, prev = prev, cur
                continue

            base = 0
            for x in range(draw_width):
                if color_type == 0:
                    r = g = b = cur[base]
                    a = 255
                elif color_type == 2:
                    r = cur[base]
                    g = cur[base + 1]
                    b = cur[base + 2]
                    a = 255
                elif color_type == 4:
                    r = g = b = cur[base]
                    a = cur[base + 1]
                elif color_type == 6:
                    r = cur[base]
                    g = cur[base + 1]
                    b = cur[base + 2]
                    a = cur[base + 3]
                else:
                    r = g = b = 0
                    a = 255

                base += bpp

                if a < 255:
                    bg = 255 if invert else 0
                    r = (r * a + bg * (255 - a)) // 255
                    g = (g * a + bg * (255 - a)) // 255
                    b = (b * a + bg * (255 - a)) // 255

                # red detection (same rule you used)
                is_red = (r * 2 > max(g, b) * 3) and (r > 128)

                if a == 0:
                    # transparent -> white (or inverted)
                    val = 1 ^ inv_mask
                elif is_red:
                    # red pixel
                    val = 2
                else:
                    # grayscale luminance
                    gray = (r * 77 + g * 151 + b * 28) >> 8

                    if dither:
                        gray = gray + err_cur[x]
                        if gray < 0:
                            gray = 0
                        elif gray > 255:
                            gray = 255

                    val = 0 if gray > 127 else 1  # 1 = white, 0 = black
                    val_before_inv = val
                    if invert:
                        val ^= 1

                    if dither:
                        # predicted brightness for chosen color: 0 for black, 255 for white
                        quant = 255 if val_before_inv == 0 else 1
                        delta = gray - quant
                        if x + 1 < draw_width:
                            err_cur[x + 1] += (delta * 7) // 16
                        if y + 1 < draw_height:
                            if x > 0:
                                err_nxt[x - 1] += (delta * 3) // 16
                            err_nxt[x] += (delta * 5) // 16
                            if x + 1 < draw_width:
                                err_nxt[x + 1] += (delta * 1) // 16

                Inkplate.write_pixel(x0 + x, y0 + y, val)

            if dither:
                err_cur, err_nxt = err_nxt, err_cur
                for i in range(draw_width):
                    err_nxt[i] = 0

            cur, prev = prev, cur

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False):
        """Display a BMP image downloaded from the web

        Args:
            bmp_data (bytes): Raw BMP file data
            x0 (int): X position to start drawing
            y0 (int): Y position to start drawing
            invert (bool): Whether to invert colors
            dither (bool): Whether to apply dithering
        """
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")

            bmp_data = response.content
            response.close()
            Inkplate.decode_bmp(bmp_data, x0, y0, invert, dither)
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()

    @staticmethod
    @micropython.native
    def decode_bmp(bmp_data, x0, y0, invert, dither):
        import array

        __screen_width_ = const(212)
        __screen_height_ = const(104)

        # BMP header parsing (support only uncompressed 24-bit or 32-bit BMP)
        if bmp_data[0:2] != b"BM":
            raise ValueError("Not a BMP file")
        int.from_bytes(bmp_data[2:6], "little")
        pixel_offset = int.from_bytes(bmp_data[10:14], "little")
        int.from_bytes(bmp_data[14:18], "little")
        width = int.from_bytes(bmp_data[18:22], "little", True)
        height = int.from_bytes(bmp_data[22:26], "little", True)
        planes = int.from_bytes(bmp_data[26:28], "little")
        bpp = int.from_bytes(bmp_data[28:30], "little")
        compression = int.from_bytes(bmp_data[30:34], "little")

        if compression != 0 or planes != 1 or bpp not in (24, 32):
            raise ValueError("Unsupported BMP format")

        # BMP rows are padded to 4 bytes
        row_bytes = ((width * bpp + 31) // 32) * 4
        draw_width = min(width, __screen_width_ - x0)
        draw_height = min(abs(height), __screen_height_ - y0)
        if draw_width <= 0 or draw_height <= 0:
            return

        # prepare dithering buffers
        if dither:
            err_cur = array.array("h", [0] * draw_width)
            err_nxt = array.array("h", [0] * draw_width)

        inv_mask = 1 if invert else 0
        flipped = height > 0  # BMP stores bottom-up if height > 0

        for y_img in range(draw_height):
            if flipped:
                y_bmp = height - 1 - y_img
            else:
                y_bmp = y_img
            row_start = pixel_offset + y_bmp * row_bytes
            row_data = bmp_data[row_start : row_start + width * (bpp // 8)]

            for x in range(draw_width):
                base = x * (bpp // 8)
                b = row_data[base]
                g = row_data[base + 1]
                r = row_data[base + 2]
                a = row_data[base + 3] if bpp == 32 else 255

                # alpha blending (against white background)
                if a < 255:
                    bg = 255 if invert else 0
                    r = (r * a + bg * (255 - a)) // 255
                    g = (g * a + bg * (255 - a)) // 255
                    b = (b * a + bg * (255 - a)) // 255

                # red detection
                is_red = (r * 2 > max(g, b) * 3) and (r > 128)

                if a == 0:
                    val = 1 ^ inv_mask  # transparent -> white
                elif is_red:
                    val = 2
                else:
                    gray = (r * 77 + g * 151 + b * 28) >> 8
                    if dither:
                        gray = gray + err_cur[x]
                        if gray < 0:
                            gray = 0
                        elif gray > 255:
                            gray = 255

                    val = 0 if gray > 127 else 1
                    val_before_inv = val
                    if invert:
                        val ^= 1

                    if dither:
                        quant = 255 if val_before_inv == 0 else 0
                        delta = gray - quant
                        if x + 1 < draw_width:
                            err_cur[x + 1] += (delta * 7) // 16
                        if y_img + 1 < draw_height:
                            if x > 0:
                                err_nxt[x - 1] += (delta * 3) // 16
                            err_nxt[x] += (delta * 5) // 16
                            if x + 1 < draw_width:
                                err_nxt[x + 1] += (delta * 1) // 16

                Inkplate.write_pixel(x0 + x, y0 + y_img, val)

            if dither:
                err_cur, err_nxt = err_nxt, err_cur
                for i in range(draw_width):
                    err_nxt[i] = 0


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
