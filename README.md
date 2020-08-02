Inkplate 6
==========

This repository contains MicroPython drivers for the E-Radionica Inkplate 6: an esp32 board with
a 6" E-paper display and three capacitive touch buttons/sensors.

### Inkplate 6 info
- CrowdSupply project: https://www.crowdsupply.com/e-radionica/inkplate-6
- Hardware: https://github.com/e-radionicacom/Inkplate-6-hardware
- Forum: _some day..._

### Features

- Simple graphics class (similar to Adafruit GFX) for monochrome use of the ePaper display.
- Simple graphics class for 2 bits per pixel greyscale use of the ePaper display.
- Support for partial updates (currently only on the monochrome display).
- Access to touch sensors.
- Everything in pure python with screen updates virtually as fast as the Arduino C driver.

Getting started
---------------

- Flash MicroPython v1.12 `GENERIC_SPIRAM` or more recent to your inkplate, e.g.
  `esp32spiram-idf4-20191220-v1.12.bin` from http://micropython.org/download/esp32/
  (it's the very last download link on that page).

- Copy library files to your board, something like:
  ```
  pyboard --device /dev/ttyUSB0 -f cp mcp23017.py gfx_standard_font_01.py :
  ```

- Run inkplate.py:
  ```
  pyboard --device /dev/ttyUSB0 inkplate.py
  ```

- On the terminal console you should see a bunch of progress lines:
  ```
  Mono: clean 857ms (17ms ea), draw 298ms (49ms ea), total 1155ms
  GS2: clean 855ms (17ms ea), draw 696ms (99ms ea), total 1551ms
  GFXPatt: in 102ms
  Mono: clean 858ms (17ms ea), draw 297ms (49ms ea), total 1155ms
  GFX: in 36ms
  Partial: draw 166ms (33ms/frame 65us/row) (y=90..158)
  ...
  ```

- On the display you should see it clearing, then showing a monochrome test pattern, clearing and
  showing a greyscale test pattern, then clearing and showing the following test pattern:
  ![alt text](https://github.com/tve/mpy-inkplate/blob/master/img/hello_world.jpg?raw=true)

- The "Hello World" box should then move across the display using partial updates.

- After a brief pause you will see the first test pattern. Touch the touchpad "3" to advance to 
  the next test pattern.

- Look at the end of inkplate.py to see the demo code.

Info
----

- 2-bit greyscale was chosen because it nicely packs 4 pixels into a byte, doesn't use a ton of
  memory, and is still fast. Using 3-bit greyscale is not supported by the MicroPython framebuf
  module, and doesn't pack nicely into bytes. 4-bit greyscale uses a lot of memory and becomes
  rather slow, plus it's not clear decent ePaper waveforms can be worked out to actually display
  that many levels. In addition, it seems that images dithered to 2-bit greyscale look better than
  if they are quantized to 3-bit greyscale. All this being said, it shouldn't be all that much
  work to make a clone of InkplateGS2 that supports 4-bit greyscale.
- The update speed relies heavily on the MicroPython viper compile-to-native functionality.
  It's great because it allows a pure python library. But it also sucks because it's not really
  that good and the code starts to become pretty obscure. It would be smart to recode the key
  functions in C and provide an optional pre-compiled mpy file with that.
- The timing of the display update is based on "it seems to work". It appears that the rate at
  which rows are updated is really faster than spec. This can have some very unintuitive
  side-effects. For example, if the speed at which rows are _skipped_ is increased in the partial
  update, the rows that are updated are washed out (even if they are written as slowly as before)!
  It would be good to exert more care about the update speed in the future C primitives.


### Display info:
- Display Datasheet: http://www.universaldisplay.asia/wp-content/uploads/2012/10/ED060SC7-2.0.pdf
- Essential Scrap page: http://essentialscrap.com/eink/waveforms.html
- SpriteTM page: http://spritesmods.com/?art=einkdisplay&page=1
- General background on waveforms: https://wenku.baidu.com/view/00bbfb6727d3240c8447efd5.html
- Display flash chip: MX25L2006 2Mbit (256KBytes)

### ESP32 GPIO map

| GPIO | Note       | Function | Description |
| ---- | ----       | -------- | ----------- |
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
