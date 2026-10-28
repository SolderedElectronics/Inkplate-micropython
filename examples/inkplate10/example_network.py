"""Connect to WiFi and fetch data from the internet."""

# Include needed libraries
import time
from inkplate10 import Inkplate

# Enter your WiFi credentials here
ssid = "ENTER_SSID_HERE"
password = "ENTER_PASSWORD_HERE"

# Create and initialize our Inkplate object in 1-bit mode
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
inkplate.begin()

# Start from a clean screen
inkplate.clear_display()
inkplate.display()

# Text twice the size of the built-in font for the progress messages
inkplate.set_text_size(2)


# Function which connects to WiFi and shows the progress on the screen
# More info here: https://docs.micropython.org/en/latest/esp8266/tutorial/network_basics.html
def do_connect():
    import network

    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("connecting to network...")
        inkplate.print("Connecting to " + ssid)
        inkplate.partial_update()
        sta_if.active(True)
        sta_if.connect(ssid, password)
        while not sta_if.isconnected():
            # One dot a second, so you can see the board is alive
            time.sleep(1)
            inkplate.print(".")
            inkplate.partial_update()
    print("network config:", sta_if.ifconfig())
    inkplate.print(" connected")
    inkplate.partial_update()


# This function does a HTTP GET request
# More info here: https://docs.micropython.org/en/latest/esp8266/tutorial/network_tcp.html
def http_get(url):
    import socket

    res = ""
    _, _, host, path = url.split("/", 3)
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    s.send(bytes("GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n" % (path, host), "utf8"))
    while True:
        data = s.recv(100)
        if data:
            res += str(data, "utf8")
        else:
            break
    s.close()
    return res


# First, connect
do_connect()

# Do a GET request to the micropython test page
# If you were to do a GET request to a different page/resource, change the URL here
response = http_get("http://micropython.org/ks/test.html")

# Clear the progress messages and use the normal text size, so more of the answer fits
inkplate.clear_display()
inkplate.set_cursor(0, 0)
inkplate.set_text_size(1)

# Print the whole answer
inkplate.print(response)

# Display image from buffer in full refresh
inkplate.display()
