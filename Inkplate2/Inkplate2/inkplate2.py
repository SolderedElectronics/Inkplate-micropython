# MicroPython driver for Inkplate 2
# By Soldered Electronics
# Based on the original contribution by https://github.com/tve
import time
import os
from machine import ADC, I2C, SPI, Pin
from micropython import const
from shapes import Shapes
from machine import Pin as mPin
from gfx import GFX

import machine
machine.freq(240000000)

# Connections between ESP32 and color Epaper
EPAPER_RST_PIN = const(19)
EPAPER_DC_PIN = const(33)
EPAPER_CS_PIN = const(27)
EPAPER_BUSY_PIN = const(32)
EPAPER_CLK = const(18)
EPAPER_DIN = const(23)

pixelMaskLUT = [0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80]
pixelMaskGLUT = [0xF, 0xF0]

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
    
    textColor=BLACK

    rotation = 0
    textSize = 1

    _panelState = False
    
    cursor = [0,0]

    @classmethod
    def begin(self):
        self.wire = I2C(0, scl=Pin(22), sda=Pin(21))
        self.spi = SPI(2, baudrate=800000)
        self._framebuf_BW = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        self._framebuf_RED = bytearray(([0xFF] * E_INK_BUFFER_SIZE))
        self.textColor = 1

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
        
        self.textSize=1

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
            self.GFX.width = E_INK_WIDTH
            self.GFX.height = E_INK_HEIGHT
            self._width = E_INK_WIDTH
            self._height = E_INK_HEIGHT
        elif self.rotation == 1 or self.rotation == 3:
            self.GFX.width = E_INK_HEIGHT
            self.GFX.height = E_INK_WIDTH
            self._width = E_INK_HEIGHT
            self._height = E_INK_WIDTH

    @classmethod
    def getRotation(self):
        return self.rotation

    @classmethod
    def drawPixel(self, x, y, c):
        self.writePixel(x, y, c)


    @classmethod
    @micropython.native
    def writePixel(self, x, y, c):
        # Bounds check
        if not (0 <= x < self.width() and 0 <= y < self.height()):
            return
        if c > 2:
            return

        # Rotate coordinates
        if self.rotation == 3:
            x, y = y, self.width() - x - 1
        elif self.rotation == 0:
            x, y = self.width() - x - 1, self.height() - y - 1
        elif self.rotation == 1:
            x, y = self.height() - y - 1, x

        # Compute position in frame buffer
        _x_sub = x % 8
        _x = x // 8
        _position = (E_INK_WIDTH // 8) * y + _x

        # Precompute LUT mask
        mask = pixelMaskLUT[7 - _x_sub]

        # Clear the bits in both buffers
        self._framebuf_BW[_position] |= mask
        self._framebuf_RED[_position] |= mask

        # Apply color
        if c < 2:
            # Black or white: clear bit in BW buffer accordingly
            self._framebuf_BW[_position] &= ~(c << (7 - _x_sub))
        else:
            # Red pixel: clear bit in RED buffer
            self._framebuf_RED[_position] &= ~mask
    




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
        self.writeFastVLine(x, y, h, c)
        

    @classmethod
    def drawFastHLine(self, x, y, w, c):
        self.writeFastHLine(x, y, w, c)
        

    @classmethod
    def fillRect(self, x, y, w, h, c):
        self.writeFillRect(x, y, w, h, c)
        

    @classmethod
    def fillScreen(self, c):
        self.fillRect(0, 0, self.width(), self.height(), c)

    @classmethod
    def drawLine(self, x0, y0, x1, y1, c):
        self.writeLine(x0, y0, x1, y1, c)
        

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
    def setTextColor(self, c):
        self.textColor = c

    @classmethod
    def setTextSize(self, s):
        self.textSize = s

    @classmethod
    def setFont(self, f):
        self.GFX.font = f

    def setCursor(self, x, y):
        self.cursor=[x,y]

    def printText(self, x, y, s, c=1):
        self.GFX._print_text(self._framebuf_BW,x, y, s, self.textSize,c, text_wrap=self.wrap_text, bpp=1)
            
    def println(self, text):
        self.cursor,line_height = self.GFX._print_text(self._framebuf_BW,self.cursor[0], self.cursor[1], text, self.textSize, self.textColor, text_wrap=self.wrap_text, bpp=1)
        self.cursor[1]+=line_height
        self.cursor[0]=0
        
    def print(self, text):
        self.cursor,_ = self.GFX._print_text(self._framebuf_BW,self.cursor[0], self.cursor[1], text, self.textSize, self.textColor, text_wrap=self.wrap_text, bpp=1)
        
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
    def drawBitmap(self, x, y, data, w, h, c=BLACK):
        byteWidth = (w + 7) // 8
        byte = 0
        
        for j in range(h):
            for i in range(w):
                if i & 7:
                    byte <<= 1
                else:
                    byte = data[j * byteWidth + i // 8]
                if byte & 0x80:
                    self.writePixel(x + i, y + j, c)
        

    @classmethod
    def drawColorBitmap(self, x, y, w, h, buf):
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
            
            raise ValueError("Draw Image error: URL could not be parsed.")
        
    
    
    def drawJPGFromWeb(self, url, x0=0, y0=0, invert=False, dither:bool=False, kernel_type:int=0):
        import jpeg
        import gc
        import urequests
        import ssl
        
        try:
            # 1. Initialize decoder
            decoder = jpeg.Decoder(rotation=0, format="RGB565_LE")
            
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
            

            self.rgb565_to_2bpp(decoded,width,height, dither)
            
            
            
            
            
        except Exception as e:
            print("Error in drawJPGFromWeb:", e)
            if 'response' in locals():
                response.close()
            raise


    

    def rgb565_to_2bpp(self, imagedata, width:int, height:int, dither:bool=True):
        row_bytes:int = -(-width // 4)
        outbuf = bytearray(row_bytes * height)

        if dither:
            # use a signed error buffer as ints to avoid overflow
            error_buffer = [0] * (width * height * 3)
        else:
            error_buffer = [0]  # dummy

        @micropython.viper
        def process_pixel(im: ptr8, out: ptr8, err: ptr32, w: int, h: int, do_dither: int):
            for y in range(h):
                for x in range(w):
                    idx = (y * w + x) * 2
                    pixel = im[idx] | (im[idx + 1] << 8)

                    r = ((pixel >> 11) & 0x1F) * 255 // 31
                    g = ((pixel >> 5) & 0x3F) * 255 // 63
                    b = (pixel & 0x1F) * 255 // 31

                    if do_dither:
                        e_idx = (y * w + x) * 3
                        r = int(min(255, int(max(0, r + err[e_idx]))))
                        g = int(min(255, int(max(0, g + err[e_idx + 1]))))
                        b = int(min(255, int(max(0, b + err[e_idx + 2]))))

                    # classify pixel
                    if r > int(max(g, b)) * 3 // 2 and r > 128:
                        c = 2  # red
                        new_r, new_g, new_b = 255, 0, 0
                    elif r + g + b < 384:
                        c = 0  # black
                        new_r, new_g, new_b = 0, 0, 0
                    else:
                        c = 1  # white
                        new_r, new_g, new_b = 255, 255, 255

                    # propagate error
                    if do_dither:
                        e_idx = (y * w + x) * 3
                        err_r = r - int(new_r)
                        err_g = g - int(new_g)
                        err_b = b - int(new_b)

                        if x + 1 < w:
                            e = (y * w + (x + 1)) * 3
                            err[e]     += err_r * 7 // 16
                            err[e + 1] += err_g * 7 // 16
                            err[e + 2] += err_b * 7 // 16
                        if y + 1 < h:
                            if x > 0:
                                e = ((y + 1) * w + (x - 1)) * 3
                                err[e]     += err_r * 3 // 16
                                err[e + 1] += err_g * 3 // 16
                                err[e + 2] += err_b * 3 // 16
                            e = ((y + 1) * w + x) * 3
                            err[e]     += err_r * 5 // 16
                            err[e + 1] += err_g * 5 // 16
                            err[e + 2] += err_b * 5 // 16
                            if x + 1 < w:
                                e = ((y + 1) * w + (x + 1)) * 3
                                err[e]     += err_r * 1 // 16
                                err[e + 1] += err_g * 1 // 16
                                err[e + 2] += err_b * 1 // 16

                    # pack 2bpp
                    byte_idx = int(y) * int(row_bytes) + int(x >> 2)
                    shift = (3 - (x & 3)) * 2
                    out[byte_idx] |= (c & 0x03) << shift

        # cast Python list to ptr32 for Viper signed access
        import array
        if dither:
            err_arr = array.array('i', error_buffer)
        else:
            err_arr = array.array('i', [0])

        process_pixel(imagedata, outbuf, err_arr, width, height, 1 if dither else 0)
        Inkplate.drawColorImage_viper(0, 0, width, height, outbuf)


    @micropython.viper
    def drawColorImage_viper(x:int, y:int, w:int, h:int, buf_obj):
        scaled_w = (w + 3) // 4
        buf = ptr8(buf_obj)
        for i in range(h):
            for j in range(w):
                byte_idx = (i * scaled_w) + (j >> 2)
                shift = (3 - (j & 3)) * 2
                pix = (buf[byte_idx] >> shift) & 0x03
                Inkplate.writePixel(j + x, i + y, pix)
                
    
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
            
            Inkplate.decode_png_to_framebuffer(png_data, x0, y0, invert, dither)
            gc.collect()
        
        except Exception as e:
            print("Error in drawPNGFromWeb:", e)
            if 'response' in locals():
                response.close()
    
    @staticmethod
    @micropython.native
    def decode_png_to_framebuffer(png_data, x0, y0, invert=False, dither=False):
        import deflate
        import io
        import array

        _SCREEN_WIDTH_ = const(212)
        _SCREEN_HEIGHT_ = const(104)

        @micropython.native
        def parse_chunks(png_bytes):
            pos = 8
            ihdr = None
            idat_list = []
            plte = None
            while pos + 8 <= len(png_bytes):
                clen = int.from_bytes(png_bytes[pos:pos+4], 'big')
                ctype = png_bytes[pos+4:pos+8]
                cstart = pos + 8
                cend = cstart + clen
                if ctype == b'IHDR':
                    ihdr = png_bytes[cstart:cend]
                elif ctype == b'PLTE':
                    plte = png_bytes[cstart:cend]
                elif ctype == b'IDAT':
                    idat_list.append(png_bytes[cstart:cend])
                elif ctype == b'IEND':
                    break
                pos = cend + 4
            return ihdr, b''.join(idat_list), plte

        def bytes_per_pixel(bit_depth, color_type):
            if bit_depth != 8:
                raise ValueError("Only 8-bit PNGs supported in this decoder path")
            if color_type == 0:
                return 1
            if color_type == 2:
                return 3
            if color_type == 4:
                return 2
            if color_type == 6:
                return 4
            if color_type == 3:
                raise ValueError("Indexed-color PNG not supported without PLTE palette handling")
            raise ValueError("Unsupported color type: %d" % color_type)

        if len(png_data) < 8 or png_data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG signature")

        ihdr, idat, plte = parse_chunks(png_data)
        if not ihdr:
            raise ValueError("Missing IHDR")
        if not idat:
            raise ValueError("No IDAT chunks")

        width  = int.from_bytes(ihdr[0:4], 'big')
        height = int.from_bytes(ihdr[4:8], 'big')
        bit_depth  = ihdr[8]
        color_type = ihdr[9]
        interlace  = ihdr[12]

        if interlace != 0:
            raise ValueError("Interlaced PNG not supported in this path")

        bpp = bytes_per_pixel(bit_depth, color_type)

        draw_width  = width  if (x0 + width)  <= _SCREEN_WIDTH_  else _SCREEN_WIDTH_  - x0
        draw_height = height if (y0 + height) <= _SCREEN_HEIGHT_ else _SCREEN_HEIGHT_ - y0
        if draw_width <= 0 or draw_height <= 0:
            return

        dstream = deflate.DeflateIO(io.BytesIO(idat))
        stride = 1 + width * bpp

        cur = bytearray(width * bpp)
        prev = bytearray(width * bpp)

        if dither:
            err_w = draw_width
            err_cur = array.array('h', [0] * err_w)
            err_nxt = array.array('h', [0] * err_w)

        inv_mask = 1 if invert else 0

        @micropython.native
        def apply_filter(raw, cur_row, prev_row, bpp_):
            f = raw[0]
            data = raw[1:]
            if f == 0:
                cur_row[:] = data
            elif f == 1:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    cur_row[i] = (data[i] + a) & 0xFF
            elif f == 2:
                for i in range(len(data)):
                    b = prev_row[i]
                    cur_row[i] = (data[i] + b) & 0xFF
            elif f == 3:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    b = prev_row[i]
                    cur_row[i] = (data[i] + ((a + b) >> 1)) & 0xFF
            elif f == 4:
                for i in range(len(data)):
                    a = cur_row[i - bpp_] if i >= bpp_ else 0
                    b = prev_row[i]
                    c = prev_row[i - bpp_] if i >= bpp_ else 0
                    p = a + b - c
                    pa = p - a
                    if pa < 0: pa = -pa
                    pb = p - b
                    if pb < 0: pb = -pb
                    pc = p - c
                    if pc < 0: pc = -pc
                    if pa <= pb and pa <= pc:
                        pred = a
                    elif pb <= pc:
                        pred = b
                    else:
                        pred = c
                    cur_row[i] = (data[i] + pred) & 0xFF
            else:
                raise ValueError("Unknown PNG filter: %d" % f)

        for y in range(height):
            raw = dstream.read(stride)
            if not raw or len(raw) != stride:
                break
            apply_filter(raw, cur, prev, bpp)

            if y >= draw_height:
                cur, prev = prev, cur
                continue

            base = 0
            for x in range(draw_width):
                if color_type == 0:
                    r = g = b = cur[base]; a = 255
                elif color_type == 2:
                    r = cur[base]; g = cur[base + 1]; b = cur[base + 2]; a = 255
                elif color_type == 4:
                    r = g = b = cur[base]; a = cur[base + 1]
                elif color_type == 6:
                    r = cur[base]; g = cur[base + 1]; b = cur[base + 2]; a = cur[base + 3]
                else:
                    r = g = b = 0; a = 255

                base += bpp

                if a < 255:
                    bg = 255 if invert else 0
                    r = (r * a + bg * (255 - a)) // 255
                    g = (g * a + bg * (255 - a)) // 255
                    b = (b * a + bg * (255 - a)) // 255

                # red detection (same rule you used)
                is_red = (r * 2 > max(g, b) * 3) and (r > 128)

                if a == 0:
                    # transparent -> white (or inverted)
                    val = 1 ^ inv_mask
                elif is_red:
                    # red pixel
                    val = 2
                else:
                    # grayscale luminance
                    gray = (r * 77 + g * 151 + b * 28) >> 8

                    if dither:
                        gray = gray + err_cur[x]
                        if gray < 0: gray = 0
                        elif gray > 255: gray = 255
        
                    val = 0 if gray > 127 else 1   # 1 = white, 0 = black
                    val_before_inv=val
                    if invert:
                        val ^= 1

                    if dither:
                        # predicted brightness for chosen color: 0 for black, 255 for white
                        quant = 255 if val_before_inv == 0 else 1
                        delta = gray - quant
                        if x + 1 < draw_width:
                            err_cur[x + 1] += (delta * 7) // 16
                        if y + 1 < draw_height:
                            if x > 0:
                                err_nxt[x - 1] += (delta * 3) // 16
                            err_nxt[x] += (delta * 5) // 16
                            if x + 1 < draw_width:
                                err_nxt[x + 1] += (delta * 1) // 16

                Inkplate.writePixel(x0 + x, y0 + y, val)

            if dither:
                err_cur, err_nxt = err_nxt, err_cur
                for i in range(draw_width):
                    err_nxt[i] = 0

            cur, prev = prev, cur
            
            
    def drawBMPFromWeb(self, url, x0=0, y0=0, invert=False, dither=False):
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
            Inkplate.decode_bmp(bmp_data, x0, y0, invert, dither)
        except Exception as e:
            print("Error in drawBMPFromWeb:", e)
            if 'response' in locals():
                response.close()

            
        
    @staticmethod
    @micropython.native
    def decode_bmp(bmp_data, x0, y0, invert, dither):
        import array

        __SCREEN_WIDTH_ = const(212)
        __SCREEN_HEIGHT_ = const(104)

        # BMP header parsing (support only uncompressed 24-bit or 32-bit BMP)
        if bmp_data[0:2] != b'BM':
            raise ValueError("Not a BMP file")
        file_size = int.from_bytes(bmp_data[2:6], 'little')
        pixel_offset = int.from_bytes(bmp_data[10:14], 'little')
        dib_header_size = int.from_bytes(bmp_data[14:18], 'little')
        width  = int.from_bytes(bmp_data[18:22], 'little', True)
        height = int.from_bytes(bmp_data[22:26], 'little', True)
        planes = int.from_bytes(bmp_data[26:28], 'little')
        bpp = int.from_bytes(bmp_data[28:30], 'little')
        compression = int.from_bytes(bmp_data[30:34], 'little')

        if compression != 0 or planes != 1 or bpp not in (24, 32):
            raise ValueError("Unsupported BMP format")

        # BMP rows are padded to 4 bytes
        row_bytes = ((width * bpp + 31) // 32) * 4
        draw_width  = min(width, __SCREEN_WIDTH_ - x0)
        draw_height = min(abs(height), __SCREEN_HEIGHT_ - y0)
        if draw_width <= 0 or draw_height <= 0:
            return

        # prepare dithering buffers
        if dither:
            err_cur = array.array('h', [0] * draw_width)
            err_nxt = array.array('h', [0] * draw_width)

        inv_mask = 1 if invert else 0
        flipped = height > 0  # BMP stores bottom-up if height > 0

        for y_img in range(draw_height):
            if flipped:
                y_bmp = height - 1 - y_img
            else:
                y_bmp = y_img
            row_start = pixel_offset + y_bmp * row_bytes
            row_data = bmp_data[row_start : row_start + width * (bpp // 8)]

            for x in range(draw_width):
                base = x * (bpp // 8)
                b = row_data[base]
                g = row_data[base + 1]
                r = row_data[base + 2]
                a = row_data[base + 3] if bpp == 32 else 255

                # alpha blending (against white background)
                if a < 255:
                    bg = 255 if invert else 0
                    r = (r * a + bg * (255 - a)) // 255
                    g = (g * a + bg * (255 - a)) // 255
                    b = (b * a + bg * (255 - a)) // 255

                # red detection
                is_red = (r * 2 > max(g, b) * 3) and (r > 128)

                if a == 0:
                    val = 1 ^ inv_mask  # transparent -> white
                elif is_red:
                    val = 2
                else:
                    gray = (r * 77 + g * 151 + b * 28) >> 8
                    if dither:
                        gray = gray + err_cur[x]
                        if gray < 0: gray = 0
                        elif gray > 255: gray = 255

                    val = 0 if gray > 127 else 1
                    val_before_inv = val
                    if invert:
                        val ^= 1

                    if dither:
                        quant = 255 if val_before_inv == 0 else 0
                        delta = gray - quant
                        if x + 1 < draw_width:
                            err_cur[x + 1] += (delta * 7) // 16
                        if y_img + 1 < draw_height:
                            if x > 0:
                                err_nxt[x - 1] += (delta * 3) // 16
                            err_nxt[x] += (delta * 5) // 16
                            if x + 1 < draw_width:
                                err_nxt[x + 1] += (delta * 1) // 16

                Inkplate.writePixel(x0 + x, y0 + y_img, val)

            if dither:
                err_cur, err_nxt = err_nxt, err_cur
                for i in range(draw_width):
                    err_nxt[i] = 0


if __name__ == '__main__':
    print("WARNING: You are running the Inkplate module itself, import this module into your example and use it that way")







                        
    
    
