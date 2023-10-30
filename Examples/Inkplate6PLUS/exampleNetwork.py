# This example will show you how to connect to WiFi
# get data from the internet and then print it

# Include needed libraries
import network
import time
from inkplate6PLUS import Inkplate

# Enter your WiFi credentials here
ssid = ""
password = ""

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

# Main function
if __name__ == "__main__":

    # First, connect
    do_connect()

    # Do a GET request to the micropython test page
    # If you were to do a GET request to a different page/resource, change the URL here
    response = http_get("http://micropython.org/ks/test.html")

    # Create and initialize our Inkplate object in 1-bit mode
    display = Inkplate(Inkplate.INKPLATE_1BIT)
    display.begin()

    # Set text size to double from the original size, so we can see the text better
    display.setTextSize(2)

    # Print response line by line
    cnt = 0
    for x in response.split("\n"):
        display.printText(
            10, 20 + cnt, x.upper()
        )  # Default font has only upper case letters
        cnt += 20

    # Display image from buffer in full refresh
    display.display()