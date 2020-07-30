# Copyright © 2020 by Thorsten von Eicken.
import time
import micropython
from machine import Pin, mem32
from uarray import array
from mcp23017 import MCP23017
from micropython import const

TPS65186_addr = const(0x48)  # I2C address

# ESP32 GPIO set and clear registers to twiddle all 32 bits at once
# from esp-idf:
# define DR_REG_GPIO_BASE           0x3ff44000
# define GPIO_OUT_W1TS_REG          (DR_REG_GPIO_BASE + 0x0008)
# define GPIO_OUT_W1TC_REG          (DR_REG_GPIO_BASE + 0x000c)
ESP32_W1TS = const(0x3FF44000 + 0x0008)  # bits written as 1's set the corresponding GPIOs
ESP32_W1TC = const(0x3FF44000 + 0x000C)  # bits written as 1's clear the corresponding GPIOs
EPD_DATA = const(0x0E8C0030)  # bits corresponding to EPD_D0..EPD_D7
EPD_CL = const(0x00000001)  # bit corresponding to the EPD_CL output pin


# Inkplate provides access to the pins of the Inkplate 6 as well as to low-level display
# functions.
class Inkplate:
    def __init__(self, i2c):
        self._i2c = i2c
        self._mcp23017 = MCP23017(i2c)
        # Display control lines
        self.EPD_CL = Pin(0, Pin.OUT, value=0)
        self.EPD_LE = Pin(2, Pin.OUT, value=0)
        self.EPD_CKV = Pin(32, Pin.OUT, value=0)
        self.EPD_SPH = Pin(33, Pin.OUT, value=1)
        self.EPD_OE = self._mcp23017.pin(0, Pin.OUT, value=0)
        self.EPD_GMODE = self._mcp23017.pin(1, Pin.OUT, value=0)
        self.EPD_SPV = self._mcp23017.pin(2, Pin.OUT, value=1)
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
        self.TPS_WAKEUP = self._mcp23017.pin(3, Pin.OUT, value=0)
        self.TPS_PWRUP = self._mcp23017.pin(4, Pin.OUT, value=0)
        self.TPS_VCOM = self._mcp23017.pin(5, Pin.OUT, value=0)
        self.TPS_INT = self._mcp23017.pin(6, Pin.IN)
        self.TPS_PWR_GOOD = self._mcp23017.pin(7, Pin.IN)
        # Misc
        self.GPIO0_PUP = self._mcp23017.pin(8, Pin.OUT, value=0)
        self.VBAT_EN = self._mcp23017.pin(9, Pin.OUT, value=1)
        # Touch sensors
        self.TOUCH1 = self._mcp23017.pin(10, Pin.IN)
        self.TOUCH2 = self._mcp23017.pin(11, Pin.IN)
        self.TOUCH3 = self._mcp23017.pin(12, Pin.IN)

        self._on = False  # whether panel is powered on or not

        if len(Inkplate.byte2gpio) == 0:
            Inkplate.gen_byte2gpio()
            Inkplate.gen_luts()

    def _tps65186_write(self, reg, v):
        self._i2c.writeto_mem(TPS65186_addr, reg, bytes((v,)))

    def _tps65186_read(self, reg):
        self._i2c.readfrom_mem(TPS65186_addr, reg, 1)[0]

    # power_on turns the voltage regulator on and wakes up the display (GMODE and OE)
    def power_on(self):
        if self._on:
            return
        self._on = True
        # turn on power regulator
        self.TPS_WAKEUP(1)
        self.TPS_PWRUP(1)
        self.TPS_VCOM(1)
        # enable all rails
        self._tps65186_write(0x01, 0x3F)  # ???
        time.sleep_ms(40)
        self._tps65186_write(0x0D, 0x80)  # ???
        time.sleep_ms(2)
        self._temperature = self._tps65186_read(1)
        # wake-up display
        self.EPD_GMODE(1)
        self.EPD_OE(1)

    # power_off puts the display to sleep and cuts the power
    def power_off(self):
        if not self._on:
            return
        self._on = False
        # put display to sleep
        self.EPD_GMODE(0)
        self.EPD_OE(0)
        # turn off power regulator
        self.TPS_PWRUP(0)
        self.TPS_WAKEUP(0)
        self.TPS_VCOM(0)

    # vscan_start begins a vertical scan by toggling CKV and SPV a few times (magic)
    def vscan_start(self):
        def ckv_pulse():
            self.EPD_CKV(0)
            self.EPD_CKV(1)

        self.EPD_CKV(1)
        time.sleep_us(7)
        self.EPD_SPV(0)
        time.sleep_us(10)
        ckv_pulse()
        time.sleep_us(8)
        self.EPD_SPV(1)
        time.sleep_us(10)
        ckv_pulse()
        time.sleep_us(18)
        ckv_pulse()
        time.sleep_us(18)
        ckv_pulse()

    # vscan_write latches the row into the display pixels and moves to the next row
    def vscan_write(self):
        self.EPD_CKV(0)
        # latch row
        self.EPD_LE(1)
        time.sleep_us(10)
        self.EPD_LE(0)
        # move to next row
        self.EPD_SPH(0)
        self.EPD_CL(1)
        time.sleep_us(10)
        self.EPD_CL(0)
        self.EPD_SPH(1)
        # done
        self.EPD_CKV(1)

    # vscan_end latches the last row into the display pixels
    def vscan_end(self):
        self.EPD_CKV(0)
        # latch row
        self.EPD_LE(1)
        self.EPD_LE(0)
        # done
        self.EPD_CKV(1)

    # nib2gpio converts a nibble (4 bits) of pixels to 32 bits of gpio0..31
    # (oh, e-radionica, why didn't you group the gpios better?!)
    byte2gpio = []

    @classmethod
    def gen_byte2gpio(cls):
        cls.byte2gpio = array("L", bytes(4 * 256))
        for b in range(256):
            cls.byte2gpio[b] = (
                (b & 0x3) << 4 | (b & 0xC) << 16 | (b & 0x10) << 19 | (b & 0xE0) << 20
            )
        # sanity check
        union = 0
        for i in range(256):
            union |= cls.byte2gpio[i]
        assert union == EPD_DATA

    # expand_pix expands 4 1-bit pixels to the 8 bits expected by the display
    # display 2 bits per pixel: 00=no-action, 01=black, 10=white, 11=no-action
    # expand_pix = [
    #    0x55, 0x56, 0x59, 0x5A,
    #    0x65, 0x66, 0x69, 0x6A,
    #    0x95, 0x96, 0x99, 0x9A,
    #    0xA5, 0xA6, 0xA9, 0xAA,
    # ]

    # gen_luts generates the look-up tables to convert a nibble (4 bits) of pixels to the
    # 32-bits that need to be pushed into the gpio port.
    @classmethod
    def gen_luts(cls):
        cls.lut_wht = []  # bits to ship to gpio to make pixels white
        cls.lut_blk = []  # bits to ship to gpio to make pixels black
        cls.lut_bw = []  # bits to ship to gpio to make pixels black and white
        for i in range(16):
            wht = 0
            blk = 0
            bw = 0
            # display uses 2 bits per pixel: 00=discharge, 01=black, 10=white, 11=skip
            for bit in range(4):
                wht = wht | ((2 if (i >> bit) & 1 == 0 else 0) << (2 * bit))
                blk = blk | ((1 if (i >> bit) & 1 == 1 else 0) << (2 * bit))
                bw = bw | ((1 if (i >> bit) & 1 == 1 else 2) << (2 * bit))
            cls.lut_wht.append(Inkplate.byte2gpio[wht] | EPD_CL)
            cls.lut_blk.append(Inkplate.byte2gpio[blk] | EPD_CL)
            cls.lut_bw.append(Inkplate.byte2gpio[bw] | EPD_CL)
        # print("Black: %08x, White:%08x Data:%08x" % (cls.lut_bw[0xF], cls.lut_bw[0], EPD_DATA))

    @micropython.native
    def fill_row(self, data):
        # cache vars into locals
        m32 = mem32
        W1TS = ESP32_W1TS
        W1TC = ESP32_W1TC
        off = EPD_DATA | EPD_CL
        # send first byte
        self.EPD_SPH(0)
        m32[W1TS] = data
        m32[W1TC] = off
        self.EPD_SPH(1)
        m32[W1TS] = data
        m32[W1TC] = off
        # send the remaining 99 bytes (792 pixels)
        for c in range(99):
            m32[W1TS] = data
            m32[W1TC] = off
            m32[W1TS] = data
            m32[W1TC] = off

    def clean_fast(self, color, rep):
        c = [0xAA, 0x55, 0x00, 0xFF][color]
        data = Inkplate.byte2gpio[c] | EPD_CL
        for i in range(rep):
            self.vscan_start()
            for r in range(600):
                self.fill_row(data)
                self.vscan_write()
                time.sleep_us(230)
            self.vscan_end()

    @micropython.native
    def send_row(self, lut, row):
        # cache vars into locals
        m32 = mem32
        W1TS = ESP32_W1TS
        W1TC = ESP32_W1TC
        off = EPD_DATA | EPD_CL
        # send first byte
        data = row[0]
        self.EPD_SPH(0)
        m32[W1TS] = lut[data >> 4]
        m32[W1TC] = off
        self.EPD_SPH(1)
        m32[W1TS] = lut[data & 0xF]
        m32[W1TC] = off
        # send the remaining 99 bytes (792 pixels)
        for c in range(99):
            data = row[0]  # FIXME!
            m32[W1TS] = lut[data >> 4]
            m32[W1TC] = off
            m32[W1TS] = lut[data & 0xF]
            m32[W1TC] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display_mono(self):
        self.power_on()

        # clean the display
        self.clean_fast(0, 1)
        self.clean_fast(1, 1)
        self.clean_fast(2, 1)
        self.clean_fast(3, 1)
        self.clean_fast(0, 1)
        # self.clean_fast(2, 1)
        # self.clean_fast(1, 1)
        # self.clean_fast(2, 1)
        # self.clean_fast(0, 2)

        # the display gets written N times
        for lut in [Inkplate.lut_blk, Inkplate.lut_blk, Inkplate.lut_bw]:
            self.vscan_start()
            # write 600 rows
            for r in range(600):
                data = [1 << ((r // 50) % 8)]
                self.send_row(lut, data)
                self.vscan_write()
                time.sleep_us(230)
            self.vscan_end()

        self.power_off()


if __name__ == "__main__":
    from machine import I2C

    ip = Inkplate(I2C(0, scl=Pin(22), sda=Pin(21)))
    ip.display_mono()
