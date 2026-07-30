"""Connect to WiFi and show the connection status on the display."""

# Include needed libraries
import network
import time
from inkplate13_spectra import Inkplate

# Enter your WiFi credentials here
ssid = "YOUR_SSID_HERE"
password = "YOUR_PASSWORD_HERE"

# Function which connects to WiFi
# More info here: https://docs.micropython.org/en/latest/esp8266/tutorial/network_basics.html
def do_connect():
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("connecting to network...")
        sta_if.active(True)
        sta_if.connect(ssid, password)
        while not sta_if.isconnected():
            pass
    print("network config:", sta_if.ifconfig())
    return True

inkplate = Inkplate()
inkplate.begin()
inkplate.set_text_size(2)

if do_connect():
    inkplate.print("Wifi connected")
else:
    inkplate.print("Wifi failed")

inkplate.display()
