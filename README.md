# Soldered Inkplate Micropython library

![](./InkplateImage.jpg)

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
* The displayImageSd example shows you how to draw a JPG/BMP/PNG image with or without dithering from an SD card
* The displayImageWeb example shows you how to draw a JPG/BMP/PNG image with or without dithering from a URL
* The gpioExpander example shows how to use the GPIO expander on new Inkplate models

More information is provided in the examples themselves in the shape of comments.

### Documentation

Find Inkplate documentation [here](https://soldered.com/documentation/inkplate/). 

### License

This repo is licensed with the MIT License. For more info, see LICENSE.

---

## About Soldered

<img src="https://raw.githubusercontent.com/SolderedElectronics/Soldered-Simple-Sensor-Arduino-Library/dev/extras/Soldered-logo-color.png" alt="soldered-logo" width="500"/>

At Soldered, we design and manufacture a wide selection of electronic products to help you turn your ideas into acts and bring you one step closer to your final project. Our products are intented for makers and crafted in-house by our experienced team in Osijek, Croatia. We believe that sharing is a crucial element for improvement and innovation, and we work hard to stay connected with all our makers regardless of their skill or experience level. Therefore, all our products are open-source. Finally, we always have your back. If you face any problem concerning either your shopping experience or your electronics project, our team will help you deal with it, offering efficient customer service and cost-free technical support anytime. 

## Have fun!

And thank you from your fellow makers at Soldered Electronics.


