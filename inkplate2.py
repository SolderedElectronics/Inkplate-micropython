import time
import os
from machine import ADC, I2C, SPI, Pin
from micropython import const
from shapes import Shapes
from machine import Pin as mPin
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

# ePaper resolution
# For Inkplate2 height and width are swapped in relation to the default rotation
E_INK_HEIGHT = 212
E_INK_WIDTH = 104

E_INK_NUM_PIXELS = E_INK_HEIGHT * E_INK_WIDTH
E_INK_BUFFER_SIZE = E_INK_NUM_PIXELS // 8

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

    _framebuf_BW = bytearray([0xFF] * E_INK_BUFFER_SIZE)
    _framebuf_RED = bytearray([0xFF] * E_INK_BUFFER_SIZE)

    @classmethod
    def begin(self):
        self.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        self.spi = SPI(2)
        self._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        self._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))

        self.GFX = GFX(
            E_INK_HEIGHT,
            E_INK_WIDTH,
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

        # 3 is the default rotation for Inkplate 2
        self.setRotation(3)

        return True

    @classmethod
    def getPanelDeepSleepState(self):
        return self._panelState

    @classmethod
    def setPanelDeepSleepState(self, state):

        # False wakes the panel up
        # True puts it to sleep
        if not state:
            self.spi.init(baudrate=20000000, firstbit=SPI.MSB,
                          polarity=0, phase=0)
            self.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
            self.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT)
            self.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT)
            self.EPAPER_CS_PIN = Pin(EPAPER_CS_PIN, Pin.OUT)
            time.sleep_ms(10)
            self.resetPanel()

            # Reinit the panel
            self.sendCommand(b"\x04")
            _timeout = time.ticks_ms()
            while not self.EPAPER_BUSY_PIN.value() and (time.ticks_ms() - _timeout) < busy_timeout_ms:
                pass

            self.sendCommand(b"\x00")
            self.sendData(b"\x0f")
            self.sendData(b"\x89")
            self.sendCommand(b"\x61")
            self.sendData(b"\x68")
            self.sendData(b"\x00")
            self.sendData(b"\xD4")
            self.sendCommand(b"\x50")
            self.sendData(b"\x77")

            self._panelState = True

            return True

        else:

            # Put the panel to sleep
            self.sendCommand(b"\x50")
            self.sendData(b"\xf7")
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
        time.sleep_ms(10)
        self.EPAPER_RST_PIN.value(1)
        time.sleep_ms(10)

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
        self._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        self._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))

    @classmethod
    def display(self):

        # Wake the display
        self.setPanelDeepSleepState(False)

        # Write b/w pixels
        self.sendCommand(b"\x10")
        self.sendData(self._framebuf_BW)

        # Write red pixels
        self.sendCommand(b"\x13")
        self.sendData(self._framebuf_RED)

        # Stop transfer
        self.sendCommand(b"\x11")
        self.sendData(b"\x00")

        # Refresh
        self.sendCommand(b"\x12")
        time.sleep_ms(5)

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
            x, y = y, x
            y = self.width() - y - 1
        elif self.rotation == 0:
            x = self.width() - x - 1
            y = self.height() - y - 1
        elif self.rotation == 1:
            x, y = y, x
            x = self.height() - x - 1
        elif self.rotation == 2:
            pass

        _x = x // 8
        _x_sub = x % 8
        _position = E_INK_WIDTH // 8 * y + _x

        # Clear both black and red frame buffer
        self._framebuf_BW[_position] |= (pixelMaskLUT[7 - _x_sub])
        self._framebuf_RED[_position] |= (pixelMaskLUT[7 - _x_sub])

        # Write the pixel to the according buffer
        if (c < 2):
            self._framebuf_BW[_position] &= ~(c << (7 - _x_sub))
        else:
            self._framebuf_RED[_position] &= ~(pixelMaskLUT[7 - _x_sub])

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
