# Copyright © 2020 by Thorsten von Eicken.
import time
import micropython
from machine import Pin
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
        self._framebuf = bytearray(60000)

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
        # time.sleep_us(10)
        self.EPD_LE(0)
        # move to next row
        self.EPD_SPH(0)
        self.EPD_CL(1)
        # time.sleep_us(10)
        self.EPD_CL(0)
        self.EPD_SPH(1)
        # done
        self.EPD_CKV(1)

    # vscan_end latches the last row into the display pixels
    def vscan_end(self):
        self.EPD_CKV(0)
        # latch row
        # self.EPD_LE(1)
        # self.EPD_LE(0)
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

    # gen_luts generates the look-up tables to convert a nibble (4 bits) of pixels to the
    # 32-bits that need to be pushed into the gpio port.
    @classmethod
    def gen_luts(cls):
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
                wht = wht | ((2 if (i >> bit) & 1 == 0 else 0) << (2 * bit))
                blk = blk | ((1 if (i >> bit) & 1 == 1 else 0) << (2 * bit))
                bw = bw | ((1 if (i >> bit) & 1 == 1 else 2) << (2 * bit))
            cls.lut_wht[i] = Inkplate.byte2gpio[wht] | EPD_CL
            cls.lut_blk[i] = Inkplate.byte2gpio[blk] | EPD_CL
            cls.lut_bw[i] = Inkplate.byte2gpio[bw] | EPD_CL
        # print("Black: %08x, White:%08x Data:%08x" % (cls.lut_bw[0xF], cls.lut_bw[0], EPD_DATA))

    # fill_row writes the same value to all bytes in a row, it is used for cleaning
    @micropython.viper
    def fill_row(self, data: int):
        # cache vars into locals
        w1ts = ptr32(int(ESP32_W1TS))
        w1tc = ptr32(int(ESP32_W1TC))
        epd_cl = int(EPD_CL)
        # set the data output gpios
        w1tc[0] = EPD_DATA | epd_cl
        w1ts[0] = data
        # send first byte
        self.EPD_SPH(0)
        w1ts[0] = epd_cl
        w1tc[0] = epd_cl
        self.EPD_SPH(1)
        w1ts[0] = epd_cl
        w1tc[0] = epd_cl
        # send the remaining 99 bytes (792 pixels)
        for c in range(99):
            w1ts[0] = epd_cl
            w1tc[0] = epd_cl
            w1ts[0] = epd_cl
            w1tc[0] = epd_cl

    def clean_fast(self, color, rep):
        t0 = time.ticks_ms()
        c = [0xAA, 0x55, 0x00, 0xFF][color]
        data = Inkplate.byte2gpio[c] & ~EPD_CL
        for i in range(rep):
            self.vscan_start()
            for r in range(600):
                self.fill_row(data)
                self.vscan_write()  # half the time is in here...
                # time.sleep_us(230)
            self.vscan_end()
        print("Clean: 0x%02x->0x%08x in %dms" % (c, data, time.ticks_diff(time.ticks_ms(), t0)))

    def clean_fast2(self, color, rep):
        t0 = time.ticks_ms()
        c = color
        data = Inkplate.byte2gpio[c] & ~EPD_CL
        for i in range(rep):
            self.vscan_start()
            for r in range(600):
                self.fill_row(data)
                self.vscan_write()
                # time.sleep_us(230)
            self.vscan_end()
        print("Clean: 0x%02x->0x%08x in %dms" % (c, data, time.ticks_diff(time.ticks_ms(), t0)))

    # send_row writes a row of data to the display
    @micropython.viper
    def send_row(self, lut_in, row: int):
        # cache vars into locals
        w1ts = ptr32(int(ESP32_W1TS))
        w1tc = ptr32(int(ESP32_W1TC))
        epd_cl = int(EPD_CL)  # clock bit as 32-bit gpio mask
        off = int(EPD_DATA | EPD_CL)  # mask with all data bits and clock bit
        fb = ptr8(self._framebuf)
        ix = int(row * 100)  # index into framebuffer
        lut = ptr32(lut_in)
        # send first byte
        data = int(fb[ix])
        ix += 1
        w1tc[0] = off
        self.EPD_SPH(0)
        w1ts[0] = lut[data >> 4]  # set data bits and assert clock
        w1tc[0] = epd_cl  # clear clock, leaving data bits (unreliable if data also cleared)
        w1tc[0] = off  # clear data bits as well ready for next byte
        self.EPD_SPH(1)
        w1ts[0] = lut[data & 0xF]
        w1tc[0] = epd_cl
        w1tc[0] = off
        # send the remaining 99 bytes (792 pixels)
        for c in range(99):
            data = int(fb[ix])
            ix += 1
            w1ts[0] = lut[data >> 4]
            w1tc[0] = epd_cl
            w1tc[0] = off
            w1ts[0] = lut[data & 0xF]
            w1tc[0] = epd_cl
            w1tc[0] = off

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display_mono(self):
        self.power_on()

        # clean the display
        self.clean_fast(0, 1)
        self.clean_fast(1, 1)
        # self.clean_fast(2, 1)
        # self.clean_fast(3, 1)
        self.clean_fast(0, 1)
        # self.clean_fast(2, 1)
        # self.clean_fast(1, 1)
        # self.clean_fast(2, 1)
        # self.clean_fast(0, 2)

        # the display gets written N times
        t0 = time.ticks_ms()
        n = 0
        for lut in [Inkplate.lut_blk, Inkplate.lut_blk, Inkplate.lut_bw]:
            self.vscan_start()
            # write 600 rows
            for r in range(600):
                self.send_row(lut, r)
                self.vscan_write()
                # time.sleep_us(230)
            self.vscan_end()
            n += 1
        print("Mono: in %dms" % (time.ticks_diff(time.ticks_ms(), t0) // n))

        self.power_off()

    @micropython.viper
    def clear(self):
        t0 = time.ticks_ms()
        fb = ptr8(self._framebuf)
        for ix in range(60000):
            fb[ix] = 0
        print("Clear: in %dms" % (time.ticks_diff(time.ticks_ms(), t0)))

    def display_test(self):
        for r in range(600):
            if r > 500:
                for i in range(100):
                    self._framebuf[r * 100 + i] = 0xFF
            else:
                for i in range(20):
                    self._framebuf[r * 100 + i] = 1 << ((r // 50) % 8)
                for i in range(20, 100):
                    self._framebuf[r * 100 + i] = i

    def pixel(self, x, y, color):
        ix = 59999 - y * 100 - x // 8
        bit = 1 << (x & 7)
        if color:
            self._framebuf[ix] |= bit
        else:
            self._framebuf[ix] &= ~bit


if __name__ == "__main__":
    from machine import I2C

    ip = Inkplate(I2C(0, scl=Pin(22), sda=Pin(21)))
    ip.display_test()
    ip.display_mono()

    ip.clear()
    t0 = time.ticks_ms()
    for y in range(100):
        ip.pixel(y, y, 1)
        ip.pixel(y, 0, 1)
        ip.pixel(0, y, 1)
        ip.pixel(799 - y, 599 - y, 1)
        ip.pixel(799 - y, 599 - 0, 1)
        ip.pixel(799 - 0, 599 - y, 1)
    for y in range(100, 160):
        for x in range(100, 120):
            ip.pixel(x, y, 1)
        ip.pixel(y, y, 0)
        ip.pixel(y + 1, y, 0)  # makes white line more visible 'til waveforms are fixed
    print("TestPatt: in %dms" % (time.ticks_diff(time.ticks_ms(), t0)))
    ip.display_mono()

    ip.clear()
    from gfx import GFX
    #from gfx_standard_font_01 import text_dict as std_font
    disp = GFX(800, 600, ip.pixel) # , font=std_font)
    disp.circle(250, 250, 100, 1)
    disp.rect(350, 250, 100, 100, 1)
    disp.fill_circle(400, 300, 50, 1)
    disp.text(304, 102, "HELLO WORLD!", 4, 1)
    disp.round_rect(290, 90, 300, 50, 10, 1)
    disp.round_rect(291, 91, 300, 50, 10, 1)
    ip.display_mono()
