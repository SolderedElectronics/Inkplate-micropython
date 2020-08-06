# Copyright © 2020 by Thorsten von Eicken.
#
# u8g2 fonts from https://github.com/olikraus/u8g2
#
# The font format consists of a font header followed by compressed glyphs.

U8_CNT = const(0)  # glyph count
U8_MODE = const(1)  # mode: 0: proportional, 1: common height, 2: monospace, 3: mult. of 8
U8_BP0 = const(2)  # bits_per_0: number of bits used to encode unset-pixel run-length
U8_BP1 = const(3)  # bits_per_1: number of bits used to encode set-pixel run-length
U8_BPCW = const(4)  # bits_per_char_width: number of bits used to encode character width
U8_BPCH = const(5)  # bits per char heigh
U8_BPCX = const(6)  # bits per char x offset
U8_BPCY = const(7)  # bits per char y offset
U8_BPCD = const(8)  # bits per char x delta to next char
U8_MAXW = const(9)  # max char width
U8_MAXH = const(10)  # max char height
U8_XO = const(11)
U8_YO = const(12)
U8_AA = const(13)  # height of A ascend
U8_DG = const(14)  # height of g descend
U8_AP = const(15)  # height of ( ascend
U8_DP = const(16)  # height of ) descent
U8_IXA = const(17)  # 2 byte offset from end of header (pos 23) to start of A
U8_IXa = const(19)  # 2 byte offset from end of header (pos 23) to start of a
U8_IXU = const(21)  # 2 byte offset from end of header (pos 23) to unicode table
U8_GLYPHS = const(23)  # first glyph

# Glyph format:
# 0.	1/2 Byte(s)	Unicode of character/glyph
# 1. (+1)	1 Byte	jump offset to next glyph
# bitcntW	glyph bitmap width (variable width)
# bitcntH	glyph bitmap height (variable width)
# bitcntX	glyph bitmap x offset (variable width)
# bitcntY	glyph bitmap y offset (variable width)
# bitcntD	character pitch (variable width)
# n Bytes	Bitmap (horizontal, RLE)

try:
    from micropython import const
    import micropython
except ImportError:

    def const(x):
        return x

    ptr8 = const

    class micropython:
        def viper(x):
            return x


# Font reads a full u8g2 font from a file in compressed format and renders glyphs from the
# compressed format as-is.
class Font:
    def __init__(self, filepath, setpixel=None):
        self.name = filepath.split("/")[-1]
        if self.name.endswith(".u8f"):
            self.name = self.name[:-4]
        self.data = open(filepath, "rb").read()
        self.setpixel = setpixel

    # find_glyph returns the index into the fond data array where the glyph with the
    # requested code_point can be found. The returned index points to the "bitcntW" field.
    #@micropython.viper
    def find_glyph(self, code_point: int) -> int:
        #data = ptr8(self.data)
        #ix = int(23)
        data = self.data
        ix = 23
        if code_point < 0x100:
            # "ascii" portion, first use offsets
            if code_point >= 97:  # after a
                ix += data[U8_IXa] << 8 | data[U8_IXa + 1]
            elif code_point >= 65:  # after A
                ix += data[U8_IXA] << 8 | data[U8_IXA + 1]
            # linear search
            while code_point != data[ix]:
                off = data[ix + 1]
                if off == 0:
                    return None
                ix += off
            return ix + 2
        else:
            # "unicode" portion, use unicode jump table
            ix += data[U8_IXU] << 8 | data[U8_IXU + 1]
            glyphs = int(ix)
            while True:
                glyphs += data[ix] << 8 | data[ix + 1]  # where this block starts
                cp = data[ix + 2] << 8 | data[ix + 3]  # highest code point in this block
                if code_point <= cp:
                    break
                ix += 4
                if ix > int(len(self.data)): return None
            # linear search
            ix = glyphs
            cp = data[ix] << 8 | data[ix + 1]
            while code_point != cp:
                if cp == 0:
                    return None
                ix += data[ix + 2]
                cp = data[ix] << 8 | data[ix + 1]
            return ix + 3

    # init_bitfield initializes for get_bitfield and count_ones to start reading at index ix
    def init_bitfield(self, ix):
        self.bf_left = 0
        self.bf_data = 0
        self.bf_glix = ix

    # get_bitfield reads the next bit-field of specified width bits
    def get_bitfield(self, width):
        bf_data = self.bf_data
        bf_left = self.bf_left
        if bf_left < width:
            bf_data |= self.data[self.bf_glix] << bf_left
            bf_left += 8
            self.bf_glix += 1
        # print(f"bitfield: left={bf_left} w={width} data={bf_data:x}", end='')
        self.bf_left = bf_left - width
        ret = bf_data & ((1 << width) - 1)
        self.bf_data = bf_data >> width
        # print(f" -> {ret}")
        return ret

    # draw_glyph draws the glyph corresponding to code_point at position x,y, where y is the
    # baseline. It returns the delta-x to the next glyph.
    def draw_glyph(self, setpixel, code_point, x, y, color):
        gl_ix = self.find_glyph(code_point)
        if gl_ix is None:
            return None
        # extract glyph header info
        self.init_bitfield(gl_ix)
        w = self.get_bitfield(self.data[U8_BPCW])
        h = self.get_bitfield(self.data[U8_BPCH])
        x += self.get_bitfield(self.data[U8_BPCX]) - (1 << (self.data[U8_BPCX] - 1))
        y -= h + self.get_bitfield(self.data[U8_BPCY]) - (1 << (self.data[U8_BPCY] - 1))
        cd = self.get_bitfield(self.data[U8_BPCD]) - (1 << (self.data[U8_BPCD] - 1))
        if w == 0:
            return cd
        # draw runlengths
        cur_x = 0
        end_y = y + h
        # print(f"y={y} h={h} w={w} end_y={end_y}")
        # consume runs of 0's and 1's until we reach the bottom of the glyph
        while y < end_y:
            # print(f"bf_data={self.bf_data} left={self.bf_left} "
            #    "next=", ['%02x' % i for i in self.data[self.bf_glix:self.bf_glix+4]],
            #    f"BP0={self.data[U8_BP0]} BP1={self.data[U8_BP1]}")
            zeros = self.get_bitfield(self.data[U8_BP0])
            ones = self.get_bitfield(self.data[U8_BP1])
            # repeat the run until we read a 0 bit
            while True:
                # print(f"Runs: {zeros}x0 {ones}x1 y={y} cur_x={cur_x}")
                # print(f"x={x+cur_x} y={y} zeros={zeros} ones={ones} repeats={repeats}")
                # skip the zeros (transparent)
                z = zeros
                while z >= w - cur_x:
                    z -= w - cur_x
                    cur_x = 0
                    y += 1
                cur_x += z
                # draw the ones
                o = ones
                while o > 0:
                    setpixel(x + cur_x, y, color)
                    cur_x += 1
                    if cur_x == w:
                        cur_x = 0
                        y += 1
                    o -= 1
                # read next bit and repeat if it's a one
                if self.bf_left == 0:
                    self.bf_data = self.data[self.bf_glix]
                    self.bf_left = 8
                    self.bf_glix += 1
                bit = self.bf_data & 1
                self.bf_data >>= 1
                self.bf_left -= 1
                if bit == 0:
                    break

        return cd

    # text draws the string starting at coordinates x;y, where y is the baseline of the text.
    # It returns the rendered text width.
    def text(self, string, x0, y, color, setpixel=None):
        if setpixel is None:
            setpixel = self.setpixel
        x = x0
        for ch in string:
            cd = self.draw_glyph(setpixel, ord(ch), x, y, color)
            if cd is None:
                print("Ooops, char %d not found!" % ord(ch))
            else:
                x += cd
        return x - x0


if __name__ == "__main__":
    from machine import I2C, Pin
    from inkplate import Inkplate, InkplateMono

    Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))
    # ipg = InkplateGS2()
    ipm = InkplateMono()
    # ipp = InkplatePartial(ipm)
    f = Font("luRS24_te.u8f", ipm.pixel)

    ipm.clear()
    ipm.fill_rect(0, 300, 799, 599, 1)

    x = 100
    y = 100
    ipm.line(0, y, 799, y, 1)
    ipm.line(x, 0, x, 300, 1)
    w = f.text("Hello World!", x, y, 1)
    ipm.line(x + w, 0, x + w, y + 10, 1)
    ipm.display()

    f.text("Hello on the dark side!", 100, 400, 0)
    ipm.display()

    y += 100
    w = f.text("Special chars: ", x, y, 1)
    ipm.display()
    x += w
    f.text("fgj@#|{}mmiill", x, y, 1)
    ipm.line(0, y, 799, y, 1)
    ipm.display()
    y += 50
    f.text("àé∄2÷4çµ100°F1⁄16©", x, y, 1)
    ipm.line(0, y, 799, y, 1)
    ipm.display()

    y = 500
    f.text("0123456789", 100, y, 0)
    f.text("0000000000", 100, y + 30, 0)

    ipm.display()

    print("DONE")
