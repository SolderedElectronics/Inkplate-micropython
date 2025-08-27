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
import machine

machine.freq(240000000)
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
    
    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN             = 1
    KERNEL_STUCKI          = 2
    KERNEL_BURKES          = 3

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

        self.spi.init(baudrate=20000000, firstbit=SPI.MSB, polarity=0, phase=0)

        self.EPAPER_BUSY_PIN = Pin(EPAPER_BUSY_PIN, Pin.IN)
        self.EPAPER_RST_PIN = Pin(EPAPER_RST_PIN, Pin.OUT)
        self.EPAPER_DC_PIN = Pin(EPAPER_DC_PIN, Pin.OUT)
        self.EPAPER_CS_PIN = Pin(EPAPER_CS_PIN, Pin.OUT)
        self.VBAT = ADC(Pin(35))
        self.VBAT.atten(ADC.ATTN_11DB)
        self.VBAT.width(ADC.WIDTH_12BIT)
        self.VBAT_EN = gpioPin(self._PCAL6416A, 9, modeOUTPUT)
        self.VBAT_EN.digitalWrite(0)
        
        self.cursor = [0,0]
        
        self.textColor= 0

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

    def initSDCard(self, fastBoot=False):
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
            if fastBoot == True:
                if machine.reset_cause() == machine.PWRON_RESET or machine.reset_cause() == machine.HARD_RESET or machine.reset_cause() == machine.WDT_RESET:
                    machine.soft_reset()
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
    def setPanelDeepSleep(self, state: bool) -> bool:
        if not state:
            # Wake the panel from deep sleep

            # Configure pins (self.EPAPER_* are assumed to be Pin objects)
            self.EPAPER_BUSY_PIN.init(self.EPAPER_BUSY_PIN.IN)
            self.EPAPER_RST_PIN.init(self.EPAPER_RST_PIN.OUT)
            self.EPAPER_DC_PIN.init(self.EPAPER_DC_PIN.OUT)
            self.EPAPER_CS_PIN.init(self.EPAPER_CS_PIN.OUT)

            # De-select epaper to charge capacitors
            self.EPAPER_DC_PIN.value(1)
            self.EPAPER_CS_PIN.value(1)

            # Wait a little
            time.sleep_ms(100)

            # Reset epaper
            self.resetPanel()

            # Wait until panel is ready
            start_time = time.ticks_ms()
            while (not self.EPAPER_BUSY_PIN.value()) and (time.ticks_diff(time.ticks_ms(), start_time) < 1500):
                pass

            if not self.EPAPER_BUSY_PIN.value():
                return False

            # Send initialization commands
            panel_set_data = bytearray([0xEF, 0x08])
            self.sendCommand(PANEL_SET_REGISTER)
            self.sendData(panel_set_data)

            power_set_data = bytearray([0x37, 0x00, 0x05, 0x05])
            self.sendCommand(POWER_SET_REGISTER)
            self.sendData(power_set_data)

            self.sendCommand(POWER_OFF_SEQ_SET_REGISTER)
            self.sendData(bytearray([0x00]))

            booster_softstart_data = bytearray([0xC7, 0xC7, 0x1D])
            self.sendCommand(BOOSTER_SOFTSTART_REGISTER)
            self.sendData(booster_softstart_data)

            self.sendCommand(TEMP_SENSOR_EN_REGISTER)
            self.sendData(bytearray([0x00]))

            self.sendCommand(VCOM_DATA_INTERVAL_REGISTER)
            self.sendData(bytearray([0x37]))

            self.sendCommand("\x60")
            self.sendData(bytearray([0x20]))

            res_set_data = bytearray([0x02, 0x58, 0x01, 0xC0])
            self.sendCommand(RESOLUTION_SET_REGISTER)
            self.sendData(res_set_data)

            self.sendCommand("\xE3")
            self.sendData(bytearray([0xAA]))

            time.sleep_ms(100)
            self.sendCommand(VCOM_DATA_INTERVAL_REGISTER)
            self.sendData(bytearray([0x37]))

            return True
        else:
            # Put the panel to deep sleep
            time.sleep_ms(10)
            self.sendCommand(DEEP_SLEEP_REGISTER)
            self.sendData(bytearray([0xA5]))
            time.sleep_ms(100)

            self.EPAPER_RST_PIN.value(0)
            time.sleep_ms(100)
            self.EPAPER_DC_PIN.value(0)
            self.EPAPER_CS_PIN.value(0)

            # SPI deinit removed per instructions

            # Set SPI pins low
            #self.EPAPER_CLK.init(self.EPAPER_CLK.OUT)
            #self.EPAPER_DIN.init(self.EPAPER_DIN.OUT)
            #self.EPAPER_CLK.value(0)
            #self.EPAPER_DIN.value(0)

            return True

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
    @micropython.native
    def display(self):
        self.setPanelDeepSleep(False)

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
        
        self.setPanelDeepSleep(True)

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

        cls.wire.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        rtcYear = rtc_yr - 2000

        data = bytearray([
            RTC_RAM_by,
            170,  # Write in RAM 170 to know that RTC is set
        ])

        cls.wire.writeto(RTC_I2C_ADDR, data)

        data = bytearray([
            RTC_DAY_ADDR,
            cls.rtc_dec_to_bcd(rtc_day),
            cls.rtc_dec_to_bcd(rtc_weekday),
            cls.rtc_dec_to_bcd(rtc_month),
            cls.rtc_dec_to_bcd(rtcYear),
        ])

        cls.wire.writeto(RTC_I2C_ADDR, data)

    @classmethod
    def rtc_get_rtc_data(cls):
        cls.wire.writeto(RTC_I2C_ADDR, bytearray([RTC_SECOND_ADDR]))
        data = cls.wire.readfrom(RTC_I2C_ADDR, 7)

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
    @micropython.native
    def writePixel(self, x, y, c):
        w = self.width()
        h = self.height()
        
        if x < 0 or y < 0 or x >= w or y >= h:
            return

        r = self.rotation
        if r == 0:
            x = w - x - 1
            y = h - y - 1
        elif r == 1:
            x, y = h - y - 1, x
        elif r == 3:
            x, y = y, w - x - 1
        # r == 2: no change needed

        idx = (D_COLS * y) >> 1
        shift = (x & 1) * 4
        mask = pixelMaskGLUT[x & 1]

        self._framebuf[idx + (x >> 1)] = (self._framebuf[idx + (x >> 1)] & mask) | (c << (4 - shift))



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
    def setTextColor(self, c):
        self.textColor = c

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

    def resetCursor(self):
        self.cursor=[0,0]

    def setCursor(self, x, y):
        self.cursor=[x,y]

    def printText(self, x, y, s):
        self.GFX._print_text(self._framebuf,x, y, s, self.textSize, self.textColor, text_wrap=self.wrap_text)
            
    def println(self, text):
        self.cursor,line_height = self.GFX._print_text(self._framebuf,self.cursor[0], self.cursor[1], text, self.textSize, self.textColor, text_wrap=self.wrap_text)
        
    def print(self, text):
        self.cursor,line_height = self.GFX._print_text(self._framebuf,self.cursor[0], self.cursor[1], text, self.textSize, self.textColor, text_wrap=self.wrap_text)
        
    def wrap_text(self,text, max_chars):
        lines = []
        for paragraph in text.split('\n'):
            while len(paragraph) > max_chars:
                # Find last space within limit
                wrap_at = paragraph.rfind(' ', 0, max_chars)
                if wrap_at == -1:
                    wrap_at = max_chars
                lines.append(paragraph[:wrap_at])
                paragraph = paragraph[wrap_at:].lstrip()
            if paragraph:
                lines.append(paragraph)
        return lines
    
    def drawTextBox(self, x0, y0, x1, y1, text, line_height=20, text_size=None):
        
        if text_size != None:
            self.setTextSize(text_size)
        max_width=x1-x0
        char_width = 6 * self.textSize  # rough estimate
        max_chars = max_width // char_width
        lines = self.wrap_text(text, max_chars)
        max_height=y1
        y=y0
        for line in lines:
            if y > y1 - 2*line_height:
                s=list(line)
                s[-1]='.'
                s[-2]='.'
                s[-3]='.'
                s="".join(s)
                self.printText(x0, y, s)
                break
            self.printText(x0, y, line)
            y += line_height

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
        return self.rtc_set_time(rtc_hour, rtc_minute, rtc_second)

    def rtcSetDate(self, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        return self.rtc_set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    def rtcGetData(self):
        return self.rtc_get_rtc_data()
    
    def drawImage(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """
        Draw an image from either web URL or local file system
        Args:
            path: Either a web URL (http/https) or local file path
            x0, y0: Coordinates for top-left corner of image
            dither: Whether to apply dithering
            kernel_type: Dithering kernel type (0=Floyd-Steinberg, etc.)
            invert: Invert colors
        """
        # Check if path is a web URL
        if path.startswith(('http://', 'https://')):
            # Determine image type from URL
            if path.lower().endswith('.bmp'):
                self.drawBMPFromWeb(path, x0, y0, invert, dither)
            elif path.lower().endswith('.jpg') or path.lower().endswith('.jpeg'):
                self.drawJPGFromWeb(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith('.png'):
                self.drawPNGFromWeb(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            # Handle local file
            if path.lower().endswith('.bmp'):
                self.drawBMPFromSd(path, x0, y0,invert, dither)
            elif path.lower().endswith('.jpg') or path.lower().endswith('.jpeg'):
                self.drawJPGFromSd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith('.png'):
                self.drawPNGFromSd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")
    
    
    
    def drawJPGFromSd(self, path, x0=0, y0=0, invert=False, dither:bool=False, kernel_type:int=0):
        import jpeg
        import gc
        import time
        
        try:
            # 1. Initialize decoder

            decoder = jpeg.Decoder(rotation=180, format="CbYCrY", clipper_width=self._width, clipper_height=self._height)
            
            # 2. Read file
            with open(path, "rb") as f:
                jpeg_data = f.read()
            
            # 3. Get image info before decoding
            try:
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            except Exception as e:
                print(e)
                decoder = jpeg.Decoder(rotation=0, format="CbYCrY")
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            

                
            
            # 4. Decode image
            decoded = decoder.decode(jpeg_data)
            
            from array import array
            
            draw_width = self._width
            err_cur, err_next = array('h', (0 for _ in range(draw_width*3))), array('h', (0 for _ in range(draw_width*3)))
            
            Inkplate.writeImage(self._framebuf, x0, y0, width, height, decoded, invert, dither, kernel_type, err_cur, err_next)
            
            gc.collect()
            
        
        except Exception as e:
            print("\nJPEG Decode error:", e)
            raise
    
    # Color palette (7 colors)
    palette = [
            (0, 0, 0),        # 0 black
            (255, 255, 255),  # 1 white
            (0, 255, 0),      # 2 green
            (0, 0, 255),      # 3 blue
            (255, 0, 0),      # 4 red
            (255, 255, 0),    # 5 yellow
            (255, 165, 0)     # 6 orange
        ]
        
    def drawJPGFromSd(self, path, x0=0, y0=0, invert=False, dither:bool=False, kernel_type:int=0):
        import jpeg
        import gc
        import time
        
        try:
            # 1. Initialize decoder

            decoder = jpeg.Decoder(rotation=180, format="RGB565_LE", clipper_width=self._width, clipper_height=self._height)
            
            # 2. Read file
            with open(path, "rb") as f:
                jpeg_data = f.read()
            
            # 3. Get image info before decoding
            try:
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            except Exception as e:
                print(e)
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]
                
            # 4. Decode image
            decoded = decoder.decode(jpeg_data)
            
            
            Inkplate.writeImage(self._framebuf, x0, y0, width, height, decoded, invert, dither, kernel_type)
            
            gc.collect()
            
        
        except Exception as e:
            print("\nJPEG Decode error:", e)
            raise
    

    @staticmethod
    @micropython.viper
    def writeImage(framebuf: ptr8, x0: int, y0: int, width: int, height: int, imagedata: ptr8, invert: bool, dither: bool, kernel_type: int):
        _SCREEN_WIDTH = const(600)
        _SCREEN_HEIGHT = const(488)
        _BYTES_PER_ROW = const(_SCREEN_WIDTH // 2)  # 2 pixels per byte (4bpp)

        # Dithering kernels (dx, dy, wt) — weights will be pre-scaled (<<6) to avoid divides
        fs_dx = (1, -1, 0, 1)
        fs_dy = (0,  1, 1, 1)
        fs_wt = (7,  3, 5, 1);  fs_div = 16

        jjn_dx = (1, 2, -2, -1, 0, 1, 2)
        jjn_dy = (0, 0,  1,  1, 1, 1, 1)
        jjn_wt = (7, 5,  3,  5, 7, 5, 3); jjn_div = 48

        stucki_dx = (1, 2, -2, -1, 0, 1, 2)
        stucki_dy = (0, 0,  1,  1, 1, 1, 1)
        stucki_wt = (8, 4,  2,  4, 8, 4, 2); stucki_div = 42

        burkes_dx = (1, 2, -2, -1, 0, 1, 2)
        burkes_dy = (0, 0,  1,  1, 1, 1, 1)
        burkes_wt = (8, 4,  2,  4, 8, 4, 2); burkes_div = 32

        # Palette flattened to avoid tuple indexing overhead
        # index: 0..6 -> (r,g,b)
        p0r = 0   ; p0g = 0   ; p0b = 0     # black
        p1r = 255 ; p1g = 255 ; p1b = 255   # white
        p2r = 0   ; p2g = 255 ; p2b = 0     # green
        p3r = 0   ; p3g = 0   ; p3b = 255   # blue
        p4r = 255 ; p4g = 0   ; p4b = 0     # red
        p5r = 255 ; p5g = 255 ; p5b = 0     # yellow
        p6r = 255 ; p6g = 165 ; p6b = 0     # orange

        draw_width: int = width if (x0 + width) <= _SCREEN_WIDTH else _SCREEN_WIDTH - x0
        draw_height: int = height if (y0 + height) <= _SCREEN_HEIGHT else _SCREEN_HEIGHT - y0

        inv_mask: int = 0x0F if invert else 0x00
        
        # Select kernel and pre-scale weights by 64 (>>6 later)
        dx0:int = 0; dx1:int = 0; dx2:int = 0; dx3:int = 0
        dx4:int = 0; dx5:int = 0; dx6:int = 0
        dy0:int = 0; dy1:int = 0; dy2:int = 0; dy3:int = 0
        dy4:int = 0; dy5:int = 0; dy6:int = 0

        # Prepare dithering
        kernel_len: int = 0
        if dither:
            errbuf_size: int = draw_width * 3  # RGB error per pixel (signed byte in [-128,127] encoded as 0..255)
            error_current = bytearray(errbuf_size)
            error_next = bytearray(errbuf_size)
            error_current_ptr = ptr8(error_current)
            error_next_ptr = ptr8(error_next)

            # Select kernel and pre-scale weights by 64 (>>6 later)
            # Select kernel and pre-scale weights by 64 (>>6 later)
            if kernel_type == 1:
                # Jarvis, Judice, Ninke
                dx0 = int(jjn_dx[0]); dy0 = int(jjn_dy[0])
                dx1 = int(jjn_dx[1]); dy1 = int(jjn_dy[1])
                dx2 = int(jjn_dx[2]); dy2 = int(jjn_dy[2])
                dx3 = int(jjn_dx[3]); dy3 = int(jjn_dy[3])
                dx4 = int(jjn_dx[4]); dy4 = int(jjn_dy[4])
                dx5 = int(jjn_dx[5]); dy5 = int(jjn_dy[5])
                dx6 = int(jjn_dx[6]); dy6 = int(jjn_dy[6])
                coeff0:int = (int(jjn_wt[0]) << 6) // jjn_div
                coeff1:int = (int(jjn_wt[1]) << 6) // jjn_div
                coeff2:int = (int(jjn_wt[2]) << 6) // jjn_div
                coeff3:int = (int(jjn_wt[3]) << 6) // jjn_div
                coeff4:int = (int(jjn_wt[4]) << 6) // jjn_div
                coeff5:int = (int(jjn_wt[5]) << 6) // jjn_div
                coeff6:int = (int(jjn_wt[6]) << 6) // jjn_div
                kernel_len:int = 7

            elif kernel_type == 2:
                # Stucki
                dx0 = int(stucki_dx[0]); dy0 = int(stucki_dy[0])
                dx1 = int(stucki_dx[1]); dy1 = int(stucki_dy[1])
                dx2 = int(stucki_dx[2]); dy2 = int(stucki_dy[2])
                dx3 = int(stucki_dx[3]); dy3 = int(stucki_dy[3])
                dx4 = int(stucki_dx[4]); dy4 = int(stucki_dy[4])
                dx5 = int(stucki_dx[5]); dy5 = int(stucki_dy[5])
                dx6 = int(stucki_dx[6]); dy6 = int(stucki_dy[6])
                coeff0:int = (int(stucki_wt[0]) << 6) // stucki_div
                coeff1:int = (int(stucki_wt[1]) << 6) // stucki_div
                coeff2:int = (int(stucki_wt[2]) << 6) // stucki_div
                coeff3:int = (int(stucki_wt[3]) << 6) // stucki_div
                coeff4:int = (int(stucki_wt[4]) << 6) // stucki_div
                coeff5:int = (int(stucki_wt[5]) << 6) // stucki_div
                coeff6:int = (int(stucki_wt[6]) << 6) // stucki_div
                kernel_len:int = 7

            elif kernel_type == 3:
                # Burkes
                dx0 = int(burkes_dx[0]); dy0 = int(burkes_dy[0])
                dx1 = int(burkes_dx[1]); dy1 = int(burkes_dy[1])
                dx2 = int(burkes_dx[2]); dy2 = int(burkes_dy[2])
                dx3 = int(burkes_dx[3]); dy3 = int(burkes_dy[3])
                dx4 = int(burkes_dx[4]); dy4 = int(burkes_dy[4])
                dx5 = int(burkes_dx[5]); dy5 = int(burkes_dy[5])
                dx6 = int(burkes_dx[6]); dy6 = int(burkes_dy[6])
                coeff0:int = (int(burkes_wt[0]) << 6) // burkes_div
                coeff1:int = (int(burkes_wt[1]) << 6) // burkes_div
                coeff2:int = (int(burkes_wt[2]) << 6) // burkes_div
                coeff3:int = (int(burkes_wt[3]) << 6) // burkes_div
                coeff4:int = (int(burkes_wt[4]) << 6) // burkes_div
                coeff5:int = (int(burkes_wt[5]) << 6) // burkes_div
                coeff6:int = (int(burkes_wt[6]) << 6) // burkes_div
                kernel_len:int = 7

            else:
                # Floyd–Steinberg
                dx0 = int(fs_dx[0]); dy0 = int(fs_dy[0])
                dx1 = int(fs_dx[1]); dy1 = int(fs_dy[1])
                dx2 = int(fs_dx[2]); dy2 = int(fs_dy[2])
                dx3 = int(fs_dx[3]); dy3 = int(fs_dy[3])
                coeff0:int = (int(fs_wt[0]) << 6) // fs_div
                coeff1:int = (int(fs_wt[1]) << 6) // fs_div
                coeff2:int = (int(fs_wt[2]) << 6) // fs_div
                coeff3:int = (int(fs_wt[3]) << 6) // fs_div
                kernel_len:int = 4


        else:
            # Dummy pointers to satisfy types, not used
            error_current_ptr = ptr8(bytearray(0))
            error_next_ptr = ptr8(bytearray(0))

        row:int = 0
        while row < draw_height:
            fb_row_pos: int = (y0 + row) * _BYTES_PER_ROW + (x0 // 2)
            img_row_start: int = row * width * 2

            col:int = 0
            while col < draw_width:
                pix_grp:int = 2 if (col + 2) <= draw_width else draw_width - col
                packed:int = 0

                i:int = 0
                while i < pix_grp:
                    idx:int = img_row_start + ((col + i) * 2)
                    pixel:int = imagedata[idx] | (imagedata[idx + 1] << 8)

                    # RGB565 -> RGB888 (bit expand)
                    r_:int = (pixel >> 8) & 0xF8
                    g_:int = (pixel >> 3) & 0xFC
                    b_:int = (pixel << 3) & 0xF8
                    r_ |= r_ >> 5
                    g_ |= g_ >> 6
                    b_ |= b_ >> 5

                    if dither:
                        epos:int = (col + i) * 3
                        # decode signed byte: s = b-256 if b>127 else b
                        er:int = error_current_ptr[epos]
                        if er > 127:
                            er -= 256
                        eg:int = error_current_ptr[epos + 1]
                        if eg > 127:
                            eg -= 256
                        eb:int = error_current_ptr[epos + 2]
                        if eb > 127:
                            eb -= 256

                        r_ += er
                        g_ += eg
                        b_ += eb
                        # clamp 0..255 manually
                        if r_ < 0: r_ = 0
                        elif r_ > 255: r_ = 255
                        if g_ < 0: g_ = 0
                        elif g_ > 255: g_ = 255
                        if b_ < 0: b_ = 0
                        elif b_ > 255: b_ = 255

                    # Unrolled nearest-color search over 7 palette entries
                    best_idx:int = 0
                    # start with black
                    dr:int = r_ - 0   ; dg:int = g_ - 0   ; db:int = b_ - 0
                    best_dist:int = dr*dr + dg*dg + db*db

                    # white
                    dr = r_ - 255 ; dg = g_ - 255 ; db = b_ - 255
                    dist:int = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 1

                    # green
                    dr = r_ - 0   ; dg = g_ - 255 ; db = b_ - 0
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 2

                    # blue
                    dr = r_ - 0   ; dg = g_ - 0   ; db = b_ - 255
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 3

                    # red
                    dr = r_ - 255 ; dg = g_ - 0   ; db = b_ - 0
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 4

                    # yellow
                    dr = r_ - 255 ; dg = g_ - 255 ; db = b_ - 0
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 5

                    # orange
                    dr = r_ - 255 ; dg = g_ - 165 ; db = b_ - 0
                    dist = dr*dr + dg*dg + db*db
                    if dist < best_dist:
                        best_dist = dist ; best_idx = 6

                    # pack 4bpp
                    val:int = best_idx ^ inv_mask
                    if i == 0:
                        packed = (val << 4)
                    else:
                        packed |= val

                    if dither:
                        # Get chosen palette RGB
                        if best_idx == 0:
                            pr = 0   ; pg = 0   ; pb = 0
                        elif best_idx == 1:
                            pr = 255 ; pg = 255 ; pb = 255
                        elif best_idx == 2:
                            pr = 0   ; pg = 255 ; pb = 0
                        elif best_idx == 3:
                            pr = 0   ; pg = 0   ; pb = 255
                        elif best_idx == 4:
                            pr = 255 ; pg = 0   ; pb = 0
                        elif best_idx == 5:
                            pr = 255 ; pg = 255 ; pb = 0
                        else:
                            pr = 255 ; pg = 165 ; pb = 0

                        # quantization error
                        drq:int = r_ - pr
                        dgq:int = g_ - pg
                        dbq:int = b_ - pb

                        # diffuse error — branchless across kernel_len (4 or 7)
                        # helper to write one target (signed byte encode back to 0..255)
                        @micropython.viper
                        def _accum(error_current_ptr: ptr8, error_next_ptr: ptr8,
                                   nx: int, ny: int, row: int, draw_width: int, draw_height: int,
                                   dyv: int, k: int, cr: int, cg: int, cb: int):
                            # bounds check
                            if nx < 0 or nx >= draw_width or ny < 0 or ny >= draw_height:
                                return

                            # choose which buffer (same row or next row)
                            target: ptr8 = error_next_ptr if dyv else error_current_ptr
                            tpos: int = nx * 3

                            # read signed bytes
                            tr: int = target[tpos]
                            if tr > 127:
                                tr -= 256
                            tg: int = target[tpos + 1]
                            if tg > 127:
                                tg -= 256
                            tb: int = target[tpos + 2]
                            if tb > 127:
                                tb -= 256

                            # add scaled error
                            tr += (cr * k) >> 6
                            tg += (cg * k) >> 6
                            tb += (cb * k) >> 6

                            # clamp
                            if tr < -128: tr = -128
                            elif tr > 127: tr = 127
                            if tg < -128: tg = -128
                            elif tg > 127: tg = 127
                            if tb < -128: tb = -128
                            elif tb > 127: tb = 127

                            # re-encode signed byte to 0..255
                            target[tpos]     = tr + 256 if tr < 0 else tr
                            target[tpos + 1] = tg + 256 if tg < 0 else tg
                            target[tpos + 2] = tb + 256 if tb < 0 else tb


                        nx0:int = col + i + dx0; dy0:int = dy0
                        _accum(error_current_ptr, error_next_ptr,
                               nx0, row + dy0, row, draw_width, draw_height,
                               dy0, coeff0, drq, dgq, dbq)

                        nx1:int = col + i + dx1; dy1:int = dy1
                        _accum(error_current_ptr, error_next_ptr,
                               nx1, row + dy1, row, draw_width, draw_height,
                               dy1, coeff1, drq, dgq, dbq)

                        nx2:int = col + i + dx2; dy2:int = dy2
                        _accum(error_current_ptr, error_next_ptr,
                               nx2, row + dy2, row, draw_width, draw_height,
                               dy2, coeff2, drq, dgq, dbq)

                        nx3:int = col + i + dx3; dy3:int = dy3
                        _accum(error_current_ptr, error_next_ptr,
                               nx3, row + dy3, row, draw_width, draw_height,
                               dy3, coeff3, drq, dgq, dbq)

                        if kernel_len == 7:
                            nx4:int = col + i + dx4; dy4:int = dy4
                            _accum(error_current_ptr, error_next_ptr,
                                   nx4, row + dy4, row, draw_width, draw_height,
                                   dy4, coeff4, drq, dgq, dbq)

                            nx5:int = col + i + dx5; dy5:int = dy5
                            _accum(error_current_ptr, error_next_ptr,
                                   nx5, row + dy5, row, draw_width, draw_height,
                                   dy5, coeff5, drq, dgq, dbq)

                            nx6:int = col + i + dx6; dy6:int = dy6
                            _accum(error_current_ptr, error_next_ptr,
                                   nx6, row + dy6, row, draw_width, draw_height,
                                   dy6, coeff6, drq, dgq, dbq)



                    i += 1  # next pixel in pair

                # write packed nibble(s)
                fb_idx = fb_row_pos + (col // 2)
                if pix_grp == 2:
                    framebuf[fb_idx] = packed
                else:
                    if (col & 1) == 0:
                        framebuf[fb_idx] = (framebuf[fb_idx] & 0x0F) | packed
                    else:
                        framebuf[fb_idx] = (framebuf[fb_idx] & 0xF0) | (packed & 0x0F)

                col += 2

            if dither:
                # swap buffers (just swap pointers; arrays persist)
                tmp = error_current_ptr
                error_current_ptr = error_next_ptr
                error_next_ptr = tmp
                # clear next buffer (fast zero)
                i2:int = 0
                while i2 < errbuf_size:
                    error_next_ptr[i2] = 0
                    i2 += 1

            row += 1
    
    def drawPNGFromSd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        with open(path, 'rb') as f:
            png_data = f.read()

        width,height,png_data=Inkplate.png_to_rgb565(png_data, len(png_data))
        
        Inkplate.writeImage(self._framebuf, x0, y0, width, height, png_data, invert, dither, kernel_type)
        
        gc.collect()
    
    def drawPNGFromWeb(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests
        import ssl
        
        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")
            
            png_data = response.content
            response.close()
            
            width,height,png_data=Inkplate.png_to_rgb565(png_data, len(png_data))
        
            Inkplate.writeImage(self._framebuf, x0, y0, width, height, png_data, invert, dither, kernel_type)
            
            gc.collect()
        except Exception as e:
            print("Error in drawPNGFromWeb:", e)
            if 'response' in locals():
                response.close()

    def drawJPGFromWeb(self, url, x0=0, y0=0, invert=False, dither:bool=False, kernel_type:int=0):
        import jpeg
        import gc
        import urequests
        import ssl
        
        try:
            # 1. Initialize decoder
            decoder = jpeg.Decoder(rotation=180, format="RGB565_LE", clipper_width=self._width, clipper_height=self._height)
            
            # 2. Download the image (with timeout and basic error handling)
            response = urequests.get(url, timeout=20)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")
            
            jpeg_data = response.content
            response.close()
            
            try:
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            except Exception as e:
                print(e)
                decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
                width, height = decoder.get_img_info(jpeg_data)[0:2]
            
            # 4. Decode image
            decoded = decoder.decode(jpeg_data)
            

            Inkplate.writeImage(self._framebuf, x0, y0, width, height, decoded, invert, dither, kernel_type)
            
            gc.collect()
            
            
        except Exception as e:
            print("Error in drawJPGFromWeb:", e)
            if 'response' in locals():
                response.close()
            raise
        

    _PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

    @micropython.viper
    def png_to_rgb565(png_data: ptr8, png_len: int):
        import deflate
        import io
        import array
        from uctypes import addressof, bytearray_at
        # --- Signature check ---
        if (png_data[0] != 0x89 or png_data[1] != 0x50 or png_data[2] != 0x4E or 
            png_data[3] != 0x47 or png_data[4] != 0x0D or png_data[5] != 0x0A or 
            png_data[6] != 0x1A or png_data[7] != 0x0A):
            raise ValueError("Invalid PNG signature")

        # --- Parse chunks (your original logic) ---
        pos: int = 8
        width: int = 0
        height: int = 0
        color_type: int = 0
        idat_data = bytearray()

        while pos + 8 <= png_len:
            chunk_len: int = (png_data[pos] << 24) | (png_data[pos+1] << 16) | (png_data[pos+2] << 8) | png_data[pos+3]

            is_ihdr = (png_data[pos+4] == 0x49 and 
                       png_data[pos+5] == 0x48 and 
                       png_data[pos+6] == 0x44 and 
                       png_data[pos+7] == 0x52)

            is_idat = (png_data[pos+4] == 0x49 and 
                       png_data[pos+5] == 0x44 and 
                       png_data[pos+6] == 0x41 and 
                       png_data[pos+7] == 0x54)

            is_iend = (png_data[pos+4] == 0x49 and 
                       png_data[pos+5] == 0x45 and 
                       png_data[pos+6] == 0x4E and 
                       png_data[pos+7] == 0x44)

            chunk_start: int = pos + 8

            if is_ihdr:
                width  = (png_data[chunk_start]   << 24) | (png_data[chunk_start+1] << 16) | (png_data[chunk_start+2] << 8) | png_data[chunk_start+3]
                height = (png_data[chunk_start+4] << 24) | (png_data[chunk_start+5] << 16) | (png_data[chunk_start+6] << 8) | png_data[chunk_start+7]
                color_type = png_data[chunk_start+9]
                if color_type != 2 and color_type != 6:
                    raise ValueError("Unsupported PNG color type")

            elif is_idat:
                # Original safe byte-by-byte copy
                idat_chunk = bytearray(chunk_len)
                i: int = 0
                while i < chunk_len:
                    idat_chunk[i] = png_data[chunk_start + i]
                    i += 1
                idat_data += idat_chunk

            elif is_iend:
                break

            pos += chunk_len + 12

        if width == 0 or height == 0:
            raise ValueError("PNG missing IHDR chunk")
        if not idat_data:
            raise ValueError("PNG missing IDAT chunk")

        # --- Setup decoding ---
        bpp: int = 3 if color_type == 2 else 4
        row_size: int = width * bpp
        stride: int = row_size + 1

        rgb565_data = array.array('H', bytearray(width * height * 2))
        rgb565_ptr = ptr16(addressof(rgb565_data))

        idat_mv = bytearray_at(addressof(idat_data), len(idat_data))
        dstream = deflate.DeflateIO(io.BytesIO(idat_mv))

        cur_buf = bytearray(row_size)
        prev_buf = bytearray(row_size)
        cur = ptr8(addressof(cur_buf))
        prev = ptr8(addressof(prev_buf))

        # zero previous row
        i: int = 0
        while i < row_size:
            prev[i] = 0
            i += 1

        # --- Main loop ---
        y: int = 0
        while y < height:
            raw = dstream.read(stride)
            if not raw or int(len(raw)) != stride:
                raise ValueError("Invalid PNG row data")

            raw_ptr = ptr8(addressof(raw))
            filt: int = raw_ptr[0]
            rp = ptr8(int(raw_ptr) + 1)

            # --- Filtering ---
            x: int = 0
            while x < row_size:
                v: int = rp[x]
                if filt == 1:  # Sub
                    if x >= bpp:
                        v = (v + cur[x - bpp]) & 0xFF
                elif filt == 2:  # Up
                    v = (v + prev[x]) & 0xFF
                elif filt == 3:  # Average
                    a = cur[x - bpp] if x >= bpp else 0
                    b = prev[x]
                    v = (v + ((a + b) >> 1)) & 0xFF
                elif filt == 4:  # Paeth
                    a = cur[x - bpp] if x >= bpp else 0
                    b = prev[x]
                    c = prev[x - bpp] if x >= bpp else 0
                    p = a + b - c
                    pa = p - a if p >= a else a - p
                    pb = p - b if p >= b else b - p
                    pc = p - c if p >= c else c - p
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    v = (v + pred) & 0xFF
                cur[x] = v
                x += 1

            # --- Convert to RGB565 ---
            row_off: int = (height - 1 - y) * width  # flip vertically
            if bpp == 3:  # RGB
                x = 0
                while x < width:
                    i = x * 3
                    r = cur[i]; g = cur[i+1]; b = cur[i+2]
                    rgb565_ptr[row_off + (width - 1 - x)] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    x += 1
            else:  # RGBA
                x = 0
                while x < width:
                    i = x * 4
                    r = cur[i]; g = cur[i+1]; b = cur[i+2]; a = cur[i+3]
                    if a < 255:
                        r = (r * a) // 255
                        g = (g * a) // 255
                        b = (b * a) // 255
                    rgb565_ptr[row_off + (width - 1 - x)] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    x += 1

            # swap buffers
            tmp = cur
            cur = prev
            prev = tmp

            y += 1

        return (width, height, rgb565_data)
    
    
    def drawBMPFromSd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        gc.collect()
        with open(path, 'rb') as f:
            bmp_data = f.read()

        width,height,bmp_data=Inkplate.bmp24_to_rgb565(bmp_data, len(bmp_data))
        
        Inkplate.writeImage(self._framebuf, x0, y0, width, height, bmp_data, invert, dither, kernel_type)
        del bmp_data
        gc.collect()
        
    def drawBMPFromWeb(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type = 0):
        """Display a BMP image downloaded from the web
        
        Args:
            bmp_data (bytes): Raw BMP file data
            x0 (int): X position to start drawing
            y0 (int): Y position to start drawing
            invert (bool): Whether to invert colors
            dither (bool): Whether to apply dithering
        """
        import gc
        import urequests
        import ssl
    
        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}")
            
            bmp_data = response.content
            response.close()
            width,height,bmp_data=Inkplate.bmp24_to_rgb565(bmp_data, len(bmp_data))
        
            Inkplate.writeImage(self._framebuf, x0, y0, width, height, bmp_data, invert, dither, kernel_type)
            del bmp_data
            gc.collect()
        except Exception as e:
            print("Error in drawBMPFromWeb:", e)
            if 'response' in locals():
                response.close()
    

    
    @micropython.viper
    def bmp24_to_rgb565(bmp_data: ptr8, bmp_len: int):
        # keep imports inside the function per your environment
        from uctypes import addressof
        
        @micropython.viper
        def le32_and_sign(data: ptr8, off: int):
            b0: int = data[off]
            b1: int = data[off+1]
            b2: int = data[off+2]
            b3: int = data[off+3]
            uval: int = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
            top_down: int = 0
            if b3 & 0x80:    # negative
                top_down = 1
                # absolute value: two’s complement, but we can do (0 - uval)
                uval = -uval
            return uval, top_down

        # --- File header checks (14 bytes) ---
        # 'BM'
        if bmp_len < 54 or bmp_data[0] != 0x42 or bmp_data[1] != 0x4D:
            raise ValueError("Invalid BMP signature")

        # Little-endian helpers (inline)
        # le32 at offset 'o'
        o: int = 10
        pixel_ofs: int = (bmp_data[o] |
                          (bmp_data[o+1] << 8) |
                          (bmp_data[o+2] << 16) |
                          (bmp_data[o+3] << 24))

        # --- DIB header (assume BITMAPINFOHEADER >= 40 bytes) ---
        dib_sz: int = (bmp_data[14] |
                       (bmp_data[15] << 8) |
                       (bmp_data[16] << 16) |
                       (bmp_data[17] << 24))
        if dib_sz < 40:
            raise ValueError("Unsupported DIB header")

        # width (int32 le)
        w_off: int = 18
        width: int = (bmp_data[w_off] |
                      (bmp_data[w_off+1] << 8) |
                      (bmp_data[w_off+2] << 16) |
                      (bmp_data[w_off+3] << 24))
        if width <= 0:
            raise ValueError("Unsupported BMP width")

        # height (int32 le, may be negative for top-down)
        h_off: int = 22
        b0: int = bmp_data[h_off]
        b1: int = bmp_data[h_off+1]
        b2: int = bmp_data[h_off+2]
        b3: int = bmp_data[h_off+3]
        height_le: int = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

        top_down: int = 0
        if b3 & 0x80:     # check sign bit
            top_down = 1
            abs_height: int = -height_le   # safe negation, no big mask
        else:
            abs_height = height_le

        if abs_height <= 0:
            raise ValueError("Unsupported BMP height")

        # planes (must be 1)
        planes: int = (bmp_data[26] | (bmp_data[27] << 8))
        if planes != 1:
            raise ValueError("Invalid planes")

        # bpp (must be 24)
        bpp: int = (bmp_data[28] | (bmp_data[29] << 8))
        if bpp != 24:
            raise ValueError("Only 24-bit BMP supported")

        # compression (must be BI_RGB = 0)
        comp: int = (bmp_data[30] |
                     (bmp_data[31] << 8) |
                     (bmp_data[32] << 16) |
                     (bmp_data[33] << 24))
        if comp != 0:
            raise ValueError("Compressed BMP not supported")

        # row stride with 4-byte padding: ((width*3 + 3) & ~3)
        bytes_per_row: int = width * 3
        stride: int = (bytes_per_row + 3) // 4 * 4

        # bounds check: pixel data must fit in file
        total_data: int = stride * abs_height
        if pixel_ofs + total_data > bmp_len:
            raise ValueError("BMP pixel data truncated")

        # --- Prepare output ---
        out_sz: int = width * abs_height * 2
        outbuf = bytearray(out_sz)
        outp: ptr16 = ptr16(addressof(outbuf))

        # constants for RGB565 pack
        RMASK: int = 0xF8
        GMASK: int = 0xFC

        # --- Iterate rows/pixels ---
        y: int = 0
        while y < abs_height:
            # source row selection (BMP is bottom-up unless top_down)
            src_y: int = y if top_down == 1 else (abs_height - 1 - y)
            src_base: int = pixel_ofs + src_y * stride

            x: int = 0
            while x < width:
                px_off: int = src_base + x * 3
                # BGR order in BMP
                b: int = bmp_data[px_off]
                g: int = bmp_data[px_off + 1]
                r: int = bmp_data[px_off + 2]

                # pack to RGB565
                rgb565: int = ((r & RMASK) << 8) | ((g & GMASK) << 3) | (b >> 3)

                # --- 180° rotation: flip horizontally and vertically ---
                out_index: int = (abs_height - 1 - y) * width + (width - 1 - x)
                outp[out_index] = rgb565

                x += 1
            y += 1


        return (width, abs_height, outbuf)


if __name__ == '__main__':
    print("WARNING: You are running the Inkplate module itself, import this module into your example and use it that way")







