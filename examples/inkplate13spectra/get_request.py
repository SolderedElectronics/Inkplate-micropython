"""Connect to WiFi and perform an HTTP GET request using urequests."""

# Include needed libraries
import network
import time
import urequests
from inkplate13_spectra import Inkplate

# Enter your WiFi credentials here
ssid = "your ssid"
password = "your password"

#Your personal webhook.site URL (use http://, no leading spaces!)
WEBHOOK_URL ="yout webhook id"
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

inkplate=Inkplate()
inkplate.begin()
inkplate.set_text_size(2)

if do_connect():
    inkplate.print("Wifi connected")
    response=urequests.get(WEBHOOK_URL)
    print("GET status:", response.status_code)
    print("GET body",response.text)
    response.close()

else:
    inkplate.print("Wifi failed")

inkplate.display()
