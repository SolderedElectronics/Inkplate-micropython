# Soldered Inkplate Micropython library

![](https://raw.githubusercontent.com/SolderedElectronics/Inkplate-Arduino-library/master/extras/InkplateImage.jpg)

The Micropython modules for the Inkplate product family can be found in this repository. Inkplate is a series of powerful, Wi-Fi and Bluetooth enabled, ESP32-based ePaper display products. Its main feature is simplicity. Just plug in a USB cable, load the MicroPython firmware and the required libraries and run your script on Inkplate itself. The Inkplate product family currently includes Inkplate 10, Inkplate 6 and Inkplate 6PLUS, Inkplate 6COLOR and Inkplate 2. 
Inkplate 6 was crowdfunded on [Crowd Supply](https://www.crowdsupply.com/e-radionica/inkplate-6), as well as [Inkplate 10](https://www.crowdsupply.com/e-radionica/inkplate-10), [Inkplate 6PLUS](https://www.crowdsupply.com/e-radionica/inkplate-6plus) and [Inkplate 6COLOR](https://www.crowdsupply.com/soldered/inkplate-6color). Inkplate 2 was funded on [Kickstarter](https://www.kickstarter.com/projects/solderedelectronics/inkplate-2-a-easy-to-use-arduino-compatible-e-paper).

All available to purchase from [Soldered.com](https://soldered.com/categories/inkplate/).

Original effort to enable MicroPython support for Inkplate was done by [tve](https://github.com/tve/micropython-inkplate6). Thank you!

### Setting up Inkplate with MicroPython

In order to get started with running your code on Inkplate, connect the device to your computer via USB and follow these steps:
1. Download the Inkplate-firmware.bin file onto your computer

2. Flash the aformentioned firmware onto the Inkplate device, this can be done via our [Micropython VSCode Extention](https://marketplace.visualstudio.com/items?itemName=SolderedElectronics.soldered-micropython-helper) or the [Thonny IDE](https://thonny.org/)

#### Flashing with the VSCode extension
After [setting up the VSCode extension](https://soldered.com/documentation/micropython/getting-started-with-vscode/), go to  `Install Micropython on your board` and pick `Upload Binary file from PC`, pick the Inkplate-firmware.bin file and wait for it to flash on the device

#### Flashing via Thonny IDE

In the Thonny IDE, go to `Run -> Configure interpreter` and on the bottom of the window go to `Install or update Micropython`. On the bottom of that window click on the `≡` button and pick `Select local MicroPython image`, pick the Inkplate-firmware.bin file on your computer and press `Install`

3. [Install the mpremote package](https://docs.micropython.org/en/latest/reference/mpremote.html)

4. With the mpremote package, we can flash the Inkplate modules onto the device with the following command:
   ```
      mpremote mip install github:SolderedElectronics/Inkplate-micropython/YOUR_DEVICE
   ```
   or if you're running a Windows OS:
   ```
      python -m mpremote mip install github:SolderedElectronics/Inkplate-micropython/YOUR_DEVICE
   ```

   For example, if you want to install drivers for the Inkplate6, it will be the following command:
   ```
      mpremote mip install github:SolderedElectronics/Inkplate-micropython/Inkplate6
   ```


**You only have to do steps 1-4 once when writing MicroPython firmware on your Inkplate!** If you have already done this, proceed from step 5 onwards.

5. Now you can flash examples and write code with the IDE of your choosing!


### Code examples

There are several examples which will indicate all the functions you can use in your own script:
* The basic examples show you drawing shapes, lines and text on the screen in different colors, also a bitmap image in a single color
* The network examples show you how to use the network features like doing a GET request and downloading a file
* The batteryAndTemperatureRead examples show you how to read the internal battery status and the temperature from the internal sensor
* The exampleSD example shows you how to read image files and text from the SD card
* The gpio_expander example shows how to use the GPIO expander on new Inkplate models
* The touchpad examples show you how to use the touchpad on older Inkplates

More information is provided in the examples themselves in the shape of comments.

### Documentation

Find Inkplate documentation [here](https://soldered.com/documentation/inkplate/). 

### Battery power

Inkplate boards have two options for powering it. The first one is obvious - USB port at side of the board. Just plug any microUSB/USB-C (depending on your board version) cable and you are good to go. The second option is using a battery. Supported batteries are standard Li-Ion/Li-Poly batteries with a 3.7V nominal voltage. Connector for the battery is standard 2.00mm pitch JST connector (except on Inkplate 2, it uses SMD solder pads for battery terminals). The onboard charger will charge the battery with 500mA when USB is plugged at the same time. You can use battery of any size or capacity if you don't have a enclosure. If you are using our enclosure, battery size shouldn't exceed 90mm x 40mm (3.5 x 1.57 inch) and 5mm (0.19 inch) in height (excluding Inkplate 2, it uses [this battery](https://soldered.com/product/li-ion-baterija-600mah-3-7v/). [This battery](https://soldered.com/product/li-ion-battery-1200mah-3-7v/) is a good fit for all Inkplate models. Also, Inkplate's hardware is specially optimized for low power consumption in deep sleep mode, making it extremely suitable for battery applications.

#### ⚠️ WARNING
Please check the polarity on the battery JST connector! Some batteries that can be purchased from the web have reversed polarity that can damage Inkplate board! You are safe if you are using the pouch battery from [soldered.com](https://soldered.com/categories/power-sources-batteries/batteries/lithium-batteries/) or Inkplate with the built-in battery . 

#### ℹ NOTE
CR2032 battery is only for RTC backup. Inkplate cannot be powered with it.

### License

This repo is licensed with the MIT License. For more info, see LICENSE.

### Open-source

All of Inkplate-related development is open-sourced:

- [Arduino library](https://github.com/SolderedElectronics/Inkplate-Arduino-library)
- Hardware design:
  - [Soldered Inkplate 2](https://github.com/SolderedElectronics/Soldered-Inkplate-2-hardware-design)
  - [Soldered Inkplate 6](https://github.com/SolderedElectronics/Soldered-Inkplate-6-hardware-design)
  - [Soldered Inkplate 6PLUS](https://github.com/SolderedElectronics/Soldered-Inkplate-6PLUS-hardware-design)
  - [Soldered Inkplate 10](https://github.com/SolderedElectronics/Soldered-Inkplate-10-hardware-design)
  - [Soldered Inkplate 6COLOR](https://github.com/SolderedElectronics/Soldered-Inkplate-6COLOR-hardware-design)
  - [e-radionica.com Inkplate 6](https://github.com/SolderedElectronics/Inkplate-6-hardware)
  - [e-radionica.com Inkplate 10](https://github.com/SolderedElectronics/Inkplate-10-hardware)
  - [e-radionica.com Inkplate 6PLUS](https://github.com/SolderedElectronics/Inkplate-6PLUS-Hardware)
- [OSHWA cerfiticates](https://certification.oshwa.org/list.html?q=inkplate)

### Where to buy

Inkplate boards are available for purchase via:

- [soldered.com](https://soldered.com/categories/inkplate/)
- [Crowd Supply](https://www.crowdsupply.com/soldered)
- [Mouser](https://hr.mouser.com/Search/Refine?Keyword=inkplate)

For all questions and issues please reach us via [e-mail](mailto:hello@soldered.com) or our [contact form](https://soldered.com/contact/).
