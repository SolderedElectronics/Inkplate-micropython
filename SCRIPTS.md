device ports can vary from device to device and from different ports device is connected to.

erase linux/mac:
esptool.py --port /dev/cu.usbserial-1420 erase_flash 

erase win:
esptool.py --port COM5 erase_flash 


flash linux/mac:
esptool.py --chip esp32 --port /dev/cu.usbserial-1420 write_flash -z 0x1000 esp32spiram-idf4-20191220-v1.12.bin

flash win:
esptool.py --chip esp32 --port COM5 write_flash -z 0x1000 esp32spiram-idf4-20191220-v1.12.bin


copy all linux/mac:
python3 pyboard.py --device /dev/cu.usbserial-1420 -f cp inkplate.py gfx.py gfx_standard_font_01.py mcp23017.py image.py sdcard.py :

copy all win:
python pyboard.py --device COM5 -f cp inkplate.py gfx.py gfx_standard_font_01.py mcp23017.py image.py sdcard.py :


run linux/mac:
python3 pyboard.py --device /dev/cu.usbserial-1420 -f cp inkplate.py : && python3 pyboard.py --device /dev/cu.usbserial-1420 example.py

run win:
python pyboard.py --device COM5 exampleNetwork.py
python pyboard.py --device COM5 example.py

