# MicroPython driver for Inkplate 5
# By Soldered Electronics
# Based on the original contribution by https://github.com/tve
import time
import micropython
import framebuf
from PCAL6416A import *
from micropython import const
from shapes import Shapes
from uarray import array
from inkplate5v2 import _Inkplate

# ===== Constants that change between the Inkplate 5 and 10

# Raw display constants for Inkplate 5
D_ROWS = const(720)
D_COLS = const(1280)


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


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)
        ip = InkplateMono
        ip._gen_luts()
        ip._wave = [ip.lut_blk, ip.lut_blk, ip.lut_blk,
                    ip.lut_blk, ip.lut_blk, ip.lut_bw]

    # gen_luts generates the look-up tables to convert a nibble (4 bits) of pixels to the
    # 32-bits that need to be pushed into the gpio port.
    # The LUTs used here were copied from the e-Radionica Inkplate-6-Arduino-library.
    @classmethod
    @micropython.native
    def _gen_luts(cls):
        # is there a better way to init an array with 16 words???
        b16 = bytes(4 * 16)
        # bits to ship to gpio to make pixels white
        cls.lut_wht = array("L", b16)
        # bits to ship to gpio to make pixels black
        cls.lut_blk = array("L", b16)
        # bits to ship to gpio to make pixels black and white
        cls.lut_bw = array("L", b16)
        for i in range(16):
            wht = 0
            blk = 0
            bw = 0
            # display uses 2 bits per pixel: 00=discharge, 01=black, 10=white, 11=skip
            for bit in range(4):
                wht = wht | ((2 if (i >> bit) & 1 == 0 else 3) << (2 * bit))
                blk = blk | ((1 if (i >> bit) & 1 == 1 else 3) << (2 * bit))
                bw = bw | ((1 if (i >> bit) & 1 == 1 else 2) << (2 * bit))
            cls.lut_wht[i] = _Inkplate.byte2gpio[wht] | EPD_CL
            cls.lut_blk[i] = _Inkplate.byte2gpio[blk] | EPD_CL
            cls.lut_bw[i] = _Inkplate.byte2gpio[bw] | EPD_CL
        # print("Black: %08x, White:%08x Data:%08x" % (cls.lut_bw[0xF], cls.lut_bw[0], EPD_DATA))

    # _send_row writes a row of data to the display
    @micropython.viper
    @staticmethod
    def _send_row(lut_in, framebuf, row: int):
        ROW_LEN = D_COLS >> 3  # length of row in bytes
        # cache vars into locals
        w1ts0 = ptr32(int(ESP32_GPIO + 4 * W1TS0))
        w1tc0 = ptr32(int(ESP32_GPIO + 4 * W1TC0))
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        fb = ptr8(framebuf)
        ix = int(row * ROW_LEN + ROW_LEN - 1)  # index into framebuffer
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
        # send the remaining bytes
        for c in range(ROW_LEN - 1):
            data = int(fb[ix])
            ix -= 1
            w1ts0[0] = lut[data >> 4]
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off
            w1ts0[0] = lut[data & 0xF]
            # w1tc0[0] = EPD_CL
            w1tc0[0] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    @micropython.native
    def display(self):
        ip = _Inkplate
        ip.power_on()

        # Create a vertically flipped copy of the framebuffer using viper
        fb = self._framebuf
        fb_width = 1280
        fb_height = 720  # Use the actual display height constant
        row_bytes = (fb_width + 7) // 8  # Monochrome: 8 pixels per byte

        # clean the display
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 12)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)

        # the display gets written N times
        t1 = time.ticks_ms()
        n = 0
        send_row = InkplateMono._send_row
        vscan_write = ip.vscan_write
        for lut in self._wave:
            ip.vscan_start()
            # write all rows (now in correct order from top to bottom)
            for r in range(D_ROWS):
                send_row(lut, fb, r)
                vscan_write()
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

    @micropython.viper
    def clear(fb:ptr8):
        for ix in range(1280 * 720 // 8):
           fb[ix] = 0


Shapes.__mix_me_in(InkplateMono)
