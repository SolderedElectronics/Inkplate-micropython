from inkplate6FLICK import _Inkplate
import time
import framebuf
from uarray import array
from PCAL6416A import *
from micropython import const
from shapes import Shapes
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

# Raw display constants for Inkplate 6
D_ROWS = const(758)
D_COLS = const(1024)
# Inkplate display with 2 bits of gray scale (4 levels)
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

        cls._wave = [genlut(w) for w in WAVE_2B]

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, framebuf, row: int):
        ROW_LEN = D_COLS >> 2  # length of row in bytes
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        fb = ptr8(framebuf)
        ix = int(row * ROW_LEN + (ROW_LEN - 1))  # index into framebuffer
        lut = ptr8(lut_in)
        b2g = ptr32(_Inkplate.byte2gpio)
        # send first byte
        data = int(fb[ix])
        ix -= 1
        w1tc0[0] = off
        w1tc0[W1TC1 - W1TC0] = EPD_SPH
        w1ts0[0] = b2g[lut[data >> 4] << 4 | lut[data & 0xF]
                       ] | EPD_CL  # set data bits and clock
        # w1tc0[0] = EPD_CL  # clear clock, leaving data bits (unreliable if data also cleared)
        w1tc0[0] = off  # clear data bits as well ready for next byte
        w1ts0[W1TS1 - W1TS0] = EPD_SPH
        # send the remaining bytes
        for c in range(ROW_LEN - 1):
            data = int(fb[ix])
            ix -= 1
            w1ts0[0] = b2g[lut[data >> 4] << 4 | lut[data & 0xF]] | EPD_CL
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    @micropython.native
    def display(self):
        ip = _Inkplate
        ip.power_on()

        # clean the display
        t0 = time.ticks_ms()
        ip.clean(0, 15)
        ip.clean(2, 1)
        ip.clean(1, 15)
        ip.clean(2, 1)
        ip.clean(0, 15)
        ip.clean(2,1)

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

        ip.clean(3, 1)
        ip.power_off()

    @micropython.viper
    def clear(fb:ptr8):
        for ix in range(1024*758//4):
           fb[ix] = 0xFF


Shapes.__mix_me_in(InkplateGS2)
