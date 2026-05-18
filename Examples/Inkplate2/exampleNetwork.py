# FILE: Inkplate2-exampleNetwork.py
# AUTHOR: Soldered
# BRIEF: An example showing how to connect to WiFi
#        and get data from the internet
# LAST UPDATED: 2025-08-12

# Include needed libraries
import network
import time
from inkplate2 import Inkplate

# Enter your WiFi credentials here
ssid = "ENTER_SSID_HERE"
password = "ENTER_PASSWORD_HERE"

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

# Create and initialize our Inkplate object in 1-bit mode
inkplate = Inkplate()
inkplate.begin()

# Set text size to double from the original size, so we can see the text better
inkplate.setTextSize(1)

# Print response line by line
inkplate.print(response)

print(response)

# Display image from buffer in full refresh
inkplate.display()
