Inkplate 6
==========

This repository contains MicroPython drivers for the E-Radionica Inkplate 6: an ESP32 board with
a 6" E-paper display and three capacitive touch buttons/sensors.

### Inkplate 6 info

- CrowdSupply project: https://www.crowdsupply.com/e-radionica/inkplate-6
- Hardware: https://github.com/e-radionicacom/Inkplate-6-hardware
- Forum: http://forum.e-radionica.com/en/viewtopic.php?f=25&t=260

### Features

- Simple graphics class for monochrome  and 2-bit greyscale use of the
  ePaper display.
- Simple graphics class for 2 bits per pixel greyscale use of the ePaper display.
- Support for partial updates (currently only on the monochrome display).
- Access to touch sensors.
- Everything in pure python with screen updates virtually as fast as the Arduino C driver.
- Added bitmap drawing, although really slow one.

Getting started
---------------

- Flash MicroPython firmware supplied, or from http://micropython.org/download/esp32/ .
- Run 
  ```
  esptool.py --port /dev/cu.usbserial-1420 erase_flash 
  ```
  to erase esp32 flash and then
  ```
  esptool.py --chip esp32 --port /dev/cu.usbserial-1420 write_flash -z 0x1000 esp32spiram-idf4-20191220-v1.12.bin
  ```
  to flash supplied firmware.
  
  If you don't have esptool.py installed, install it from here: https://github.com/espressif/esptool.

- Copy library files to your board, something like:
  ```
  python3 pyboard.py --device /dev/ttyUSB0 -f cp mcp23017.py sdcard.py inkplate.py image.py gfx.py gfx_standard_font_01.py :
  ```
  (You can find `pyboard.py` in the MicroPython tools directory or just download it from
  GitHub: https://raw.githubusercontent.com/micropython/micropython/master/tools/pyboard.py)

- Run `example.py`:
  ```
  python3 pyboard.py --device /dev/ttyUSB0 example.py
  ```
- You can run our other 2 examples, showing how to use the Sd card and network class.

### Performance and Timing

The update speed relies heavily on the MicroPython viper compile-to-native functionality.
It's great because it allows a pure python library. But it also sucks because it's not really
that good and the code starts to become pretty obscure. It would be smart to recode the key
functions in C and provide an optional pre-compiled mpy file with that. This is probably only worth
doing once all the kinks are worked out and the intricacies of the ePaper displaya are better
understood.

The timing of the display update is based on "it seems to work". It appears that the rate at
which rows are updated is really faster than spec. This can have some very unintuitive
side-effects. For example, if the speed at which rows are _skipped_ is increased in the partial
update, the rows that are subsequently updated are washed out (even if they are written as slowly
as before)!
It would be good to exert more care with the update speed in the future C primitives.

### Display background info

- Display Datasheet: http://www.universaldisplay.asia/wp-content/uploads/2012/10/ED060SC7-2.0.pdf
- Essential Scrap page: http://essentialscrap.com/eink/waveforms.html
- SpriteTM page: http://spritesmods.com/?art=einkdisplay&page=1
- General background on waveforms: https://wenku.baidu.com/view/00bbfb6727d3240c8447efd5.html
- Display flash chip: MX25L2006 2Mbit (256KBytes)

### ESP32 GPIO map

| GPIO | Std func   | Inkplate | Description |
| ---- | ---------- | -------- | ----------- |
|   0  | pup/ftdi   | EPD-CL   | Clock byte, positive pulse |
|   1  | U0TXD      | TX       |
|   2  | pdn        | EPD-LE   | Latch (row) enable: positive pulse |
|   3  | U0RXD      | RX       |
|   4  |            | EPD-D0   |
|   5  | pup        | EPD-D1   |
|  12  | pdn, mmiso | SPI-MISO |
|  13  | msck       | SPI-MOSI |
|  14  |            | SPI-CK   |
|  15  | mmosi      | SPI-CS   |
|  16  |            | PSRAM    |
|  17  |            | PSRAM    |
|  18  | vsck       | EPD-D2   |
|  19  | vmosi      | EPD-D3   |
|  21  |            | SDA      |
|  22  |            | SCL      |
|  23  | vmiso      | EPD-D4   |
|  25  | dac1       | EPD-D5   |
|  26  | dac2       | EPD-D6   |
|  27  |            | EPD-D7   |
|  32  | adc4       | EPD-CKV  | Clock vertical: positive pulse |
|  33  | adc9       | EPD-SPH  | Start pulse horizontal, active low |
|  34  | in, adc6   | INTB     | interrupt from MCP23017 |
|  35  | in, adc7   | BATV     |
|  36  | in, adc0   |          |
|  39  | in, adc3   |          |

### I2C I/O Expander MCP23017

| IO | Function | Description |
| -- | -------- | ----------- |
| A0 | EPD-OE   |
| A1 | EPD-GMODE | Gate output mode: high to enable |
| A2 | EPD-SPV  | Start pulse vertical, active low |
| A3 | TPS65186 WAKEUP |
| A4 | TPS65186 PWRUP |
| A5 | TPS65186 VCOM-CTRL |
| A6 | TPS65186 INT |
| A7 | TPS65186 PWR-GOOD |
|    |          |             |
| B0 | GPIO0-MOSFET (EPD-CL) | low pulls gpio0/EPD-CL high via 1K Ohm |
| B1 | VBAT-MOSFET | low enables VBAT |
| B2 | TOUCH1   |
| B3 | TOUCH2   |
| B4 | TOUCH3   |
| B5 | K19      |
| B6 | K20      |
| B7 | K21      |
