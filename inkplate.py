# Copyright © 2020 by Thorsten von Eicken.
import time
import micropython
import framebuf
from machine import Pin
from uarray import array
from mcp23017 import MCP23017
from micropython import const

TPS65186_addr = const(0x48)  # I2C address

# ESP32 GPIO set and clear registers to twiddle 32 gpio bits at once
# from esp-idf:
# define DR_REG_GPIO_BASE           0x3ff44000
# define GPIO_OUT_W1TS_REG          (DR_REG_GPIO_BASE + 0x0008)
# define GPIO_OUT_W1TC_REG          (DR_REG_GPIO_BASE + 0x000c)
ESP32_GPIO = const(0x3FF44000)  # ESP32 GPIO base
# register offsets from ESP32_GPIO
W1TS0 = const(2)  # offset for "write one to set" register for gpios 0..31
W1TC0 = const(3)  # offset for "write one to clear" register for gpios 0..31
W1TS1 = const(5)  # offset for "write one to set" register for gpios 32..39
W1TC1 = const(6)  # offset for "write one to clear" register for gpios 32..39
# bit masks in W1TS/W1TC registers
EPD_DATA = const(0x0E8C0030)  # EPD_D0..EPD_D7
EPD_CL = const(0x00000001)  # in W1Tx0
EPD_LE = const(0x00000004)  # in W1Tx0
EPD_CKV = const(0x00000001)  # in W1Tx1
EPD_SPH = const(0x00000002)  # in W1Tx1

# Raw display constants
D_ROWS = const(600)
D_COLS = const(800)

# Inkplate provides access to the pins of the Inkplate 6 as well as to low-level display
# functions.
class Inkplate:
    @classmethod
    def init(cls, i2c):
        cls._i2c = i2c
        cls._mcp23017 = MCP23017(i2c)
        # Display control lines
        cls.EPD_CL = Pin(0, Pin.OUT, value=0)
        cls.EPD_LE = Pin(2, Pin.OUT, value=0)
        cls.EPD_CKV = Pin(32, Pin.OUT, value=0)
        cls.EPD_SPH = Pin(33, Pin.OUT, value=1)
        cls.EPD_OE = cls._mcp23017.pin(0, Pin.OUT, value=0)
        cls.EPD_GMODE = cls._mcp23017.pin(1, Pin.OUT, value=0)
        cls.EPD_SPV = cls._mcp23017.pin(2, Pin.OUT, value=1)
        # Display data lines - we only use the Pin class to init the pins
        Pin(4, Pin.OUT)
        Pin(5, Pin.OUT)
        Pin(18, Pin.OUT)
        Pin(19, Pin.OUT)
        Pin(23, Pin.OUT)
        Pin(25, Pin.OUT)
        Pin(26, Pin.OUT)
        Pin(27, Pin.OUT)
        # TPS65186 power regulator control
        cls.TPS_WAKEUP = cls._mcp23017.pin(3, Pin.OUT, value=0)
        cls.TPS_PWRUP = cls._mcp23017.pin(4, Pin.OUT, value=0)
        cls.TPS_VCOM = cls._mcp23017.pin(5, Pin.OUT, value=0)
        cls.TPS_INT = cls._mcp23017.pin(6, Pin.IN)
        cls.TPS_PWR_GOOD = cls._mcp23017.pin(7, Pin.IN)
        # Misc
        cls.GPIO0_PUP = cls._mcp23017.pin(8, Pin.OUT, value=0)
        cls.VBAT_EN = cls._mcp23017.pin(9, Pin.OUT, value=1)
        # Touch sensors
        cls.TOUCH1 = cls._mcp23017.pin(10, Pin.IN)
        cls.TOUCH2 = cls._mcp23017.pin(11, Pin.IN)
        cls.TOUCH3 = cls._mcp23017.pin(12, Pin.IN)

        cls._on = False  # whether panel is powered on or not

        if len(Inkplate.byte2gpio) == 0:
            Inkplate.gen_byte2gpio()

    # _tps65186_write writes an 8-bit value to a register
    @classmethod
    def _tps65186_write(cls, reg, v):
        cls._i2c.writeto_mem(TPS65186_addr, reg, bytes((v,)))

    # _tps65186_read reads an 8-bit value from a register
    @classmethod
    def _tps65186_read(cls, reg):
        cls._i2c.readfrom_mem(TPS65186_addr, reg, 1)[0]

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE)
    @classmethod
    def power_on(cls):
        if cls._on:
            return
        cls._on = True
        # turn on power regulator
        cls.TPS_WAKEUP(1)
        cls.TPS_PWRUP(1)
        cls.TPS_VCOM(1)
        # enable all rails
        cls._tps65186_write(0x01, 0x3F)  # ???
        time.sleep_ms(40)
        cls._tps65186_write(0x0D, 0x80)  # ???
        time.sleep_ms(2)
        cls._temperature = cls._tps65186_read(1)
        # wake-up display
        cls.EPD_GMODE(1)
        cls.EPD_OE(1)

    # power_off puts the display to sleep and cuts the power
    # TODO: also tri-state gpio pins to avoid current leakage during deep-sleep
    @classmethod
    def power_off(cls):
        if not cls._on:
            return
        cls._on = False
        # put display to sleep
        cls.EPD_GMODE(0)
        cls.EPD_OE(0)
        # turn off power regulator
        cls.TPS_PWRUP(0)
        cls.TPS_WAKEUP(0)
        cls.TPS_VCOM(0)

    # ===== Methods that are independent of pixel bit depth

    # vscan_start begins a vertical scan by toggling CKV and SPV
    # sleep_us calls are commented out 'cause MP is slow enough...
    @classmethod
    def vscan_start(cls):
        def ckv_pulse():
            cls.EPD_CKV(0)
            cls.EPD_CKV(1)

        # start a vertical scan pulse
        cls.EPD_CKV(1)  # time.sleep_us(7)
        cls.EPD_SPV(0)  # time.sleep_us(10)
        ckv_pulse()  # time.sleep_us(8)
        cls.EPD_SPV(1)  # time.sleep_us(10)
        # pulse through 3 scan lines that end up being invisible
        ckv_pulse()  # time.sleep_us(18)
        ckv_pulse()  # time.sleep_us(18)
        ckv_pulse()

    # vscan_write latches the row into the display pixels and moves to the next row
    @micropython.viper
    @staticmethod
    def vscan_write():
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        w1tc0[W1TC1 - W1TC0] = EPD_CKV  # remove gate drive
        w1ts0[0] = EPD_LE  # pulse to latch row --
        w1ts0[0] = EPD_LE  # delay a tiny bit
        w1tc0[0] = EPD_LE
        w1tc0[0] = EPD_LE  # delay a tiny bit
        w1ts0[W1TS1 - W1TS0] = EPD_CKV  # apply gate drive to next row

    # byte2gpio converts a byte of data for the screen to 32 bits of gpio0..31
    # (oh, e-radionica, why didn't you group the gpios better?!)
    byte2gpio = []

    @classmethod
    def gen_byte2gpio(cls):
        cls.byte2gpio = array("L", bytes(4 * 256))
        for b in range(256):
            cls.byte2gpio[b] = (
                (b & 0x3) << 4 | (b & 0xC) << 16 | (b & 0x10) << 19 | (b & 0xE0) << 20
            )
        # sanity check that all EPD_DATA bits got set at some point and no more
        union = 0
        for i in range(256):
            union |= cls.byte2gpio[i]
        assert union == EPD_DATA

    # fill_screen writes the same value to all bytes of the screen, it is used for cleaning
    @micropython.viper
    @staticmethod
    def fill_screen(data: int):
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        # set the data output gpios
        w1tc0[0] = EPD_DATA | EPD_CL
        w1ts0[0] = data
        vscan_write = Inkplate.vscan_write
        epd_cl = EPD_CL

        # send all rows
        for r in range(D_ROWS):
            # send first byte of row with start-row signal
            w1tc0[W1TC1 - W1TC0] = EPD_SPH
            w1ts0[0] = epd_cl
            w1tc0[0] = epd_cl
            w1ts0[W1TS1 - W1TS0] = EPD_SPH

            # send remaining bytes (we overshoot by one, which is OK)
            i = int(D_COLS >> 3)
            while i > 0:
                w1ts0[0] = epd_cl
                w1tc0[0] = epd_cl
                w1ts0[0] = epd_cl
                w1tc0[0] = epd_cl
                i -= 1

            # latch row and increment to next
            # inlined vscan_write()
            w1tc0[W1TC1 - W1TC0] = EPD_CKV  # remove gate drive
            w1ts0[0] = EPD_LE  # pulse to latch row --
            w1ts0[0] = EPD_LE  # delay a tiny bit
            w1tc0[0] = EPD_LE
            w1tc0[0] = EPD_LE  # delay a tiny bit
            w1ts0[W1TS1 - W1TS0] = EPD_CKV  # apply gate drive to next row

    # clean fills the screen with one of the four possible pixel patterns
    @classmethod
    def clean(cls, patt, rep):
        c = [0xAA, 0x55, 0x00, 0xFF][patt]
        data = Inkplate.byte2gpio[c] & ~EPD_CL
        for i in range(rep):
            cls.vscan_start()
            cls.fill_screen(data)


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)
        ip = InkplateMono
        ip._gen_luts()
        ip._wave = [ip.lut_blk, ip.lut_blk, ip.lut_blk, ip.lut_blk, ip.lut_blk, ip.lut_bw]
        InkplateShapes.__mix_me_in(InkplateMono)

    # gen_luts generates the look-up tables to convert a nibble (4 bits) of pixels to the
    # 32-bits that need to be pushed into the gpio port.
    # The LUTs used here were copied from the e-Radionica Inkplate-6-Arduino-library.
    @classmethod
    def _gen_luts(cls):
        b16 = bytes(4 * 16)  # is there a better way to init an array with 16 words???
        cls.lut_wht = array("L", b16)  # bits to ship to gpio to make pixels white
        cls.lut_blk = array("L", b16)  # bits to ship to gpio to make pixels black
        cls.lut_bw = array("L", b16)  # bits to ship to gpio to make pixels black and white
        for i in range(16):
            wht = 0
            blk = 0
            bw = 0
            # display uses 2 bits per pixel: 00=discharge, 01=black, 10=white, 11=skip
            for bit in range(4):
                wht = wht | ((2 if (i >> bit) & 1 == 0 else 3) << (2 * bit))
                blk = blk | ((1 if (i >> bit) & 1 == 1 else 3) << (2 * bit))
                bw = bw | ((1 if (i >> bit) & 1 == 1 else 2) << (2 * bit))
            cls.lut_wht[i] = Inkplate.byte2gpio[wht] | EPD_CL
            cls.lut_blk[i] = Inkplate.byte2gpio[blk] | EPD_CL
            cls.lut_bw[i] = Inkplate.byte2gpio[bw] | EPD_CL
        # print("Black: %08x, White:%08x Data:%08x" % (cls.lut_bw[0xF], cls.lut_bw[0], EPD_DATA))

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, framebuf, row: int):
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        fb = ptr8(framebuf)
        ix = int(row * (D_COLS >> 3) + 99)  # index into framebuffer
        lut = ptr32(lut_in)
        # send first byte
        data = int(fb[ix])
        ix -= 1
        w1tc0[0] = off
        w1tc0[W1TC1 - W1TC0] = EPD_SPH
        w1ts0[0] = lut[data >> 4]  # set data bits and assert clock
        # w1tc0[0] = EPD_CL  # clear clock, leaving data bits (unreliable if data also cleared)
        w1tc0[0] = off  # clear data bits as well ready for next byte
        w1ts0[W1TS1 - W1TS0] = EPD_SPH
        w1ts0[0] = lut[data & 0xF]
        # w1tc0[0] = EPD_CL
        w1tc0[0] = off
        # send the remaining bytes (792 pixels)
        for c in range(99):
            data = int(fb[ix])
            ix -= 1
            w1ts0[0] = lut[data >> 4]
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off
            w1ts0[0] = lut[data & 0xF]
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = Inkplate
        ip.power_on()

        # clean the display
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 12)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)
        ip.clean(1, 12)
        ip.clean(2, 1)
        ip.clean(0, 11)

        # the display gets written N times
        t1 = time.ticks_ms()
        n = 0
        send_row = InkplateMono._send_row
        vscan_write = ip.vscan_write
        fb = self._framebuf
        for lut in self._wave:
            ip.vscan_start()
            # write all rows
            r = D_ROWS - 1
            while r >= 0:
                send_row(lut, fb, r)
                vscan_write()
                r -= 1
            n += 1

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print(
            "Mono: clean %dms (%dms ea), draw %dms (%dms ea), total %dms"
            % (tc, tc // (4 + 22 + 24), td, td // len(self._wave), tt)
        )

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.power_off()

    # @micropython.viper
    def clear(self):
        self.fill(0)
        # fb = ptr8(self._framebuf)
        # for ix in range(D_ROWS * D_COLS // 8):
        #    fb[ix] = 0


# Inkplate display with 2 bits of gray scale (4 levels)
class InkplateGS2(framebuf.FrameBuffer):
    _wave = None

    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 4)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.GS2_HMSB)
        if not InkplateGS2._wave:
            InkplateGS2._gen_wave()

    # _gen_wave generates the waveform table. The table consists of N phases or steps during
    # each of which the entire display gets written. The array in each phase gets indexed with
    # a nibble of data and contains the 32-bits that need to be pushed into the gpio port.
    # The waveform used here was adapted from the e-Radionica Inkplate-6-Arduino-library
    # by taking colors 0 (black), 3, 5, and 7 (white) from "waveform3Bit[8][7]".
    @classmethod
    def _gen_wave(cls):
        # genlut generates the lookup table that maps a nibble (2 pixels, 4 bits) to a 32-bit
        # word to push into the GPIO port
        def genlut(op):
            return bytes([op[j] | op[i] << 2 for i in range(4) for j in range(4)])

        cls._wave = [
            genlut([0, 0, 0, 0]),  # order: blk, dk-grey, light-grey, white
            genlut([0, 0, 0, 0]),  # value: 0=dischg, 1=black, 2=white, 3=skip
            genlut([0, 1, 1, 0]),
            genlut([0, 1, 1, 0]),
            genlut([1, 2, 1, 0]),
            genlut([1, 1, 2, 0]),
            genlut([1, 2, 2, 2]),
        ]

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, framebuf, row: int):
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        fb = ptr8(framebuf)
        ix = int(row * 200 + 199)  # index into framebuffer
        lut = ptr8(lut_in)
        b2g = ptr32(Inkplate.byte2gpio)
        # send first byte
        data = int(fb[ix])
        ix -= 1
        w1tc0[0] = off
        w1tc0[W1TC1 - W1TC0] = EPD_SPH
        w1ts0[0] = b2g[lut[data >> 4] << 4 | lut[data & 0xF]] | EPD_CL  # set data bits and clock
        # w1tc0[0] = EPD_CL  # clear clock, leaving data bits (unreliable if data also cleared)
        w1tc0[0] = off  # clear data bits as well ready for next byte
        w1ts0[W1TS1 - W1TS0] = EPD_SPH
        # send the remaining bytes (792 pixels)
        for c in range(199):
            data = int(fb[ix])
            ix -= 1
            w1ts0[0] = b2g[lut[data >> 4] << 4 | lut[data & 0xF]] | EPD_CL
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = Inkplate
        ip.power_on()

        # clean the display
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 12)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)
        ip.clean(1, 12)
        ip.clean(2, 1)
        ip.clean(0, 11)

        # the display gets written N times
        t1 = time.ticks_ms()
        n = 0
        send_row = InkplateGS2._send_row
        vscan_write = ip.vscan_write
        fb = self._framebuf
        for lut in InkplateGS2._wave:
            ip.vscan_start()
            # write all rows
            r = D_ROWS - 1
            while r >= 0:
                send_row(lut, fb, r)
                vscan_write()
                r -= 1
            n += 1

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print(
            "GS2: clean %dms (%dms ea), draw %dms (%dms ea), total %dms"
            % (tc, tc // (4 + 22 + 24), td, td // len(InkplateGS2._wave), tt)
        )

        ip.clean(2, 1)  # ??
        ip.clean(3, 1)
        ip.power_off()

    # @micropython.viper
    def clear(self):
        self.fill(3)
        # fb = ptr8(self._framebuf)
        # for ix in range(int(len(self._framebuf))):
        #    fb[ix] = 0xFF


# InkplatePartial managed partial updates. It starts by making a copy of the current framebuffer
# and then when asked to draw it renders the differences between the copy and the new framebuffer
# state. The constructor needs a reference to the current/main display object (InkplateMono).
# Only InkplateMono is supported at the moment.
class InkplatePartial:
    def __init__(self, base):
        self._base = base
        self._framebuf = bytearray(len(base._framebuf))
        InkplatePartial._gen_lut_mono()

    # start makes a reference copy of the current framebuffer
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer contents
    def display(self, x=0, y=0, w=D_COLS, h=D_ROWS):
        ip = Inkplate
        ip.power_on()

        # the display gets written a couple of times
        t0 = time.ticks_ms()
        n = 0
        send_row = InkplatePartial._send_row
        skip_rows = InkplatePartial._skip_rows
        vscan_write = ip.vscan_write
        nfb = self._base._framebuf  # new framebuffer
        ofb = self._framebuf  # old framebuffer
        lut = InkplatePartial._lut_mono
        h -= 1
        for _ in range(5):
            ip.vscan_start()
            r = D_ROWS - 1
            # skip rows that supposedly have no change
            if r > y + h:
                skip_rows(r - (y + h))
                r = y + h
            # write changed rows
            while r >= y:
                send_row(lut, ofb, nfb, r)
                vscan_write()
                r -= 1
            # skip remaining rows (doesn't seem to be necessary)
            # if r > 0:
            #    skip_rows(r)
            n += 1

        t1 = time.ticks_ms()
        td = time.ticks_diff(t1, t0)
        print(
            "Partial: draw %dms (%dms/frame %dus/row) (y=%d..%d)"
            % (td, td // n, td * 1000 // n // (D_ROWS - y), y, y + h + 1)
        )

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.power_off()

    # gen_lut_mono generates a look-up tables to change the display from a nibble of old
    # pixels (4 bits = 4 pixels) to a nibble of new pixels. The LUT contains the
    # 32-bits that need to be pushed into the gpio port to effect the change.
    @classmethod
    def _gen_lut_mono(cls):
        lut = cls._lut_mono = array("L", bytes(4 * 256))
        for o in range(16):  # iterate through all old-pixels combos
            for n in range(16):  # iterate through all new-pixels combos
                bw = 0
                for bit in range(4):
                    # value to send to display: turns out that if we juxtapose the old and new
                    # bits we get the right value except for the 00 combination...
                    val = (((o >> bit) << 1) & 2) | ((n >> bit) & 1)
                    if val == 0:
                        val = 3
                    bw = bw | (val << (2 * bit))
                lut[o * 16 + n] = Inkplate.byte2gpio[bw] | EPD_CL
        # print("Black: %08x, White:%08x Data:%08x" % (cls.lut_bw[0xF], cls.lut_bw[0], EPD_DATA))

    # _skip_rows skips N rows
    @micropython.viper
    @staticmethod
    def _skip_rows(rows: int):
        if rows <= 0:
            return
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))

        # need to fill the column latches with "no-change" values (all ones)
        epd_cl = EPD_CL
        w1tc0[0] = epd_cl
        w1ts0[0] = EPD_DATA
        # send first byte of row with start-row signal
        w1tc0[W1TC1 - W1TC0] = EPD_SPH
        w1ts0[0] = epd_cl
        w1tc0[0] = epd_cl
        w1ts0[W1TS1 - W1TS0] = EPD_SPH
        # send remaining bytes
        i = int(D_COLS >> 3)
        while i > 0:
            w1ts0[0] = epd_cl
            w1tc0[0] = epd_cl
            w1ts0[0] = epd_cl
            w1tc0[0] = epd_cl
            i -= 1

        # write the same row over and over, weird thing is that we need the sleep otherwise
        # the rows we subsequently draw don't draw proper whites leaving ghosts behind - hard to
        # understand why the speed at which we "skip" rows affects rows that are drawn later...
        while rows > 0:
            Inkplate.vscan_write()
            rows -= 1
            time.sleep_us(50)

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, old_framebuf, new_framebuf, row: int):
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        ofb = ptr8(old_framebuf)
        nfb = ptr8(new_framebuf)
        ix = int(row * (D_COLS >> 3) + 99)  # index into framebuffer
        lut = ptr32(lut_in)
        # send first byte
        odata = int(ofb[ix])
        ndata = int(nfb[ix])
        ix -= 1
        w1tc0[0] = off
        w1tc0[W1TC1 - W1TC0] = EPD_SPH
        if odata == ndata:
            w1ts0[0] = off  # send all-ones: no change to any of the pixels
            w1tc0[0] = EPD_CL
            w1ts0[W1TS1 - W1TS0] = EPD_SPH
            w1ts0[0] = EPD_CL
            w1tc0[0] = off
        else:
            w1ts0[0] = lut[(odata & 0xF0) + (ndata >> 4)]
            w1tc0[0] = off  # clear data bits as well ready for next byte
            w1ts0[W1TS1 - W1TS0] = EPD_SPH
            w1ts0[0] = lut[((odata & 0xF) << 4) + (ndata & 0xF)]
            w1tc0[0] = off
        # send the remaining bytes (792 pixels)
        for c in range(99):
            odata = int(ofb[ix])
            ndata = int(nfb[ix])
            ix -= 1
            if odata == ndata:
                w1ts0[0] = off  # send all-ones: no change to any of the pixels
                w1tc0[0] = EPD_CL
                w1ts0[0] = EPD_CL
                w1tc0[0] = off
            else:
                w1ts0[0] = lut[(odata & 0xF0) + ((ndata >> 4) & 0xF)]
                w1tc0[0] = off
                w1ts0[0] = lut[((odata & 0xF) << 4) + (ndata & 0xF)]
                w1tc0[0] = off


class InkplateShapes:
    from gfx_standard_font_01 import text_dict as font

    @classmethod
    def __mix_me_in(cls, target):
        for func in dir(cls):
            if not callable(getattr(cls, func)) or func.startswith("__"):
                continue
            setattr(target, func, getattr(cls, func))
            setattr(target, "font", cls.font)

    # The following shapes are adapted from https://github.com/peterhinch/micropython-epaper
    # Copyright 2015 Peter Hinch
    #
    # Licensed under the Apache License, Version 2.0 (the "License") you may not use this
    # file except in compliance with the License.  You may obtain a copy of the License at:
    #
    #   http:#www.apache.org/licenses/LICENSE-2.0
    #
    # Unless required by applicable law or agreed to in writing, software distributed under
    # the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    # KIND, either express or implied.  See the License for the specific language governing
    # permissions and limitations under the License.
    # Code translated and developed from https://developer.mbed.org/users/dreschpe/code/EaEpaper/

    @staticmethod
    def _circle(self, x0, y0, r, color):  # Single pixel circle
        x = -r
        y = 0
        err = 2 - 2 * r
        while x <= 0:
            self.pixel(x0 - x, y0 + y, color)
            self.pixel(x0 + x, y0 + y, color)
            self.pixel(x0 + x, y0 - y, color)
            self.pixel(x0 - x, y0 - y, color)
            e2 = err
            if e2 <= y:
                y += 1
                err += y * 2 + 1
                if -x == y and e2 <= x:
                    e2 = 0
            if e2 > x:
                x += 1
                err += x * 2 + 1

    @staticmethod
    def circle(self, x0, y0, r, color, width=1):  # Draw circle
        x0, y0, r = int(x0), int(y0), int(r)
        for r in range(r, r - width, -1):
            self._circle(x0, y0, r, color)

    def fill_circle(self, x0, y0, r, color):  # Draw filled circle
        x0, y0, r = int(x0), int(y0), int(r)
        x = -r
        y = 0
        err = 2 - 2 * r
        while x <= 0:
            self.line(x0 - x, y0 - y, x0 - x, y0 + y, color)
            self.line(x0 + x, y0 - y, x0 + x, y0 + y, color)
            e2 = err
            if e2 <= y:
                y += 1
                err += y * 2 + 1
                if -x == y and e2 <= x:
                    e2 = 0
            if e2 > x:
                x += 1
                err += x * 2 + 1

    # The following shapes are adapted from https://github.com/adafruit/Adafruit_CircuitPython_GFX
    # The MIT License (MIT)
    #
    # Copyright (c) 2018 Kattni Rembor for Adafruit Industries
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

    def triangle(self, x0, y0, x1, y1, x2, y2, color):
        """Triangle drawing function.  Will draw a single pixel wide triangle
        around the points (x0, y0), (x1, y1), and (x2, y2)."""
        self.line(x0, y0, x1, y1, color)
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x0, y0, color)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, color):
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
        y = 0
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
            self.hline(a, y0, b - a + 1, color)
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
        if y1 == y2:
            last = y1
        else:
            last = y1 - 1
        for y in range(y0, last + 1):
            a = x0 + sa // dy01
            b = x0 + sb // dy02
            sa += dx01
            sb += dx02
            if a > b:
                a, b = b, a
            self.hline(a, y, b - a + 1, color)
        sa = dx12 * (y - y1)
        sb = dx02 * (y - y0)
        while y <= y2:
            a = x1 + sa // dy12
            b = x0 + sb // dy02
            sa += dx12
            sb += dx02
            if a > b:
                a, b = b, a
            self.hline(a, y, b - a + 1, color)
            y += 1

    def round_rect(self, x0, y0, width, height, radius, color):
        """Rectangle with rounded corners drawing function.
        This works like a regular rect though! if radius = 0
        Will draw the outline of a rextabgle with rounded corners with (x0,y0) at the top left"""
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
            self.vline(x0 - radius, y0, height - 2 * radius + 1, color)  # left
            self.vline(x0 + width - radius, y0, height - 2 * radius + 1, color)  # right
            self.hline(x0, y0 + height - radius + 1, width - 2 * radius + 1, color)  # bottom
            self.hline(x0, y0 - radius, width - 2 * radius + 1, color)  # top
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
                self.pixel(x0 - y, y0 - x, color)  # 180 to 135
                self.pixel(x0 - x, y0 - y, color)  # 90 to 135
                # top right
                self.pixel(x0 + x + width - 2 * radius, y0 - y, color)  # 90 to 45
                self.pixel(x0 + y + width - 2 * radius, y0 - x, color)  # 0 to 45
                # bottom right
                self.pixel(
                    x0 + y + width - 2 * radius, y0 + x + height - 2 * radius, color
                )  # 0 to 315
                self.pixel(
                    x0 + x + width - 2 * radius, y0 + y + height - 2 * radius, color
                )  # 270 to 315
                # bottom left
                self.pixel(x0 - x, y0 + y + height - 2 * radius, color)  # 270 to 255
                self.pixel(x0 - y, y0 + x + height - 2 * radius, color)  # 180 to 225

    def fill_round_rect(self, x0, y0, width, height, radius, color):
        """Filled circle drawing function.  Will draw a filled circule with
        center at x0, y0 and the specified radius."""
        # shift to correct for start point location
        x0 += radius
        y0 += radius

        # ensure that the radius will only ever half of the shortest side or less
        radius = int(min(radius, width / 2, height / 2))

        self.fill_rect(x0, y0 - radius, width - 2 * radius + 2, height + 2, color)

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
                self.vline(x0 - y, y0 - x, 2 * x + 1 + height - 2 * radius, color)  # 0 to .25
                self.vline(x0 - x, y0 - y, 2 * y + 1 + height - 2 * radius, color)  # .5 to .25
                # top right
                self.vline(
                    x0 + x + width - 2 * radius, y0 - y, 2 * y + 1 + height - 2 * radius, color
                )  # .5 to .75
                self.vline(
                    x0 + y + width - 2 * radius, y0 - x, 2 * x + 1 + height - 2 * radius, color
                )  # 1 to .75

    def _place_char(self, x0, y0, char, size, color):
        """A sub class used for placing a single character on the screen"""
        arr = self.font[char]
        width = arr[0]
        height = arr[1]
        # extract the char section of the data
        data = arr[2:]
        for x in range(width):
            for y in range(height):
                bit = bool(data[x] & (1 << y))
                # char pixel
                if bit:
                    self.fill_rect(size * x + x0, size * (height - y - 1) + y0, size, size, color)
                # else background pixel
                # else:
                #    try:
                #        self.fill_rect(
                #            size * x + x0, size * (height - y - 1) + y0, size, size, self.bgcolor
                #        )
                #    except TypeError:
                #        pass

    def text(self, x0, y0, string, size, color):
        x = x0
        y = y0
        for char in string:
            # make sure something is sent even if not in font dict
            try:
                self._place_char(x, y, char, size, color)
            except KeyError:
                char = "?CHAR?"
                self._place_char(x, y, char, size, color)
            x += size * self.font[char][0] + size


if __name__ == "__main__":
    from machine import I2C

    Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))
    ipg = InkplateGS2()
    ipm = InkplateMono()
    ipp = InkplatePartial(ipm)

    def wait_click(n):
        print("Press touch sensor %d to continue" % n)
        t = [Inkplate.TOUCH1, Inkplate.TOUCH2, Inkplate.TOUCH3][n - 1]
        while t() == 0:
            time.sleep_ms(100)
        while t() == 1:
            time.sleep_ms(100)
        print("Continuing...")

    iter = 0
    while True:
        if True:
            ipm.clear()
            t0 = time.ticks_ms()
            for x in range(300, 500, 20):
                ipm.line(x, 0, x + 10, 599, 1)
            ipm.fill_rect(50, 300, 200, 100, 1)
            ipm.fill_rect(400, 400, 300, 100, 1)
            for y in range(100):
                ipm.pixel(y, y, 1)
                ipm.pixel(y, 0, 1)
                ipm.pixel(0, y, 1)
                ipm.pixel(799 - y, 599 - y, 1)
                ipm.pixel(799 - y, 599 - 0, 1)
                ipm.pixel(799 - 0, 599 - y, 1)
            for y in range(100, 160):
                for x in range(100, 200):
                    ipm.pixel(x, y, 1)
                ipm.pixel(y, y, 0)
                ipm.pixel(y + 1, y, 0)  # makes white line more visible 'til waveforms are fixed
            ipm.circle(600, 200, 100, 1)
            print("TestPatt: in %dms" % (time.ticks_diff(time.ticks_ms(), t0)))
            ipm.display()
            if iter > 0:
                wait_click(3)
            else:
                time.sleep_ms(1000)

        if True:
            ipg.clear()
            for i in range(24):
                c = i & 3
                x = 100 + i * 20
                ipg.line(x, 0, x + 10, 599, c)
            for y in range(100):
                ipg.pixel(y, y, 0)
                ipg.pixel(y, 0, 0)
                ipg.pixel(0, y, 0)
                ipg.pixel(799 - y, 599 - y, 0)
                ipg.pixel(799 - y, 599 - 0, 0)
                ipg.pixel(799 - 0, 599 - y, 0)
            ipg.line(800, 0, 600, 200, 0)
            for i in range(4):
                ipg.fill_rect(50, 300 + i * 50, 300, 50, i)
            ipg.display()
            if iter > 0:
                wait_click(3)
            else:
                time.sleep_ms(1000)

        if True:
            ipm.clear()

            # from gfx_standard_font_01 import text_dict as std_font
            t0 = time.ticks_ms()
            ipm.circle(250, 250, 100, 1)
            ipm.rect(350, 250, 100, 100, 1)
            ipm.fill_circle(400, 300, 50, 1)
            # some fine white lines (they tend to be hard to see in the end)
            ipm.circle(400, 300, 48, 0)
            ipm.line(400, 251, 400, 349, 0)
            ipm.line(351, 300, 449, 300, 0)
            ipm.line(351, 251, 449, 349, 0)
            ipm.line(351, 349, 449, 251, 0)
            # hello world box
            ipm.text(304, 102, "HELLO WORLD!", 4, 1)
            ipm.round_rect(290, 90, 300, 50, 10, 1)
            ipm.round_rect(291, 91, 300, 50, 10, 1)
            print("GFXPatt: in %dms" % (time.ticks_diff(time.ticks_ms(), t0)))
            ipm.display()
            if iter > 0:
                wait_click(3)
            else:
                time.sleep_ms(1000)

        if True:
            # Draw the hello-world label into its own framebuffer
            hello_fb = bytearray(304 * 53 // 8)
            # framebuf.FrameBuffer cannot be extended, so we need to wrap it, ugh!
            class MyFB(framebuf.FrameBuffer):
                def __init__(self, fb, w, h, t, s):
                    super().__init__(fb, w, h, t, s)
                    InkplateShapes.__mix_me_in(MyFB)

            hello = MyFB(hello_fb, 302, 53, framebuf.MONO_HMSB, 304)
            hello.fill(0)
            hello.text(14, 12, "HELLO WORLD!", 4, 1)
            hello.round_rect(0, 0, 300, 50, 10, 1)
            hello.round_rect(1, 1, 300, 50, 10, 1)

            x = 290
            y = 90
            for i in range(30):
                t0 = time.ticks_ms()
                ipp.start()
                ymin = y
                ymax = y + 53
                ipm.fill_rect(x, y, 302, 53, 0)
                if i < 10:
                    x -= 20
                    y += 15
                elif i < 22:
                    x += 10
                    y += 20
                else:
                    x += 20
                    y -= 40
                if y < ymin:
                    ymin = y
                if y + 53 > ymax:
                    ymax = y + 53
                ipm.blit(hello, x, y)
                print("GFX: in %dms" % (time.ticks_diff(time.ticks_ms(), t0)))
                ipp.display(y=ymin, h=ymax - ymin)
                # ipp.display()
            if iter > 0:
                wait_click(3)
            else:
                time.sleep_ms(1000)

        iter += 1
