"""Connect to WiFi and perform an HTTP POST request with a JSON payload using urequests."""

import network
import time
import urequests
import ujson
from inkplate5 import Inkplate

# Your WiFi credentials
SSID = "YourNetwork"
PASSWORD = "YourPassword"

# Your personal webhook.site URL (use http://, no leading spaces!)
WEBHOOK_URL = "http://webhook.site/your-unique-url"

def connect_wifi():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Connecting to WiFi...")
        sta_if.active(True)
        sta_if.connect(SSID, PASSWORD)
        start = time.ticks_ms()
        while not sta_if.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 10_000:
                print("WiFi connection failed")
                return False
            time.sleep(0.5)
    print("Connected:", sta_if.ifconfig())
    return True

# Initialize Inkplate display
inkplate = Inkplate(Inkplate.INKPLATE_1BIT, variant="inkplate5v2")
inkplate.begin()
inkplate.clear_display()
inkplate.display()
inkplate.set_text_size(2)
inkplate.set_cursor(50, 100)

if connect_wifi():
    # Data to send
    data = {"message": "Hello from Inkplate 5v2!"}

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
    inkplate.print("WiFi failed!")
    inkplate.display()
