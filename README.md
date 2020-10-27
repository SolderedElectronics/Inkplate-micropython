# Inkplate 6 micropython module

![](https://www.crowdsupply.com/img/040a/inkplate-6-angle-01_png_project-main.jpg)

Micropython for all-in-one e-paper display Inkplate 6 can be found in this repo. Inkplate 6 is a powerful, Wi-Fi enabled ESP32 based six-inch e-paper display – recycled from a Kindle e-reader. Its main feature is simplicity. Just plug in a USB cable, open Arduino IDE, and change the contents of the screen with few lines of code. Learn more about Inkplate 6 on [official website](https://inkplate.io/). Inkplate was crowdfunded on [Crowd Supply](https://www.crowdsupply.com/e-radionica/inkplate-6).

Original effort done by [tve](https://github.com/tve/micropython-inkplate6).

### Features

- Simple graphics class for monochrome use of the e-paper display
- Simple graphics class for 2 bits per pixel greyscale use of the e-paper display
- Support for partial updates (currently only on the monochrome display)
- Access to touch sensors
- Everything in pure python with screen updates virtually as fast as the Arduino C driver
- Bitmap drawing, although really slow one

### Getting started with micropython on Inkplate 6


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

### Battery power

Inkplate 6 has two options for powering it. First one is obvious - USB port at side of the board. Just plug any micro USB cable and you are good to go. Second option is battery. Supported batteries are standard Li-Ion/Li-Poly batteries with 3.7V nominal voltage. Connector for the battery is standard 2.00mm pitch JST connector. The onboard charger will charge the battery with 500mA when USB is plugged at the same time. You can use battery of any size or capacity if you don't have a enclosure. If you are using our enclosure, battery size shouldn't exceed 90mm x 40mm (3.5 x 1.57 inch) and 5mm (0.19 inch) in height. [This battery](https://e-radionica.com/en/li-ion-baterija-1200mah.html) is good fit for the Inkplate.

### Arduino?

Looking for Arduino library? Look [here](https://github.com/e-radionicacom/Inkplate-6-Arduino-library)!

### Open-source

All of Inkplate-related development is open-sourced:
- [Arduino library](https://github.com/e-radionicacom/Inkplate-6-Arduino-library)
- [Inkplate 6 hardware](https://github.com/e-radionicacom/Inkplate-6-hardware)
- [micropython Inkplate](https://github.com/e-radionicacom/Inkplate-6-micropython)
- [OSHWA certificate](https://certification.oshwa.org/hr000003.html)

### Where to buy & other

Inkplate 6 is available for purchase via:

- [e-radionica.com](https://e-radionica.com/en/inkplate.html)
- [Crowd Supply](https://www.crowdsupply.com/e-radionica/inkplate-6)
- [Mouser](https://hr.mouser.com/Search/Refine?Keyword=inkplate)
- [Sparkfun](https://www.sparkfun.com/search/results?term=inkplate)
- [Pimoroni](https://shop.pimoroni.com/products/inkplate-6)

Inkplate 6 is open-source. If you are looking for hardware design of the board, check the [Hardware repo](https://github.com/e-radionicacom/Inkplate-6-hardware). You will find 3D printable [enclosure](https://github.com/e-radionicacom/Inkplate-6-hardware/tree/master/3D%20printable%20case) there, as well as [detailed dimensions](https://github.com/e-radionicacom/Inkplate-6-hardware/tree/master/Technical%20drawings). In this repo you will find code for driving the ED060SC7 e-paper display used by Inkplate.

For all questions and issues, please use our [forum](http://forum.e-radionica.com/en) to ask an question.
For sales & collaboration, please reach us via [e-mail](mailto:kontakt@e-radionica.com).
