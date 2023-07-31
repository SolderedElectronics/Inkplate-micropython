import time
import os
from machine import ADC, I2C, SPI, Pin, SDCard
from micropython import const
from shapes import Shapes
from PCAL6416A import *
from gfx import GFX
from gfx_standard_font_01 import text_dict as std_font

# Connections between ESP32 and color Epaper
EPAPER_RST_PIN = const(19)
EPAPER_DC_PIN = const(33)
EPAPER_CS_PIN = const(27)
EPAPER_BUSY_PIN = const(32)
EPAPER_CLK = const(18)
EPAPER_DIN = const(23)

pixelMaskLUT = [0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80]
pixelMaskGLUT = [0xF, 0xF0]
LUT_IP7 = [0b0011, 0b0000, 0b0100]

# ePaper resolution
E_INK_HEIGHT = 384
E_INK_WIDTH = 640

E_INK_NUM_PIXELS = E_INK_HEIGHT * E_INK_WIDTH
E_INK_BUFFER_SIZE = E_INK_NUM_PIXELS // 2

busy_timeout_ms = 30000

class Inkplate:

    # Colors
    WHITE = 0b00000000
    BLACK = 0b00000001
    RED = 0b00000010

    _width = E_INK_WIDTH
    _height = E_INK_HEIGHT

    rotation = 0
    textSize = 1

    _panelState = False

    _framebuf = bytearray([0x33] * E_INK_BUFFER_SIZE)

    @classmethod
    def begin(self):
        self.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        self.spi = SPI(2)

        self.clearDisplay()

        self.GFX = GFX(
            E_INK_WIDTH,
            E_INK_HEIGHT,
            self.writePixel,
            self.writeFastHLine,
            self.writeFastVLine,
            self.writeFillRect,
            None,
            None,
        )

        # Wake the panel and init it
        if not (self.setPanelDeepSleepState(False)):
            return False

        # Put it back to sleep
        self.setPanelDeepSleepState(True)

        # Set i2c
        self._i2c = I2C(0, scl=Pin(22), sda=Pin(21))

        # Init gpio expander
        self._PCAL6416A = PCAL6416A(self._i2c)

        # Init SD card
        self.SD_ENABLE = gpioPin(self._PCAL6416A, 10, modeOUTPUT)
        self.SD_ENABLE.digitalWrite(1) # Initially disable the SD card

        # Set battery enable pin
        self.VBAT_EN = gpioPin(self._PCAL6416A, 9, modeOUTPUT)
        self.VBAT_EN.digitalWrite(0)  # Initially disable the battery read

        # Set battery read pin
        self.VBAT = ADC(Pin(35))
        self.VBAT.atten(ADC.ATTN_11DB)
        self.VBAT.width(ADC.WIDTH_12BIT)

        self.setRotation(0)

        return True

    @classmethod
    def getPanelDeepSleepState(self):
        return self._panelState

    @classmethod
    def setPanelDeepSleepState(self, state):

        # False wakes the panel up
        # True puts it to sleep
        if not state:
            self.spi.init(baudrate=40000000, firstbit=SPI.MSB,
                          polarity=0, phase=0)
            self.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
            self.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT)
            self.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT)
            self.EPAPER_CS_PIN = Pin(EPAPER_CS_PIN, Pin.OUT)
            time.sleep_ms(10)
            self.resetPanel()

            # Reinit the panel
            self.sendCommand(b"\x12")
            _timeout = time.ticks_ms()
            while not self.EPAPER_BUSY_PIN.value() and (time.ticks_ms() - _timeout) < busy_timeout_ms:
                pass

            self.sendCommand(b"\x65")
            self.sendData(b"\x01")
            self.sendCommand(b"\xAB")
            self.sendCommand(b"\x65")
            self.sendData(b"\x00")
            self.sendCommand(b"\x01")
            self.sendData(b"\x37")
            self.sendData(b"\x00")
            self.sendCommand(b"\x00")
            self.sendData(b"\xCF")
            self.sendData(b"\x08")
            self.sendCommand(b"\x06")
            self.sendData(b"\xc7")
            self.sendData(b"\xcc")
            self.sendData(b"\x28")
            self.sendCommand(b"\x30")
            self.sendData(b"\x3c")
            self.sendCommand(b"\x41")
            self.sendData(b"\x00")
            self.sendCommand(b"\x50")
            self.sendData(b"\x77")
            self.sendCommand(b"\x60")
            self.sendData(b"\x22")
            self.sendCommand(b"\x61")
            self.sendData(b"\x02")
            self.sendData(b"\x80")
            self.sendData(b"\x01")
            self.sendData(b"\x80")
            self.sendCommand(b"\x82")
            self.sendData(b"\x1E")
            self.sendCommand(b"\xe5")
            self.sendData(b"\x03")
            self.sendCommand(b"\x04")

            self._panelState = True

            return True

        else:

            # Put the panel to sleep
            self.sendCommand(b"\x65")
            self.sendData(b"\x01")
            self.sendCommand(b"\xB9")
            self.sendCommand(b"\x65")
            self.sendData(b"\x00")
            self.sendCommand(b"\x02")
            # Wait for ePaper
            _timeout = time.ticks_ms()
            while not self.EPAPER_BUSY_PIN.value() and (time.ticks_ms() - _timeout) < busy_timeout_ms:
                pass
            self.sendCommand(b"\07")
            self.sendData(b"\xA5")

            time.sleep_ms(1)
            # Turn off SPI
            self.spi.deinit()
            self.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
            self.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.IN)
            self.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.IN)
            self.EPAPER_CS_PIN = Pin(EPAPER_CS_PIN, Pin.IN)

            self._panelState = False

            return False

    @classmethod
    def resetPanel(self):
        self.EPAPER_RST_PIN.value(0)
        time.sleep_ms(15)
        self.EPAPER_RST_PIN.value(1)
        time.sleep_ms(15)

    @classmethod
    def sendCommand(self, command):
        self.EPAPER_DC_PIN.value(0)
        self.EPAPER_CS_PIN.value(0)
        self.spi.write(command)

        self.EPAPER_CS_PIN.value(1)

    @classmethod
    def sendData(self, data):
        self.EPAPER_CS_PIN.value(0)
        self.EPAPER_DC_PIN.value(1)
        self.spi.write(data)

        self.EPAPER_CS_PIN.value(1)
        time.sleep_ms(1)

    @classmethod
    def clearDisplay(self):
        self._framebuf = bytearray(([0x33] * E_INK_BUFFER_SIZE))

    @classmethod
    def display(self):

        # Wake the display
        self.setPanelDeepSleepState(False)

        # Write b/w pixels
        self.sendCommand(b"\x10")
        self.sendData(self._framebuf)

        # EPD update
        self.sendCommand(b"\x12")

        time.sleep_ms(10)

        _timeout = time.ticks_ms()
        while not self.EPAPER_BUSY_PIN.value() and (time.ticks_ms() - _timeout) < busy_timeout_ms:
            pass

        # Put the display back to sleep
        self.setPanelDeepSleepState(True)

    @classmethod
    def width(self):
        return self._width

    @classmethod
    def height(self):
        return self._height

    # Arduino compatibility functions
    @classmethod
    def setRotation(self, x):
        self.rotation = x % 4
        if self.rotation == 0 or self.rotation == 2:
            self._width = E_INK_WIDTH
            self._height = E_INK_HEIGHT
        elif self.rotation == 1 or self.rotation == 3:
            self._width = E_INK_HEIGHT
            self._height = E_INK_WIDTH

    @classmethod
    def getRotation(self):
        return self.rotation

    @classmethod
    def drawPixel(self, x, y, c):
        self.startWrite()
        self.writePixel(x, y, c)
        self.endWrite()

    @classmethod
    def startWrite(self):
        pass

    @classmethod
    def writePixel(self, x, y, c):
        if x > self.width() - 1 or y > self.height() - 1 or x < 0 or y < 0:
            return
        
        if (c > 2):
            return

        if self.rotation == 3:
            x = self.width() - x - 1
            x, y = y, x
        elif self.rotation == 0:
            x = self.width() - x - 1
            y = self.height() - y - 1
        elif self.rotation == 1:
            y = self.height() - y - 1
            x, y = y, x
        elif self.rotation == 2:
            pass

        _x = x // 2
        _x_sub = x % 2
        _position = E_INK_WIDTH // 2 * y + _x

        # Clear both black and red frame buffer

        # Clear the old pixel in the buffer
        self._framebuf[_position] &= pixelMaskGLUT[_x_sub]
        self._framebuf[_position] |= (LUT_IP7[c] << ((1 - _x_sub) * 4))

    @classmethod
    def writeFillRect(self, x, y, w, h, c):
        for j in range(w):
            for i in range(h):
                self.writePixel(x + j, y + i, c)

    @classmethod
    def writeFastVLine(self, x, y, h, c):
        for i in range(h):
            self.writePixel(x, y + i, c)

    @classmethod
    def writeFastHLine(self, x, y, w, c):
        for i in range(w):
            self.writePixel(x + i, y, c)

    @classmethod
    def writeLine(self, x0, y0, x1, y1, c):
        self.GFX.line(x0, y0, x1, y1, c)

    @classmethod
    def endWrite(self):
        pass

    @classmethod
    def drawFastVLine(self, x, y, h, c):
        self.startWrite()
        self.writeFastVLine(x, y, h, c)
        self.endWrite()

    @classmethod
    def drawFastHLine(self, x, y, w, c):
        self.startWrite()
        self.writeFastHLine(x, y, w, c)
        self.endWrite()

    @classmethod
    def fillRect(self, x, y, w, h, c):
        self.startWrite()
        self.writeFillRect(x, y, w, h, c)
        self.endWrite()

    @classmethod
    def fillScreen(self, c):
        self.fillRect(0, 0, self.width(), self.height(), c)

    @classmethod
    def drawLine(self, x0, y0, x1, y1, c):
        self.startWrite()
        self.writeLine(x0, y0, x1, y1, c)
        self.endWrite()

    @classmethod
    def drawRect(self, x, y, w, h, c):
        self.GFX.rect(x, y, w, h, c)

    @classmethod
    def drawCircle(self, x, y, r, c):
        self.GFX.circle(x, y, r, c)

    @classmethod
    def fillCircle(self, x, y, r, c):
        self.GFX.fill_circle(x, y, r, c)

    @classmethod
    def drawTriangle(self, x0, y0, x1, y1, x2, y2, c):
        self.GFX.triangle(x0, y0, x1, y1, x2, y2, c)

    @classmethod
    def fillTriangle(self, x0, y0, x1, y1, x2, y2, c):
        self.GFX.fill_triangle(x0, y0, x1, y1, x2, y2, c)

    @classmethod
    def drawRoundRect(self, x, y, q, h, r, c):
        self.GFX.round_rect(x, y, q, h, r, c)

    @classmethod
    def fillRoundRect(self, x, y, q, h, r, c):
        self.GFX.fill_round_rect(x, y, q, h, r, c)

    @classmethod
    def setTextSize(self, s):
        self.textSize = s

    @classmethod
    def setFont(self, f):
        self.GFX.font = f

    @classmethod
    def printText(self, x, y, s, c=BLACK):
        self.GFX._very_slow_text(x, y, s, self.textSize, c)

    @classmethod
    def drawBitmap(self, x, y, data, w, h, c=BLACK):
        byteWidth = (w + 7) // 8
        byte = 0
        self.startWrite()
        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byteWidth + i // 8]
                if byte & 0x80:
                    self.writePixel(x + i, y + j, c)
        self.endWrite()
    
    @classmethod
    def gpioExpanderPin(self, pin, mode):
        return gpioPin(self._PCAL6416A, pin, mode)

    @classmethod
    def initSDCard(self):
        self.SDCardWake()
        try:
            os.mount(
                SDCard(
                    slot=3,
                    miso=Pin(12),
                    mosi=Pin(13),
                    sck=Pin(14),
                    cs=Pin(15)),
                "/sd"
            )
        except Exception as e:
            print("Sd card could not be read", str(e))

    @classmethod
    def SDCardSleep(self):
        self.SD_ENABLE.digitalWrite(1)
        time.sleep_ms(25)
    
    @classmethod
    def SDCardWake(self):
        self.SD_ENABLE.digitalWrite(0)
        time.sleep_ms(25)
    
    @classmethod
    def drawImageFile(self, x, y, path, invert=False):
        with open(path, "rb") as f:
            header14 = f.read(14)
            if header14[0] != 0x42 or header14[1] != 0x4D:
                return 0
            header40 = f.read(40)

            w = int(
                (header40[7] << 24)
                + (header40[6] << 16)
                + (header40[5] << 8)
                + header40[4]
            )
            h = int(
                (header40[11] << 24)
                + (header40[10] << 16)
                + (header40[9] << 8)
                + header40[8]
            )
            dataStart = int((header14[11] << 8) + header14[10])

            depth = int((header40[15] << 8) + header40[14])
            totalColors = int((header40[33] << 8) + header40[32])

            rowSize = 4 * ((depth * w + 31) // 32)

            if totalColors == 0:
                totalColors = 1 << depth

            palette = None

            if depth <= 8:
                palette = [0 for i in range(totalColors)]
                p = f.read(totalColors * 4)
                for i in range(totalColors):
                    palette[i] = (
                        54 * p[i * 4] + 183 * p[i * 4 + 1] + 19 * p[i * 4 + 2]
                    ) >> 14
            # print(palette)
            f.seek(dataStart)
            for j in range(h):
                # print(100 * j // h, "% complete")
                buffer = f.read(rowSize)
                for i in range(w):
                    val = 0
                    if depth == 1:
                        px = int(
                            invert
                            ^ (palette[0] < palette[1])
                            ^ bool(buffer[i >> 3] & (1 << (7 - i & 7)))
                        )
                        val = palette[px]
                    elif depth == 4:
                        px = (buffer[i >> 1] & (0x0F if i & 1 == 1 else 0xF0)) >> (
                            0 if i & 1 else 4
                        )
                        val = palette[px]
                        if invert:
                            val = 3 - val
                    elif depth == 8:
                        px = buffer[i]
                        val = palette[px]
                        if invert:
                            val = 3 - val
                    elif depth == 16:
                        px = (buffer[(i << 1) | 1] << 8) | buffer[(i << 1)]

                        r = (px & 0x7C00) >> 7
                        g = (px & 0x3E0) >> 2
                        b = (px & 0x1F) << 3

                        val = (54 * r + 183 * g + 19 * b) >> 14

                        if invert:
                            val = 3 - val
                    elif depth == 24:
                        r = buffer[i * 3]
                        g = buffer[i * 3 + 1]
                        b = buffer[i * 3 + 2]

                        val = (54 * r + 183 * g + 19 * b) >> 14

                        if invert:
                            val = 3 - val
                    elif depth == 32:
                        r = buffer[i * 4]
                        g = buffer[i * 4 + 1]
                        b = buffer[i * 4 + 2]

                        val = (54 * r + 183 * g + 19 * b) >> 14

                        if invert:
                            val = 3 - val

                    val >>= 1

                    self.drawPixel(x + i, y + h - j, val)

    @classmethod
    def read_battery(self):
        self.VBAT_EN.digitalWrite(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(5)
        value = self.VBAT.read()
        self.VBAT_EN.digitalWrite(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    @classmethod
    def drawColorImage(self, x, y, w, h, buf):
        scaled_w = int(-(-(w / 4.0) // 1))
        for i in range(h):
            for j in range(scaled_w):
                self.writePixel(4 * j + x, i + y, (buf[scaled_w * i + j] & 0xC0) >> 6)
                if 4 * j + x + 1 < w:
                    self.writePixel(4 * j + x + 1, i + y, (buf[scaled_w * i + j] & 0x30) >> 4)
                if 4 * j + x + 2 < w:
                    self.writePixel(4 * j + x + 2, i + y, (buf[scaled_w * i + j] & 0x0C) >> 2)
                if 4 * j + x + 3 < w:
                    self.writePixel(4 * j + x + 3, i + y, (buf[scaled_w * i + j] & 0x03))
