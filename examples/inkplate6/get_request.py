"""Connect to WiFi and perform an HTTP GET request using urequests."""

import network
import time
import urequests
from inkplate6 import Inkplate

# Your WiFi credentials
SSID = "YourNetwork"
PASSWORD = "YourPassword"

# Your personal webhook.site URL (use http://, no leading spaces!)
WEBHOOK_URL = "http://webhook.site/your-unique-url"

def connect_wifi():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        sta_if.active(True)
        sta_if.connect(SSID, PASSWORD)
        start = time.ticks_ms()
        while not sta_if.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 10_000:
                print("WiFi connection failed")
                return False
            time.sleep(0.5)
    return True

if connect_wifi():
    print("Connected to WiFi")

    # Perform GET request
    response = urequests.get(WEBHOOK_URL)
    print("GET status:", response.status_code)
    print("GET body:", response.text)
    response.close()
