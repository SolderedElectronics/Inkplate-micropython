# MicroPython driver for Inkplate 6COLOR
# Contributed by: https://github.com/tve
# Copyright © 2020 by Thorsten von Eicken
import time
import os
from machine import ADC, I2C, SPI, Pin, SDCard
from micropython import const
from PCAL6416A import *
from shapes import Shapes
from machine import Pin as mPin
from gfx import GFX
from gfx_standard_font_01 import text_dict as std_font

# ===== Constants that change between the Inkplate 6 and 10

# Connections between ESP32 and color Epaper
EPAPER_RST_PIN = const(19)
EPAPER_DC_PIN = const(33)
EPAPER_CS_PIN = const(27)
EPAPER_BUSY_PIN = const(32)
EPAPER_CLK = const(18)
EPAPER_DIN = const(23)
VBAT_PIN = const(35)

# Timeout for init of epaper(1.5 sec in this case)
# INIT_TIMEOUT 1500

pixelMaskGLUT = [0xF, 0xF0]

# Epaper registers
PANEL_SET_REGISTER = "\x00"
POWER_SET_REGISTER = "\x01"
POWER_OFF_SEQ_SET_REGISTER = "\x03"
POWER_OFF_REGISTER = "\x04"
BOOSTER_SOFTSTART_REGISTER = "\x06"
DEEP_SLEEP_REGISTER = "\x07"
DATA_START_TRANS_REGISTER = "\x10"
DATA_STOP_REGISTER = "\x11"
DISPLAY_REF_REGISTER = "\x12"
IMAGE_PROCESS_REGISTER = "\x13"
PLL_CONTROL_REGISTER = "\x30"
TEMP_SENSOR_REGISTER = "\x40"
TEMP_SENSOR_EN_REGISTER = "\x41"
TEMP_SENSOR_WR_REGISTER = "\x42"
TEMP_SENSOR_RD_REGISTER = "\x43"
VCOM_DATA_INTERVAL_REGISTER = "\x50"
LOW_POWER_DETECT_REGISTER = "\x51"
RESOLUTION_SET_REGISTER = "\x61"
STATUS_REGISTER = "\x71"
VCOM_VALUE_REGISTER = "\x81"
VCM_DC_SET_REGISTER = "\x02"

# Epaper resolution and colors
D_COLS = const(600)
D_ROWS = const(448)

# User pins on PCAL6416A for Inkplate COLOR
IO_PIN_A0 = const(0)
IO_PIN_A1 = const(1)
IO_PIN_A2 = const(2)
IO_PIN_A3 = const(3)
IO_PIN_A4 = const(4)
IO_PIN_A5 = const(5)
IO_PIN_A6 = const(6)
IO_PIN_A7 = const(7)

IO_PIN_B0 = const(8)
IO_PIN_B1 = const(9)
IO_PIN_B2 = const(10)
IO_PIN_B3 = const(11)
IO_PIN_B4 = const(12)
IO_PIN_B5 = const(13)
IO_PIN_B6 = const(14)
IO_PIN_B7 = const(15)

RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04

class Inkplate:
    BLACK = const(0b00000000)  # 0
    WHITE = const(0b00000001)  # 1
    GREEN = const(0b00000010)  # 2
    BLUE = const(0b00000011)  # 3
    RED = const(0b00000100)  # 4
    YELLOW = const(0b00000101)  # 5
    ORANGE = const(0b00000110)  # 6

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    textSize = 1

    _panelState = False

    _framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    @classmethod
    def begin(self):
        self.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        self._PCAL6416A = PCAL6416A(self.wire)

        self.spi = SPI(2)

        self.spi.init(baudrate=2000000, firstbit=SPI.MSB, polarity=0, phase=0)

        self.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
        self.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT)
        self.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT)
        self.EPAPER_CS_PIN = Pin(EPAPER_CS_PIN, Pin.OUT)
        self.VBAT = ADC(Pin(35))
        self.VBAT.atten(ADC.ATTN_11DB)
        self.VBAT.width(ADC.WIDTH_12BIT)
        self.VBAT_EN = gpioPin(self._PCAL6416A, 9, modeOUTPUT)
        self.VBAT_EN.digitalWrite(0)

        # self.SD_ENABLE = gpioPin(self._PCAL6416A, 10, modeOUTPUT)

        self.framebuf = bytearray(D_ROWS * D_COLS // 2)

        self.GFX = GFX(
            D_COLS,
            D_ROWS,
            self.writePixel,
            self.writeFastHLine,
            self.writeFastVLine,
            self.writeFillRect,
            None,
            None,
        )

        self.resetPanel()

        _timeout = time.ticks_ms()
        while not self.EPAPER_BUSY_PIN.value() and (time.ticks_ms() - _timeout) < 10000:
            pass

        if not self.EPAPER_BUSY_PIN.value():
            return False

        self.sendCommand(PANEL_SET_REGISTER)
        self.sendData(b"\xef\x08")
        self.sendCommand(POWER_SET_REGISTER)
        self.sendData(b"\x37\x00\x23\x23")
        self.sendCommand(POWER_OFF_SEQ_SET_REGISTER)
        self.sendData(b"\x00")
        self.sendCommand(BOOSTER_SOFTSTART_REGISTER)
        self.sendData(b"\xc7\xc7\x1d")
        self.sendCommand(PLL_CONTROL_REGISTER)
        self.sendData(b"\x3c")
        self.sendCommand(TEMP_SENSOR_REGISTER)
        self.sendData(b"\x00")
        self.sendCommand(VCOM_DATA_INTERVAL_REGISTER)
        self.sendData(b"\x37")
        self.sendCommand(b"\x60")
        self.sendData(b"\x20")
        self.sendCommand(RESOLUTION_SET_REGISTER)
        self.sendData(b"\x02\x58\x01\xc0")
        self.sendCommand(b"\xE3")
        self.sendData(b"\xaa")

        time.sleep_ms(100)

        self.sendCommand(b"\x50")
        self.sendData(b"\x37")

        self.setPCALForLowPower()

        self._panelState = True

        return True

    def initSDCard(self):
        # self.SD_ENABLE.digitalWrite(0)
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
        except:
            print("Sd card could not be read")

    def SDCardSleep(self):
        # self.SD_ENABLE.digitalWrite(1)
        time.sleep_ms(5)

    def SDCardWake(self):
        # self.SD_ENABLE.digitalWrite(0)
        time.sleep_ms(5)

    @classmethod
    def setPCALForLowPower(self):

        for x in range(16):
            self._PCAL6416A.pinMode(int(x), modeOUTPUT)
            self._PCAL6416A.digitalWrite(int(x), 0)

    @classmethod
    def getPanelDeepSleepState(self):
        return self._panelState

    @classmethod
    def setPanelDeepSleepState(self, state):
        _panelState = False if state == 0 else True

        if _panelState:
            self.begin()
        else:
            time.sleep_ms(10)
            self.sendCommand(DEEP_SLEEP_REGISTER)
            self.sendData(b"\xA5")
            time.sleep_ms(100)
            EPAPER_RST_PIN.value(0)
            EPAPER_DC_PIN.value(0)
            EPAPER_CS_PIN.value(0)

    @classmethod
    def resetPanel(self):
        self.EPAPER_RST_PIN.value(0)
        time.sleep_ms(1)
        self.EPAPER_RST_PIN.value(1)
        time.sleep_ms(1)

    @classmethod
    def sendCommand(self, command):
        self.EPAPER_DC_PIN.value(0)
        self.EPAPER_CS_PIN.value(0)

        self.spi.write(command)

        self.EPAPER_CS_PIN.value(1)

    @classmethod
    def sendData(self, data):
        self.EPAPER_DC_PIN.value(1)
        self.EPAPER_CS_PIN.value(0)

        self.spi.write(data)

        self.EPAPER_CS_PIN.value(1)

    @classmethod
    def clearDisplay(self):
        self._framebuf = bytearray([0x11] * (D_COLS * D_ROWS // 2))

    @classmethod
    def display(self):
        if not self._panelState:
            return

        self.sendCommand(b"\x61")
        self.sendData(b"\x02\x58\x01\xc0")

        self.sendCommand(b"\x10")

        self.EPAPER_DC_PIN.value(1)
        self.EPAPER_CS_PIN.value(0)

        self.spi.write(self._framebuf)

        self.EPAPER_CS_PIN.value(1)

        self.sendCommand(POWER_OFF_REGISTER)
        while not self.EPAPER_BUSY_PIN.value():
            pass

        self.sendCommand(DISPLAY_REF_REGISTER)
        while not self.EPAPER_BUSY_PIN.value():
            pass

        self.sendCommand(POWER_OFF_REGISTER)
        while self.EPAPER_BUSY_PIN.value():
            pass

        time.sleep_ms(200)

    @classmethod
    def gpioExpanderPin(self, pin, mode):
        return gpioPin(self._PCAL6416A, pin, mode)

    @classmethod
    def rtc_dec_to_bcd(cls, val):
        return (val // 10 * 16) + (val % 10)

    @classmethod
    def rtc_bcd_to_dec(cls, val):
        return (val // 16 * 10) + (val % 16)

    @classmethod
    def rtc_set_time(cls, rtc_hour, rtc_minute, rtc_second):
        data = bytearray([
            RTC_RAM_by,
            170,  # Write in RAM 170 to know that RTC is set
            cls.rtc_dec_to_bcd(rtc_second),
            cls.rtc_dec_to_bcd(rtc_minute),
            cls.rtc_dec_to_bcd(rtc_hour)
        ])

        cls._i2c.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        rtcYear = rtc_yr - 2000

        data = bytearray([
            RTC_RAM_by,
            170,  # Write in RAM 170 to know that RTC is set
        ])

        cls._i2c.writeto(RTC_I2C_ADDR, data)

        data = bytearray([
            RTC_DAY_ADDR,
            cls.rtc_dec_to_bcd(rtc_day),
            cls.rtc_dec_to_bcd(rtc_weekday),
            cls.rtc_dec_to_bcd(rtc_month),
            cls.rtc_dec_to_bcd(rtcYear),
        ])

        cls._i2c.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_get_rtc_data(cls):
        cls._i2c.writeto(RTC_I2C_ADDR, bytearray([RTC_SECOND_ADDR]))
        data = cls._i2c.readfrom(RTC_I2C_ADDR, 7)

        rtc_second = cls.rtc_bcd_to_dec(data[0] & 0x7F)  # Ignore bit 7
        rtc_minute = cls.rtc_bcd_to_dec(data[1] & 0x7F)
        rtc_hour = cls.rtc_bcd_to_dec(data[2] & 0x3F)  # Ignore bits 7 & 6
        rtc_day = cls.rtc_bcd_to_dec(data[3] & 0x3F)
        rtc_weekday = cls.rtc_bcd_to_dec(data[4] & 0x07)  # Ignore bits 7,6,5,4 & 3
        rtc_month = cls.rtc_bcd_to_dec(data[5] & 0x1F)  # Ignore bits 7,6 & 5
        rtc_year = cls.rtc_bcd_to_dec(data[6]) + 2000

        return {
            'second': rtc_second,
            'minute': rtc_minute,
            'hour': rtc_hour,
            'day': rtc_day,
            'weekday': rtc_weekday,
            'month': rtc_month,
            'year': rtc_year
        }

    @classmethod
    def clean(self):
        if not self._panelState:
            return

        self.sendCommand(b"\x61")
        self.sendData(b"\x02\x58\x01\xc0")

        self.sendCommand(b"\x10")

        self.EPAPER_DC_PIN.value(1)
        self.EPAPER_CS_PIN.value(0)

        self.spi.write(bytearray(0x11 for x in range(D_COLS * D_ROWS // 2)))

        self.EPAPER_CS_PIN.value(1)

        self.sendCommand(POWER_OFF_REGISTER)
        while not self.EPAPER_BUSY_PIN.value():
            pass

        self.sendCommand(DISPLAY_REF_REGISTER)
        while not self.EPAPER_BUSY_PIN.value():
            pass

        self.sendCommand(POWER_OFF_REGISTER)
        while self.EPAPER_BUSY_PIN.value():
            pass

        time.sleep_ms(200)

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
            self.GFX.width = D_COLS
            self.GFX.height = D_ROWS
            self._width = D_COLS
            self._height = D_ROWS
        elif self.rotation == 1 or self.rotation == 3:
            self.GFX.width = D_ROWS
            self.GFX.height = D_COLS
            self._width = D_ROWS
            self._height = D_COLS

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
        if self.rotation == 1:
            x, y = y, x
            x = self.height() - x - 1
        elif self.rotation == 0:
            x = self.width() - x - 1
            y = self.height() - y - 1
        elif self.rotation == 3:
            x, y = y, x
            y = self.width() - y - 1

        _x = x // 2
        _x_sub = x % 2

        temp = self._framebuf[D_COLS * y // 2 + _x]
        self._framebuf[D_COLS * y // 2 + _x] = (pixelMaskGLUT[_x_sub] & temp) | \
                                               (c if _x_sub else c << 4)

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
    def setDisplayMode(self, mode):
        self.displayMode = mode

    @classmethod
    def selectDisplayMode(self, mode):
        self.displayMode = mode

    @classmethod
    def getDisplayMode(self):
        return self.displayMode

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
    def readBattery(self):
        self.VBAT_EN.digitalWrite(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(5)
        value = self.VBAT.read()
        self.VBAT_EN.digitalWrite(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

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

    def drawColorImage(self, x, y, width, height, image):
        for i in range(0, len(image)):
            # Unpack the byte into two pixel values
            pixel_value1 = (image[i] & 0b11110000) >> 4
            pixel_value2 = image[i] & 0b00001111

            # Calculate the x and y coordinates of the pixels
            x1 = (2*i) % width
            y1 = (2*i) // width
            x2 = (2*i + 1) % width
            y2 = (2*i + 1) // width

            # Check if the coordinates are within the image bounds
            if x1 < width and y1 < height:
                self.writePixel(x1 + x, y1 + y, pixel_value1)
            if x2 < width and y2 < height:
                self.writePixel(x2 + x, y2 + y, pixel_value2)
    
    def rtcSetTime(self, rtc_hour, rtc_minute, rtc_second):
        return _Inkplate.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtcSetDate(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return _Inkplate.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtcGetData(self):
        return _Inkplate.rtc_get_rtc_data()
