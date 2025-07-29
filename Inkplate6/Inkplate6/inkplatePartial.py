# FILE: inkplatePartial.py
# AUTHOR: Soldered
# BRIEF: InkplatePartial managed partial updates. It starts by making a copy of the current framebuffer
# and then when asked to draw it renders the differences between the copy and the new framebuffer
# state. The constructor needs a reference to the current/main display object (InkplateMono).
# LAST UPDATED: 2025-05-26
import time
import framebuf
from shapes import Shapes
from uarray import array
from inkplate6 import _Inkplate

# Raw display constants for Inkplate 6
D_ROWS = const(600)
D_COLS = const(800)

# Waveforms for 2 bits per pixel grey-scale.
# Order of 4 values in each tuple: blk, dk-grey, light-grey, white
# Meaning of values: 0=dischg, 1=black, 2=white, 3=skip
# Uses "colors" 0 (black), 3, 5, and 7 (white) from 3-bit waveforms below

# add discharge to waveforms to try to fix them
WAVE_2B = (  # original mpy driver for Ink 6, differs from arduino driver below
    (0, 0, 0, 0),
    (0, 0, 0, 0),
    (0, 1, 1, 0),
    (0, 1, 1, 0),
    (1, 2, 1, 0),
    (1, 1, 2, 0),
    (1, 2, 2, 2),
)
# Ink6 WAVEFORM3BIT from arduino driver
# {{0,1,1,0,0,1,1,0},{0,1,2,1,1,2,1,0},{1,1,1,2,2,1,0,0},{0,0,0,1,1,1,2,0},
#  {2,1,1,1,2,1,2,0},{2,2,1,1,2,1,2,0},{1,1,1,2,1,2,2,0},{0,0,0,0,0,0,2,0}};

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

# Inkplate provides access to the pins of the Inkplate 6 as well as to low-level display
# functions.

RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04
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
        ip = _Inkplate
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
            # skip remaining rows (doesn't seem to be necessary for Inkplate 6 but it is for 10)
            if r > 0:
                skip_rows(r)
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
                lut[o * 16 + n] = _Inkplate.byte2gpio[bw] | EPD_CL
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
            _Inkplate.vscan_write()
            rows -= 1
            time.sleep_us(50)

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, old_framebuf, new_framebuf, row: int):
        ROW_LEN = D_COLS >> 3  # length of row in bytes
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        ofb = ptr8(old_framebuf)
        nfb = ptr8(new_framebuf)
        ix = int(row * ROW_LEN + (ROW_LEN - 1))  # index into framebuffer
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
        # send the remaining bytes
        for c in range(ROW_LEN - 1):
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