"""Shared image-decode (bmp/png/jpg, sd/web) for the single-buffer palette-color
Inkplate boards (Inkplate6COLOR/13SPECTRA).

Host class contract -- must provide before any of these are called:
    self._framebuf   the panel's single packed-palette framebuffer (bytearray)
    self.rotation    0-3, current rotation (native numbering, not gfx.c's offset one)
    self.write_pixel(x, y, c)   used by draw_color_image
"""

import gc

import inkplate


class ImagePaletteMixin:
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

    def draw_image(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """Draw an image from either a web URL or a local file path.

        dither/kernel_type select a dithering algorithm (0=Floyd-Steinberg, 1=JJN,
        2=Stucki, 3=Burkes); invert flips colors.
        """
        if path.startswith(("http://", "https://")):
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_web(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_web(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_sd(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_sd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")

    def draw_jpg_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        with open(path, "rb") as f:
            jpg_data = f.read()
        inkplate.jpeg_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, jpg_data
        )
        gc.collect()

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        with open(path, "rb") as f:
            png_data = f.read()
        # No scratch buffer passed: png_draw_palette only needs one for a rare
        # Adam7-interlaced source (dithers non-interlaced PNGs -- the common case --
        # inline, per pixel, no whole-image buffer at all). Pre-allocating one here
        # unconditionally used to reliably MemoryError on real hardware for completely
        # ordinary photos -- worse than the rare case this was meant to serve.
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
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

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
            raise

    def draw_jpg_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
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
        gc.collect()
        with open(path, "rb") as f:
            bmp_data = f.read()

        inkplate.bmp_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, bmp_data
        )
        del bmp_data
        gc.collect()

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

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
            raise
