device ports can vary from device to device and from different ports device is connected to.
inkplate6.py and inkplate10.py are used for respective boards
erase linux/mac:
esptool.py --port /dev/cu.usbserial-1420 erase_flash 

erase win:
esptool.py --port COM5 erase_flash 


flash linux/mac:
esptool.py --chip esp32 --port /dev/cu.usbserial-1420 write_flash -z 0x1000 esp32spiram-20210418-v1.15.bin

flash win:
esptool.py --chip esp32 --port COM5 write_flash -z 0x1000 esp32spiram-20210418-v1.15.bin


copy all linux/mac:
python3 pyboard.py --device /dev/cu.usbserial-1420 -f cp inkplate6.py gfx.py gfx_standard_font_01.py mcp23017.py image.py shapes.py sdcard.py :

This one might need to be started twice
copy all win:
python pyboard.py --device COM5 -f cp inkplate6.py gfx.py gfx_standard_font_01.py mcp23017.py image.py shapes.py sdcard.py :


run linux/mac:
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/basicBW.py
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/basicGrayscale.py
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/exampleNetwork.py
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/exampleSd.py
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/batteryAndTemperatureRead.py
python3 pyboard.py --device /dev/cu.usbserial-1420 Examples/Inkplate6/touchpads.py

run win:
python pyboard.py --device COM5 "Examples/Inkplate6/basicBW.py"
python pyboard.py --device COM5 "Examples/Inkplate6/basicGrayscale.py"
python pyboard.py --device COM5 "Examples/Inkplate6/exampleNetwork.py"
python pyboard.py --device COM5 "Examples/Inkplate6/exampleSd.py"
python pyboard.py --device COM5 "Examples/Inkplate 6/batteryAndTemperatureRead.py"
python pyboard.py --device COM5 "Examples/Inkplate 6/touchpads.py"
