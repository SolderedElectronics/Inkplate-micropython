Inkplate 6
==========

This repository contains MicroPython drivers for the E-Radionica Inkplate 6: an ESP32 board with
a 6" E-paper display and three capacitive touch buttons/sensors.

### Inkplate 6 info

- CrowdSupply project: https://www.crowdsupply.com/e-radionica/inkplate-6
- Hardware: https://github.com/e-radionicacom/Inkplate-6-hardware
- Forum: http://forum.e-radionica.com/en/viewtopic.php?f=25&t=260

### Features

- Simple graphics class (similar to Adafruit GFX) for monochrome  and 2-bit greyscale use of the
  ePaper display.
- Simple graphics class for 2 bits per pixel greyscale use of the ePaper display.
- Support for partial updates (currently only on the monochrome display).
- Support for ("u8g2" fonts)[https://github.com/olikraus/u8g2] including rendering from the
  compressed format.
- Access to touch sensors.
- Everything in pure python with screen updates virtually as fast as the Arduino C driver.

Getting started
---------------

- Flash MicroPython v1.12 `GENERIC_SPIRAM` or more recent to your inkplate, e.g.
  `esp32spiram-idf4-20191220-v1.12.bin` from http://micropython.org/download/esp32/
  (it's the very last download link on that page).

- Copy library files to your board, something like:
  ```
  pyboard.py --device /dev/ttyUSB0 -f cp mcp23017.py shapes.py u8g2_font.py luRS24_te.u8f :
  ```
  (You can find `pyboard.py` in the MicroPython tools directory or just download it from
  GitHub: https://raw.githubusercontent.com/micropython/micropython/master/tools/pyboard.py)

- Run `inkplate.py`:
  ```
  pyboard.py --device /dev/ttyUSB0 inkplate.py
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
  ![hello world image](https://github.com/tve/mpy-inkplate/blob/master/img/hello_world.jpg?raw=true)

- The "Hello World" box should then move across the display using partial updates.

  ![hello world animation](https://s3.amazonaws.com/s3.voneicken.com/img/inkplate_vid_o1.gif)

- After a brief pause you will see the first test pattern again.
  Touch the touchpad "3" to advance to the next test pattern.

- Look at the end of `inkplate.py` to see the demo code.

- An initial version of "u8g2" font support can be found in `u8g2_font.py`. The rendering is
  currently not optimized due to a bug in MicroPython's viper code emitter (oops!) but the
  performance seems reasonable.  To try it out copy `inkplate.py` to flash:
  ```
  pyboard.py --device /dev/ttyUSB0 -f cp inkplate.py :
  ```
  Then run the demo:
  ```
  pyboard.py --device /dev/ttyUSB0 u8g2_font.py
  ```
  And have some patience until everything loads and draws incrementally until you see:
  ![alt text](https://github.com/tve/mpy-inkplate/blob/master/img/hello_font.jpg?raw=true)

- Additional fonts can be downloaded as C files from
  https://github.com/olikraus/u8g2/tree/master/tools/font/build/single_font_files
  (realistically you will need to grab the repo...), see (that repo's
  wiki)[https://github.com/olikraus/u8g2/wiki/fntgrp] for an index to all
  the fonts available. Once you grabbed a C file for the font, run
  `./u8g2_convert.py <u8g2_font_blah.c` and upload the resulting `.u8f` binary font file.

- _(This is superceded by the u8g2 font support.)_
  An initial version of BDF font support can be found in `bdf_font.py`. The BDF font parsing is
  super-slow and needs a better solution, but the text looks good. To try it out copy the
  provided font to flash, _warning_ it takes the better part of a minute to upload the font
  file!
  ```
  pyboard.py --device /dev/ttyUSB0 -f cp luRS24.bdf :
  ```
  Then run the demo:
  ```
  pyboard.py --device /dev/ttyUSB0 bdf_font.py
  ```
  And have some patience until everything loads and draws incrementally until you see:
  ![alt text](https://github.com/tve/mpy-inkplate/blob/master/img/hello_font.jpg?raw=true)

Info
----

### Partial Updates

The partial update works as follows. An `InkplateMono` is allocated as well as an `InkplatePartial`
based on it. Then an initial image is drawn using `InkplateMono` and `InkplatePartial.start()` is
called, which makes a copy of the image from `InkplateMono`. The desired screen changes are drawn
normally on the `InkplateMono` and when they're ready to display, `InkplatePartial.display()` is
called.

What `InkplatePartial.display` does is to render the attached `InkplateMono` but as it renders it
compares the pixels with those saved by the call to `start()`. For pixels that have not changed
it sends a "no change" code to the display and for ones that have changed it sends the appropriate
waveform. Sending "no change" is faster than sending the waveform and the partial update waveform
is shorter (thus faster) than the standard refresh-the-screen waveform.

In addition, a bounding box can be passed to `InkplatePartial.display` and it will skip rows outside
of the bounding box, which is faster than sending a full rows of "no change". (The x/width
parameters to `InkplatePartial.display` are currently unused and cannot be used to exclude the
update of pixels that were changed but shouldn't be displayed.)

### Greyscale

Greyscale display is supported using `InkplateGS2` providing 2 bits per pixel.
2-bit greyscale was chosen because it nicely packs 4 pixels into a byte, doesn't use a ton of
memory, and is still fast. Using 3-bit greyscale is not supported by the MicroPython framebuf
module, and doesn't pack nicely into bytes. 4-bit greyscale uses a lot of memory and becomes
rather slow, plus it's not clear decent open source ePaper waveforms can be worked out to
actually display that many levels.

It seems that the main use for more than 2-bit greyscale is the display of images.
The results of the Arduino C driver displaying images quantized to 8 levels (3 bits per pixel) look
rather unconvincing (IMHO) with large flat blotches where the original images has a gradient (for
example portions showing the sky). It seems that images dithered to 2-bit greyscale with
Floyd-Steinberg or equivalent ought to look better than that.

All this being said, it shouldn't be all that much work to make a clone of `InkplateGS2` that
supports 4-bit greyscale.

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
