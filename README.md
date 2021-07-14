# Inkplate micropython module

![](https://www.crowdsupply.com/img/040a/inkplate-6-angle-01_png_project-main.jpg)

Micropython for all-in-one e-paper display Inkplate can be found in this repo. Inkplate is a powerful, Wi-Fi enabled ESP32 based e-paper display – recycled from a Kindle e-reader. Its main feature is simplicity. Just plug in a USB cable, open Arduino IDE, and change the contents of the screen with few lines of code. Learn more about Inkplate on [official website](https://inkplate.io/). Inkplate was crowdfunded on [Crowd Supply Inkplate 6](https://www.crowdsupply.com/e-radionica/inkplate-6) and [Crowd Supply Inkplate 10](https://www.crowdsupply.com/e-radionica/inkplate-10).

Original effort done by [tve](https://github.com/tve/micropython-inkplate6).

### Features

- Simple graphics class for monochrome use of the e-paper display
- Simple graphics class for 2 bits per pixel greyscale use of the e-paper display
- Support for partial updates (currently only on the monochrome display)
- Access to touch sensors
- Everything in pure python with screen updates virtually as fast as the Arduino C driver
- Bitmap drawing, although really slow one

### Getting started with micropython on Inkplate


- Flash MicroPython firmware supplied, or from http://micropython.org/download/esp32/ .
- Port name/number vary on different devices 
- Run 
  ```
  //Linux/Mac
  esptool.py --port /dev/cu.usbserial-1420 erase_flash

  //Windows
  esptool.py --port COM5 erase_flash 
  ```
  to erase esp32 flash and then
  ```
  //Linux/Mac
  esptool.py --chip esp32 --port /dev/cu.usbserial-1420 write_flash -z 0x1000 esp32spiram-20210418-v1.15.bin

  //Windows
  esptool.py --chip esp32 --port COM5 write_flash -z 0x1000 esp32spiram-20210418-v1.15.bin
  ```
  to flash supplied firmware.
  
  If you don't have esptool.py installed, install it from here: https://github.com/espressif/esptool, at minimum use version 1.15.

- Copy library files to your board, use inkplate6.py or inkplate10.py for respective versions, something like this:
  ```
  //Linux/Mac
  python3 pyboard.py --device /dev/ttyUSB0 -f cp mcp23017.py sdcard.py inkplate6.py image.py shapes.py gfx.py gfx_standard_font_01.py :

  //Windows
  //This one might need to be started twice
  python pyboard.py --device COM5 -f cp inkplate6.py gfx.py gfx_standard_font_01.py mcp23017.py image.py shapes.py sdcard.py :
  ```
  (You can find `pyboard.py` in the MicroPython tools directory or just download it from
  GitHub: https://raw.githubusercontent.com/micropython/micropython/master/tools/pyboard.py)

- Run `example.py`:
  ```
  //Linux/Mac
  python3 pyboard.py --device /dev/ttyUSB0 "Examples/Inkplate6/basicBW.py"

  //Windows
  python pyboard.py --device COM5 "Examples/Inkplate6/basicBW.py"
  ```
- You can run our others examples, showing how to use rest of the functionalities.

### Examples

The repo contains many examples which can demonstrate the Inkplate capabilites. 
- basicBW.py -> demonstrates basic drawing capabilites, as well as drawing some images.
- basicGrayscale.py -> demonstrates basic drawing capabilites, as well as drawing some images.
- exampleNetwork.py -> demonstrates connection to WiFi network while drawing the HTTP request response on the screen.
- exampleSd.py -> demonstrates reading files and images from SD card.
- batteryAndTemperatureRead.py -> demonstrates how to read temperature and voltage from internal sensors.
- touchpads.py -> demonstrates how to use built in touchpads.

### Battery power

Inkplate has two options for powering it. First one is obvious - USB port at side of the board. Just plug any micro USB cable and you are good to go. Second option is battery. Supported batteries are standard Li-Ion/Li-Poly batteries with 3.7V nominal voltage. Connector for the battery is standard 2.00mm pitch JST connector. The onboard charger will charge the battery with 500mA when USB is plugged at the same time. You can use battery of any size or capacity if you don't have a enclosure. If you are using our enclosure, battery size shouldn't exceed 90mm x 40mm (3.5 x 1.57 inch) and 5mm (0.19 inch) in height. [This battery](https://e-radionica.com/en/li-ion-baterija-1200mah.html) is good fit for the Inkplate.

### Arduino?

Looking for Arduino library? Look [here](https://github.com/e-radionicacom/Inkplate-6-Arduino-library)!

### Open-source

All of Inkplate-related development is open-sourced:
- [Arduino library](https://github.com/e-radionicacom/Inkplate-6-Arduino-library)
- [Inkplate 6 hardware](https://github.com/e-radionicacom/Inkplate-6-hardware)
- [micropython Inkplate](https://github.com/e-radionicacom/Inkplate-6-micropython)
- [OSHWA certificate](https://certification.oshwa.org/hr000003.html)

### Where to buy & other

Inkplate is available for purchase via:

- [e-radionica.com](https://e-radionica.com/en/inkplate.html)
- [Crowd Supply Inkplate 6](https://www.crowdsupply.com/e-radionica/inkplate-6)
- [Crowd Supply Inkplate 10](https://www.crowdsupply.com/e-radionica/inkplate-10)
- [Mouser](https://hr.mouser.com/Search/Refine?Keyword=inkplate)
- [Sparkfun](https://www.sparkfun.com/search/results?term=inkplate)
- [Pimoroni](https://shop.pimoroni.com/products/inkplate-6)

Inkplate is open-source. If you are looking for hardware design of the board, check the [Hardware repo for Inkplate 6](https://github.com/e-radionicacom/Inkplate-6-hardware) and [Hardware repo for Inkplate 10](https://github.com/e-radionicacom/Inkplate-10-hardware). You will find 3D printable [enclosure](https://github.com/e-radionicacom/Inkplate-6-hardware/tree/master/3D%20printable%20case) there, as well as [detailed dimensions](https://github.com/e-radionicacom/Inkplate-6-hardware/tree/master/Technical%20drawings). In this repo you will find code for driving the ED060SC7 e-paper display used by Inkplate.

For all questions and issues, please use our [forum](http://forum.e-radionica.com/en) to ask an question.
For sales & collaboration, please reach us via [e-mail](mailto:kontakt@e-radionica.com).
