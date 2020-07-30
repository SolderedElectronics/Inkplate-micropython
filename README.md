Inkplate 6
==========

This repository contains drivers for the E-Radionica Inkplate 6: an esp32 board with
a 6" E-paper display and three capacitive touch buttons/sensors.

__THIS REPOSITORY IS WORK IN PROGRESS__

E-Radionica info:
- Hardware: https://github.com/e-radionicacom/Inkplate-6-hardware
- Arduino: https://github.com/e-radionicacom/Inkplate-6-Arduino-library

Display info:
- Display Datasheet: http://www.universaldisplay.asia/wp-content/uploads/2012/10/ED060SC7-2.0.pdf
- Essential Scrap page: http://essentialscrap.com/eink/waveforms.html
- SpriteTM page: http://spritesmods.com/?art=einkdisplay&page=1

ESP32 GPIO map
--------------

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

#### I2C I/O Expander MCP23017

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
| -- | -------- | ----------- |
| B0 | GPIO0-MOSFET (EPD-CL) | low pulls gpio0/EPD-CL high via 1K Ohm |
| B1 | VBAT-MOSFET | low enables VBAT |
| B2 | TOUCH1   |
| B3 | TOUCH2   |
| B4 | TOUCH3   |
| B5 | K19      |
| B6 | K20      |
| B7 | K21      |
