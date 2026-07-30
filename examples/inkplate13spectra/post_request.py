"""Connect to WiFi and perform an HTTP POST request with a JSON payload using urequests."""

import network
import time
import urequests
import ujson
from inkplate13_spectra import Inkplate

# Enter your WiFi credentials here
ssid = ""
password = ""

#Your personal webhook.site URL (use http://, no leading spaces!)
WEBHOOK_URL =""
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
    data = {"message": "Hello from Inkplate 13SPECTRA!"}

    # Perform POST request
    try:
        response = urequests.post(WEBHOOK_URL, json=data)
        print("POST status:", response.status_code)
        print("POST body:", response.text)

        inkplate.print("POST OK!")
        inkplate.display()

        response.close()

    except Exception as e:
        print("POST failed:", e)
        inkplate.print("POST failed!")
        inkplate.display()

else:
    inkplate.print("Wifi failed")
    inkplate.display()
