"""Connect to WiFi and perform an HTTP POST request with a JSON payload using urequests."""

from inkplate2 import Inkplate
import network
import time
import urequests
import ujson

# Replace with your credentials
SSID = "YOUR_SSID_HERE"
PASSWORD = "YOU_PASSWORD_HERE"

# Initialize Inkplate
inkplate = Inkplate()
inkplate.begin()

sta_if = network.WLAN(network.STA_IF)


# Connect to WiFi network
def do_connect():
    connected = False
    if not sta_if.isconnected():
        print("Connecting to network...")
        sta_if.active(True)
        try:
            sta_if.connect(SSID, PASSWORD)
        except Exception as e:
            print(f"Wi-Fi connect error: {e}\n")
            print("Check your credentials!")
        else:
            timeout = 30  # seconds
            start = time.ticks_ms()

            while not sta_if.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                    print("Failed to connect within timeout")
                    break
                time.sleep(0.5)
            else:
                connected = True
    else:
        connected = True

    if connected:
        print(f"CONNECTED: \n{sta_if.ifconfig()}")
        return True
    else:
        return False


def http_post(url, text_data):
    response = urequests.post(url, json=text_data)
    print("Status code:", response.status_code)
    inkplate.print(f"Body: {response.text}")


# Connect to WiFi
if not do_connect():
    raise SystemExit("WiFi connection failed")

WEBHOOK_URL = "https://webhook.site/YOUR_UNIQUE_ID"

# Data you want to send
data = {"message": "Hello from Inkplate2!"}

http_post(WEBHOOK_URL, data)

# Display HTTP response
inkplate.display()
