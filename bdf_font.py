# The MIT License (MIT)
#
# Copyright (c) 2019 Scott Shawcroft for Adafruit Industries LLC
# Copyright (c) 2020 Thorsten von Eicken, adaptations for micropython-inkplate6
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# import gc

import time
try:
    from micropython import const
except ImportError:

    def const(x):
        x


# from fontio import Glyph
# from .glyph_cache import GlyphCache

# Glyph: represented as a bytearray. The first few bytes are used for infomartional values,
# the remainder form the bitmap, which is stored in HMSB format (horizontal, then down, most
# significant bit first).
# The following constants are the offsets into the bytearray:
GL_WIDTH = const(0)  # width: the width of the glyph's bitmap
GL_HEIGHT = const(1)  # height: the height of the glyph's bitmap
GL_DX = const(2)  # dx: x adjustment to the bitmap's position (offset by 128 to allow negative)
GL_DY = const(3)  # dy: y adjustment to the bitmap's position (offset by 128 to allow negative)
GL_SX = const(4)  # shift_x: the x difference to the next glyph
GL_SY = const(5)  # shift_y: the y difference to the next glyph
GL_BM = const(6)  # bitmap: the first byte of the bitmap


# Font: holds the glyphs forming a font.
class Font:
    def __init__(self):
        self.start = None  # first character in glyph array
        self.ascii = []  # array of ascii (0..127) glyphs, starting with self.start
        self.unicode = {}  # glyphs beyond the 0..127 ascii range, indexed by code point

    def __setitem__(self, code_point, glyph):
        assert code_point >= 0
        if code_point > 127:
            # beyond ascii: add to unicode map
            self.unicode[code_point] = glyph
        elif self.start is None:
            self.start = code_point
            self.ascii = [glyph]
        elif code_point >= self.start:
            # replace or append
            code_point -= self.start
            if code_point >= len(self.ascii):
                # append, possibly extend array
                while len(self.ascii) < code_point:
                    self.ascii.append(None)
                self.ascii.append(glyph)
            else:
                self.ascii[code_point] = glyph
        elif code_point == self.start - 1:
            self.ascii.insert(0, glyph)
            self.start -= 1
        else:
            self.ascii = [None] * (self.start - code_point) + self.ascii
            self.ascii[0] = glyph
            self.start = code_point

    def __getitem__(self, code_point):
        try:
            if code_point > 127:
                return self.unicode[code_point]
            if self.start is None:
                return None
            code_point -= self.start
            if code_point >= 0:
                return self.ascii[code_point]
            return None
        except (IndexError, KeyError):
            return None

    def __contains__(self, code_point):
        if code_point > 127:
            return code_point in self.unicode
        if self.start is None:
            return False
        code_point -= self.start
        return code_point >= 0 and code_point < len(self.ascii) and self.ascii[code_point]

    @micropython.viper
    def draw_glyph(self, setpixel, glyph, x: int, y: int, color: int):
        gl = ptr8(glyph)
        ix = GL_BM
        w = int(gl[GL_WIDTH])
        y -= gl[GL_HEIGHT]
        for dy in range(int(gl[GL_HEIGHT])):
            for dx in range(w):
                bit = dx & 7
                pixel = gl[ix] >> (7 - bit) & 1
                if pixel:
                    setpixel(x + dx, y + dy, color)
                if bit == 7 or dx == w - 1:
                    ix += 1

    # text draws the string starting at coordinates x;y, where y is the baseline of the text.
    # It returns the rendered text width.
    def text(self, setpixel, string, x0, y, color):
        self.load_glyphs(string)
        x = x0
        for ch in string:
            gl = self[ord(ch)]
            if gl is None:
                gl = self[0]
                if gl is None:
                    continue
            dy = gl[GL_DY] - 128
            dx = gl[GL_DX] - 128
            self.draw_glyph(setpixel, gl, x + dx, y - dy, color)
            x += gl[GL_SX]
            y += gl[GL_SY] # ever used???
        return x - x0

    # @staticmethod
    # def make_glyph(w, h, dx, dy, sx, sy):
    #    stride = (w + 7) // 8
    #    g = bytearray(GL_BM + h * stride)
    #    g[0] = w
    #    g[1] = h
    #    g[2] = dx
    #    g[3] = dy
    #    g[4] = sx
    #    g[5] = sy
    #    return g


class BDFFont(Font):
    """Loads glyphs from a BDF file in the given bitmap_class."""

    def __init__(self, filepath):
        self.file = open(filepath, "r")
        super().__init__()
        self.name = filepath.split("/")[-1]
        if self.name.endswith(".bdf"):
            self.name = self.name[:-5]
        line = self.file.readline()
        if not line or not line.startswith("STARTFONT 2.1"):
            raise ValueError("Unsupported file version")
        self.point_size = None
        self.x_resolution = None
        self.y_resolution = None

    # def get_bounding_box(self):
    #    """Return the maximum glyph size as a 4-tuple of: width, height, x_offset, y_offset"""
    #    self.file.seek(0)
    #    while True:
    #        line = self.file.readline()
    #        line = str(line, "utf-8")
    #        if not line:
    #            break
    #
    #        if line.startswith("FONTBOUNDINGBOX "):
    #            _, x, y, x_offset, y_offset = line.split()
    #            return (int(x), int(y), int(x_offset), int(y_offset))
    #    return None

    def load_glyphs(self, code_points):
        t0 = time.ticks_ms()
        # figure out the set of code_points to actually load
        if isinstance(code_points, int):
            remaining = set()
            remaining.add(code_points)
        elif isinstance(code_points, str):
            remaining = set(ord(c) for c in code_points)
        elif isinstance(code_points, set):
            remaining = code_points
        else:
            remaining = set(code_points)
        for code_point in remaining:
            if code_point in self:
                remaining.remove(code_point)
        if not remaining:
            return

        desired_character = False  # flag to indicate that we're reading char we want
        in_char = False # flag to indicate that we're reading a character
        bounds = shift = bitmap = code_point = None

        self.file.seek(0)
        while True:
            line = self.file.readline()
            if not line:
                break
            if not in_char:
                if line.startswith("SIZE"):
                    _, self.point_size, self.x_resolution, self.y_resolution = line.split()
                elif line.startswith("ENCODING"):
                    _, code_point = line.split()
                    code_point = int(code_point)
                    if code_point in remaining:
                        desired_character = True
                        bounds = shift = bitmap = None
                    in_char = True
                    #print("BDF: found %d," % code_point, "desired" if desired_character else "--")
            elif line.startswith("ENDCHAR"):
                if desired_character:
                    if not (bounds and shift and bitmap):
                        raise ValueError("Insufficient info for code point %s" % code_point)
                    # gc.collect() # GC is a good idea, but takes a long time with PSRAM
                    try:
                        self[code_point] = bytes(bounds + shift + bitmap)
                    except ValueError as e:
                        print(e, bounds, shift, bitmap)
                    remaining.remove(code_point)
                    if not remaining:
                        break
                desired_character = False
                in_char = False
            elif desired_character:
                if line.startswith("BBX"):
                    _, width, height, x_offset, y_offset = line.split()
                    width = int(width)
                    height = int(height)
                    bounds = [width, height, 128+int(x_offset), 128+int(y_offset)]
                    stride = (width + 7) // 8
                    bitmap = [0] * (stride * height)
                elif line.startswith("BITMAP"):
                    current_y = 0
                elif line.startswith("DWIDTH"):
                    _, shift_x, shift_y = line.split()
                    shift = [int(shift_x), int(shift_y)]
                elif not line.startswith("SWIDTH"):
                    bits = int(line.strip(), 16)
                    ix = current_y * stride
                    for i in range(stride):
                        bitmap[ix] = (bits >> ((stride - i - 1) * 8)) & 0xFF
                        ix += 1
                    current_y += 1

        td = time.ticks_diff(time.ticks_ms(), t0)
        if td > 1000 or remaining:
            print("BDF %s took %dms, remaining:" % (self.name, td), remaining)


if __name__ == "__main__":
    import time
    from machine import I2C, Pin
    from inkplate import Inkplate, InkplateMono

    Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))
    # ipg = InkplateGS2()
    ipm = InkplateMono()
    # ipp = InkplatePartial(ipm)
    f = BDFFont("luRS24.bdf")

    ipm.clear()
    ipm.fill_rect(0, 300, 799, 599, 1)

    x = 100
    y = 100
    ipm.line(0, y, 799, y, 1)
    ipm.line(x, 0, x, 300, 1)
    w = f.text(ipm.pixel, "Hello World!", x, y, 1)
    ipm.line(x+w, 0, x+w, y+10, 1)
    ipm.display()

    f.text(ipm.pixel, "Hello on the dark side!", 100, 400, 0)
    ipm.display()

    y += 100
    w = f.text(ipm.pixel, "Special chars: ", x, y, 1)
    ipm.display()
    x += w
    f.text(ipm.pixel, "fgj@#|{}mmiill", x, y, 1)
    ipm.line(0, y, 799, y, 1)
    ipm.display()
    y += 50
    f.text(ipm.pixel, "àé∄2÷4çµ100°F1⁄16©", x, y, 1)
    ipm.line(0, y, 799, y, 1)
    ipm.display()

    y = 500
    f.text(ipm.pixel, "0123456789", 100, y, 0)
    f.text(ipm.pixel, "0000000000", 100, y+30, 0)

    ipm.display()

    print("DONE")
