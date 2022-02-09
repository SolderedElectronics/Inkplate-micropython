import machine
import time
from inkplate6_COLOR import Inkplate


display = Inkplate()


if __name__ == "__main__":
    print("Waking up")

    display.begin()
    display.display()
    display.setPanelDeepSleepState(1)

    time.sleep(5)
    display.begin()
    display.printText(100, 100, "aaaaa", Inkplate.BLACK)
    display.display()
