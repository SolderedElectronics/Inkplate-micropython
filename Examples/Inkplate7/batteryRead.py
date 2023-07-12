from inkplate7 import Inkplate
from image import *

display = Inkplate()

if __name__ == "__main__":
    display.begin()
    #display.clearDisplay()
    #display.display()

    battery = str(display.read_battery())

    display.setTextSize(2)
    display.printText(100, 100, "batt: " + battery + "V")
    display.display()