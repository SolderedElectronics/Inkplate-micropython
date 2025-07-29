"""
`gfx`
====================================================

CircuitPython pixel graphics drawing library.

* Author(s): Kattni Rembor, Tony DiCola, Jonah Yolles-Murphy, based on code by Phil Burgess

Implementation Notes
--------------------

**Hardware:**

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_GFX.git"

import gfx_standard_font_01 as MontserratBlack
class GFX:
    """Create an instance of the GFX drawing class.

    :param width: The width of the drawing area in pixels.
    :param height: The height of the drawing area in pixels.
    :param pixel: A function to call when a pixel is drawn on the display. This function
                  should take at least an x and y position and then any number of optional
                  color or other parameters.
    :param hline: A function to quickly draw a horizontal line on the display.
                  This should take at least an x, y, and width parameter and
                  any number of optional color or other parameters.
    :param vline: A function to quickly draw a vertical line on the display.
                  This should take at least an x, y, and height paraemter and
                  any number of optional color or other parameters.
    :param fill_rect: A function to quickly draw a solid rectangle with four
                  input parameters: x,y, width, and height. Any number of other
                  parameters for color or screen specific data.
    :param text: A function to quickly place text on the screen. The inputs include:
                  x, y data(top left as starting point).
    :param font: An optional input to augment the default text method with a new font.
                  The input should be a properly formatted dict.
    """

    def __init__(
        self,
        width,
        height,
        pixel,
        hline=None,
        vline=None,
        fill_rect=None,
        text=None,
        font=None,
    ):
        self.width = width
        self.height = height
        self._pixel = pixel
        # Default to slow horizontal & vertical line implementations if no
        # faster versions are provided.
        if hline is None:
            self.hline = self._slow_hline
        else:
            self.hline = hline
        if vline is None:
            self.vline = self._slow_vline
        else:
            self.vline = vline
        if fill_rect is None:
            self.fill_rect = self._fill_rect
        else:
            self.fill_rect = fill_rect
        if text is None:
            self.text = self._print_text
            # if no supplied font set to std
            if font is None:
                self.font_family = MontserratBlack

                self.font = self.font_family._font
                self.set_text_background()
            else:
                self.font = font
                if not isinstance(self.font, dict):
                    raise ValueError("Font definitions must be contained in a dictionary object.")
                del self.set_text_background

        else:
            self.text = text

    def pixel(self, x0, y0, *args, **kwargs):
        """A function to pass through in input pixel functionality."""
        # This was added to mainitatn the abstraction between gfx and the dislay library
        self._pixel(x0, y0, *args, **kwargs)

    def _slow_hline(self, x0, y0, width, *args, **kwargs):
        """Slow implementation of a horizontal line using pixel drawing.
        This is used as the default horizontal line if no faster override
        is provided."""
        if y0 < 0 or y0 > self.height or x0 < -width or x0 > self.width:
            return
        for i in range(width):
            self._pixel(x0 + i, y0, *args, **kwargs)

    def _slow_vline(self, x0, y0, height, *args, **kwargs):
        """Slow implementation of a vertical line using pixel drawing.
        This is used as the default vertical line if no faster override
        is provided."""
        if y0 < -height or y0 > self.height or x0 < 0 or x0 > self.width:
            return
        for i in range(height):
            self._pixel(x0, y0 + i, *args, **kwargs)

    def rect(self, x0, y0, width, height, *args, **kwargs):
        """Rectangle drawing function.  Will draw a single pixel wide rectangle
        starting in the upper left x0, y0 position and width, height pixels in
        size."""
        if y0 < -height or y0 > self.height or x0 < -width or x0 > self.width:
            return
        self.hline(x0, y0, width, *args, **kwargs)
        self.hline(x0, y0 + height - 1, width, *args, **kwargs)
        self.vline(x0, y0, height, *args, **kwargs)
        self.vline(x0 + width - 1, y0, height, *args, **kwargs)

    def _fill_rect(self, x0, y0, width, height, *args, **kwargs):
        """Filled rectangle drawing function.  Will draw a single pixel wide
        rectangle starting in the upper left x0, y0 position and width, height
        pixels in size."""
        if y0 < -height or y0 > self.height or x0 < -width or x0 > self.width:
            return
        for i in range(x0, x0 + width):
            self.vline(i, y0, height, *args, **kwargs)

    def line(self, x0, y0, x1, y1, *args, **kwargs):
        """Line drawing function.  Will draw a single pixel wide line starting at
        x0, y0 and ending at x1, y1."""
        steep = abs(y1 - y0) > abs(x1 - x0)
        if steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
        dx = x1 - x0
        dy = abs(y1 - y0)
        err = dx // 2
        ystep = 0
        if y0 < y1:
            ystep = 1
        else:
            ystep = -1
        while x0 <= x1:
            if steep:
                self._pixel(y0, x0, *args, **kwargs)
            else:
                self._pixel(x0, y0, *args, **kwargs)
            err -= dy
            if err < 0:
                y0 += ystep
                err += dx
            x0 += 1

    def circle(self, x0, y0, radius, *args, **kwargs):
        """Circle drawing function.  Will draw a single pixel wide circle with
        center at x0, y0 and the specified radius."""
        f = 1 - radius
        ddF_x = 1
        ddF_y = -2 * radius
        x = 0
        y = radius
        self._pixel(x0, y0 + radius, *args, **kwargs)  # bottom
        self._pixel(x0, y0 - radius, *args, **kwargs)  # top
        self._pixel(x0 + radius, y0, *args, **kwargs)  # right
        self._pixel(x0 - radius, y0, *args, **kwargs)  # left
        while x < y:
            if f >= 0:
                y -= 1
                ddF_y += 2
                f += ddF_y
            x += 1
            ddF_x += 2
            f += ddF_x
            # angle notations are based on the unit circle and in diection of being drawn
            self._pixel(x0 + x, y0 + y, *args, **kwargs)  # 270 to 315
            self._pixel(x0 - x, y0 + y, *args, **kwargs)  # 270 to 255
            self._pixel(x0 + x, y0 - y, *args, **kwargs)  # 90 to 45
            self._pixel(x0 - x, y0 - y, *args, **kwargs)  # 90 to 135
            self._pixel(x0 + y, y0 + x, *args, **kwargs)  # 0 to 315
            self._pixel(x0 - y, y0 + x, *args, **kwargs)  # 180 to 225
            self._pixel(x0 + y, y0 - x, *args, **kwargs)  # 0 to 45
            self._pixel(x0 - y, y0 - x, *args, **kwargs)  # 180 to 135

    def fill_circle(self, x0, y0, radius, *args, **kwargs):
        """Filled circle drawing function.  Will draw a filled circle with
        center at x0, y0 and the specified radius."""
        self.vline(x0, y0 - radius, 2 * radius + 1, *args, **kwargs)
        f = 1 - radius
        ddF_x = 1
        ddF_y = -2 * radius
        x = 0
        y = radius
        while x < y:
            if f >= 0:
                y -= 1
                ddF_y += 2
                f += ddF_y
            x += 1
            ddF_x += 2
            f += ddF_x
            self.vline(x0 + x, y0 - y, 2 * y + 1, *args, **kwargs)
            self.vline(x0 + y, y0 - x, 2 * x + 1, *args, **kwargs)
            self.vline(x0 - x, y0 - y, 2 * y + 1, *args, **kwargs)
            self.vline(x0 - y, y0 - x, 2 * x + 1, *args, **kwargs)

    def triangle(self, x0, y0, x1, y1, x2, y2, *args, **kwargs):
        """Triangle drawing function.  Will draw a single pixel wide triangle
        around the points (x0, y0), (x1, y1), and (x2, y2)."""
        self.line(x0, y0, x1, y1, *args, **kwargs)
        self.line(x1, y1, x2, y2, *args, **kwargs)
        self.line(x2, y2, x0, y0, *args, **kwargs)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, *args, **kwargs):
        """Filled triangle drawing function.  Will draw a filled triangle around
        the points (x0, y0), (x1, y1), and (x2, y2)."""
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0
        if y1 > y2:
            y2, y1 = y1, y2
            x2, x1 = x1, x2
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0
        a = 0
        b = 0
        last = 0
        if y0 == y2:
            a = x0
            b = x0
            if x1 < a:
                a = x1
            elif x1 > b:
                b = x1
            if x2 < a:
                a = x2
            elif x2 > b:
                b = x2
            self.hline(a, y0, b - a + 1, *args, **kwargs)
            return
        dx01 = x1 - x0
        dy01 = y1 - y0
        dx02 = x2 - x0
        dy02 = y2 - y0
        dx12 = x2 - x1
        dy12 = y2 - y1
        if dy01 == 0:
            dy01 = 1
        if dy02 == 0:
            dy02 = 1
        if dy12 == 0:
            dy12 = 1
        sa = 0
        sb = 0
        y = y0
        if y0 == y1:
            last = y1 - 1
        else:
            last = y1
        while y <= last:
            a = x0 + sa // dy01
            b = x0 + sb // dy02
            sa += dx01
            sb += dx02
            if a > b:
                a, b = b, a
            self.hline(a, y, b - a + 1, *args, **kwargs)
            y += 1
        sa = dx12 * (y - y1)
        sb = dx02 * (y - y0)
        while y <= y2:
            a = x1 + sa // dy12
            b = x0 + sb // dy02
            sa += dx12
            sb += dx02
            if a > b:
                a, b = b, a
            self.hline(a, y, b - a + 1, *args, **kwargs)
            y += 1

    def round_rect(self, x0, y0, width, height, radius, *args, **kwargs):
        """Rectangle with rounded corners drawing function.
        This works like a regular rect though! if radius = 0
        Will draw the outline of a rectangle with rounded corners with (x0,y0) at the top left
        """
        # shift to correct for start point location
        x0 += radius
        y0 += radius

        # ensure that the radius will only ever half of the shortest side or less
        radius = int(min(radius, width / 2, height / 2))

        if radius:
            f = 1 - radius
            ddF_x = 1
            ddF_y = -2 * radius
            x = 0
            y = radius
            self.vline(x0 - radius, y0, height - 2 * radius + 1, *args, **kwargs)  # left
            self.vline(x0 + width - radius, y0, height - 2 * radius + 1, *args, **kwargs)  # right
            self.hline(
                x0, y0 + height - radius + 1, width - 2 * radius + 1, *args, **kwargs
            )  # bottom
            self.hline(x0, y0 - radius, width - 2 * radius + 1, *args, **kwargs)  # top
            while x < y:
                if f >= 0:
                    y -= 1
                    ddF_y += 2
                    f += ddF_y
                x += 1
                ddF_x += 2
                f += ddF_x
                # angle notations are based on the unit circle and in diection of being drawn

                # top left
                self._pixel(x0 - y, y0 - x, *args, **kwargs)  # 180 to 135
                self._pixel(x0 - x, y0 - y, *args, **kwargs)  # 90 to 135
                # top right
                self._pixel(x0 + x + width - 2 * radius, y0 - y, *args, **kwargs)  # 90 to 45
                self._pixel(x0 + y + width - 2 * radius, y0 - x, *args, **kwargs)  # 0 to 45
                # bottom right
                self._pixel(
                    x0 + y + width - 2 * radius,
                    y0 + x + height - 2 * radius,
                    *args,
                    **kwargs,
                )  # 0 to 315
                self._pixel(
                    x0 + x + width - 2 * radius,
                    y0 + y + height - 2 * radius,
                    *args,
                    **kwargs,
                )  # 270 to 315
                # bottom left
                self._pixel(x0 - x, y0 + y + height - 2 * radius, *args, **kwargs)  # 270 to 255
                self._pixel(x0 - y, y0 + x + height - 2 * radius, *args, **kwargs)  # 180 to 225

    def fill_round_rect(self, x0, y0, width, height, radius, *args, **kwargs):
        """Filled circle drawing function.  Will draw a filled circle with
        center at x0, y0 and the specified radius."""
        # shift to correct for start point location
        x0 += radius
        y0 += radius

        # ensure that the radius will only ever half of the shortest side or less
        radius = int(min(radius, width / 2, height / 2))

        self.fill_rect(x0, y0 - radius, width - 2 * radius + 2, height + 2, *args, **kwargs)

        if radius:
            f = 1 - radius
            ddF_x = 1
            ddF_y = -2 * radius
            x = 0
            y = radius
            while x < y:
                if f >= 0:
                    y -= 1
                    ddF_y += 2
                    f += ddF_y
                x += 1
                ddF_x += 2
                f += ddF_x
                # part notation starts with 0 on left and 1 on right, and direction is noted
                # top left
                self.vline(
                    x0 - y, y0 - x, 2 * x + 1 + height - 2 * radius, *args, **kwargs
                )  # 0 to .25
                self.vline(
                    x0 - x, y0 - y, 2 * y + 1 + height - 2 * radius, *args, **kwargs
                )  # .5 to .25
                # top right
                self.vline(
                    x0 + x + width - 2 * radius,
                    y0 - y,
                    2 * y + 1 + height - 2 * radius,
                    *args,
                    **kwargs,
                )  # .5 to .75
                self.vline(
                    x0 + y + width - 2 * radius,
                    y0 - x,
                    2 * x + 1 + height - 2 * radius,
                    *args,
                    **kwargs,
                )  # 1 to .75
                
                
    def _print_text(self, framebuf, x0, y0, string, size, *args, **kwargs):
        """Optimized text rendering for 1bpp and 2bpp framebuffers with text wrapping"""
        # Display parameters (adjust to your display)
        DISPLAY_WIDTH = 800
        DISPLAY_HEIGHT = 600
        
        # Default to 2bpp if not specified
        bpp = kwargs.get('bpp', 2)
        
        wrap_text = kwargs.get('text_wrap', False)
        BYTES_PER_ROW = (DISPLAY_WIDTH * bpp) // 8
        
        # Color handling
        color = args[0] if args else (1 if bpp == 1 else 3)  # Default to white
        if bpp == 1:
            color = 1 if color else 0  # Only 0 or 1 for 1bpp
        else:
            color = min(max(color, 0), 3)  # Clamp to 0-3 for 2bpp
        
        x = int(x0)
        y = int(y0)
        line_height = 0  # Will be set when we draw the first character
        
        for chunk in string.split("__"):
            try:
                # Try to draw as special character first
                char_data, ch_h, ch_w = self.font_family.get_ch(chunk)
                line_height = max(line_height, ch_h * size)
                
                if wrap_text==True:
                    # Check if this would go beyond display width
                    if x + ch_w * size > DISPLAY_WIDTH:
                        x = 0  # Reset to initial x position
                        y += line_height  # Move to next line
                        line_height = ch_h * size  # Reset line height for new line
                
                if bpp == 1:
                    GFX._draw_char_1bpp(
                        framebuf, x, y, char_data, ch_w, ch_h,
                        size, color, BYTES_PER_ROW,
                        DISPLAY_WIDTH, DISPLAY_HEIGHT
                    )
                else:
                    GFX._draw_char_2bpp(
                        framebuf, x, y, char_data, ch_w, ch_h,
                        size, color, BYTES_PER_ROW,
                        DISPLAY_WIDTH, DISPLAY_HEIGHT
                    )
                x += ch_w * size
            except (ValueError, TypeError):
                # Fall back to character-by-character
                for char in chunk:
                    # Handle newline character
                    if char == '\n':
                        x = x0  # Reset to initial x position
                        y += line_height  # Move to next line
                        line_height = 0  # Reset line height for new line
                        continue
                        
                    try:
                        char_data, ch_h, ch_w = self.font_family.get_ch(char)
                    except (ValueError, TypeError):
                        char_data, ch_h, ch_w = self.font_family.get_ch("?")
                    
                    line_height = max(line_height, ch_h * size)
                    
                    # Check if this character would go beyond display width
                    if wrap_text==True:
                        if x + ch_w * size > DISPLAY_WIDTH:
                            x = 0  # Reset to initial x position
                            y += line_height  # Move to next line
                            line_height = ch_h * size  # Reset line height for new line
                    
                    if bpp == 1:
                        GFX._draw_char_1bpp(
                            framebuf, x, y, char_data, ch_w, ch_h,
                            size, color, BYTES_PER_ROW,
                            DISPLAY_WIDTH, DISPLAY_HEIGHT
                        )
                    else:
                        GFX._draw_char_2bpp(
                            framebuf, x, y, char_data, ch_w, ch_h,
                            size, color, BYTES_PER_ROW,
                            DISPLAY_WIDTH, DISPLAY_HEIGHT
                        )
                    x += ch_w * size
        return [x,y], line_height

    @micropython.viper
    def _draw_char_1bpp(framebuf: ptr8, x0: int, y0: int, char_data: ptr8,
                       width: int, height: int, size: int,
                       color: int, bytes_per_row: int,
                       display_width: int, display_height: int):
        """Optimized 1bpp character drawing"""
        shift_mask = ptr8(b'\x80\x40\x20\x10\x08\x04\x02\x01')  # Bit masks
        color_bit = 0x01 if color else 0x00
        
        for row in range(height):
            row_bytes = (width + 7) // 8
            row_offset = row * row_bytes
            
            for col in range(width):
                byte_idx = col // 8
                bit_mask = int(shift_mask[col % 8])
                pixel_on = int(char_data[row_offset + byte_idx]) & bit_mask
                
                if pixel_on:
                    x_base = x0 + col * size
                    y_base = y0 + row * size
                    
                    # Clip to display bounds
                    if x_base >= display_width or y_base >= display_height:
                        continue
                    if x_base < 0 or y_base < 0:
                        continue
                    
                    # Handle scaling
                    for sy in range(size):
                        y_pos = y_base + sy
                        if y_pos >= display_height:
                            break
                        for sx in range(size):
                            x_pos = x_base + sx
                            if x_pos < display_width and x_pos >= 0:
                                # Calculate framebuffer position (1bpp specific)
                                fb_idx = y_pos * bytes_per_row + (x_pos // 8)
                                shift =(x_pos % 8)
                                
                                # Set or clear the bit
                                if color:
                                    framebuf[fb_idx] |= (1 << shift)
                                else:
                                    framebuf[fb_idx] &= ~(1 << shift)

    @micropython.viper
    def _draw_char_2bpp(framebuf: ptr8, x0: int, y0: int, char_data: ptr8,
                       width: int, height: int, size: int,
                       color: int, bytes_per_row: int,
                       display_width: int, display_height: int):
        """Optimized 2bpp character drawing"""
        shift_mask = ptr8(b'\x80\x40\x20\x10\x08\x04\x02\x01')  # Bit masks
        
        for row in range(height):
            row_bytes = (width + 7) // 8
            row_offset = row * row_bytes
            
            for col in range(width):
                byte_idx = col // 8
                bit_mask = int(shift_mask[col % 8])
                pixel_on = int(char_data[row_offset + byte_idx]) & bit_mask
                
                if pixel_on:
                    x_base = x0 + col * size
                    y_base = y0 + row * size
                    
                    # Clip to display bounds
                    if x_base >= display_width or y_base >= display_height:
                        continue
                    if x_base < 0 or y_base < 0:
                        continue
                    
                    # Handle scaling
                    for sy in range(size):
                        y_pos = y_base + sy
                        if y_pos >= display_height:
                            break
                        for sx in range(size):
                            x_pos = x_base + sx
                            if x_pos < display_width and x_pos >= 0:
                                # Calculate framebuffer position (2bpp specific)
                                fb_idx = y_pos * bytes_per_row + (x_pos // 4)
                                shift =((x_pos % 4) * 2)
                                
                                # Clear existing bits and set new color
                                framebuf[fb_idx] = (framebuf[fb_idx] & ~(0x03 << shift)) | (color << shift)
        




    def set_text_background(self, *args, **kwargs):
        """A function to change the background color of text, input any and all color params.
        Run without any inputs to return to "clear" background
        """
        self.text_bkgnd_args = args
        self.text_bkgnd_kwargs = kwargs