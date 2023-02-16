from inkplate6_COLOR import Inkplate

display = Inkplate()

if __name__ == "__main__":
    display.begin()
    display.clearDisplay()

    battery = str(display.readBattery())

    display.setTextSize(2)
    display.printText(100, 100, "batt: " + battery + "V")
    display.display()
