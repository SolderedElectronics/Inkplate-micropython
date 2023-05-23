from inkplate2 import Inkplate
from image import *

display = Inkplate()

if __name__ == "__main__":
    display.begin()
    display.clearDisplay()
    display.display()

    battery = str(display.readBattery())

    display.setTextSize(1)
    display.printText(5, 5, "batt: " + battery + "V")
    display.display()