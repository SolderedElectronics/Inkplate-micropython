# MicroPython driver for the PCAL6416A GPIO expander
# By Soldered Electronics
# Based on the original contribution by https://github.com/tve
from machine import Pin as mPin
from micropython import const

PCAL6416A_INPORT0 = const(0x00)
PCAL6416A_INPORT1 = const(0x01)
PCAL6416A_OUTPORT0 = const(0x02)
PCAL6416A_OUTPORT1 = const(0x03)
PCAL6416A_POLINVPORT0 = const(0x04)
PCAL6416A_POLINVPORT1 = const(0x05)
PCAL6416A_CFGPORT0 = const(0x06)
PCAL6416A_CFGPORT1 = const(0x07)
PCAL6416A_OUTDRVST_REG00 = const(0x40)
PCAL6416A_OUTDRVST_REG01 = const(0x41)
PCAL6416A_OUTDRVST_REG10 = const(0x42)
PCAL6416A_OUTDRVST_REG11 = const(0x43)
PCAL6416A_INLAT_REG0 = const(0x44)
PCAL6416A_INLAT_REG1 = const(0x45)
PCAL6416A_PUPDEN_REG0 = const(0x46)
PCAL6416A_PUPDEN_REG1 = const(0x47)
PCAL6416A_PUPDSEL_REG0 = const(0x48)
PCAL6416A_PUPDSEL_REG1 = const(0x49)
PCAL6416A_INTMSK_REG0 = const(0x4A)
PCAL6416A_INTMSK_REG1 = const(0x4B)
PCAL6416A_INTSTAT_REG0 = const(0x4C)
PCAL6416A_INTSTAT_REG1 = const(0x4D)
PCAL6416A_OUTPORT_CONF = const(0x4F)

PCAL6416A_INPORT0_ARRAY = const(0)
PCAL6416A_INPORT1_ARRAY = const(1)
PCAL6416A_OUTPORT0_ARRAY = const(2)
PCAL6416A_OUTPORT1_ARRAY = const(3)
PCAL6416A_POLINVPORT0_ARRAY = const(4)
PCAL6416A_POLINVPORT1_ARRAY = const(5)
PCAL6416A_CFGPORT0_ARRAY = const(6)
PCAL6416A_CFGPORT1_ARRAY = const(7)
PCAL6416A_OUTDRVST_REG00_ARRAY = const(8)
PCAL6416A_OUTDRVST_REG01_ARRAY = const(9)
PCAL6416A_OUTDRVST_REG10_ARRAY = const(10)
PCAL6416A_OUTDRVST_REG11_ARRAY = const(11)
PCAL6416A_INLAT_REG0_ARRAY = const(12)
PCAL6416A_INLAT_REG1_ARRAY = const(13)
PCAL6416A_PUPDEN_REG0_ARRAY = const(14)
PCAL6416A_PUPDEN_REG1_ARRAY = const(15)
PCAL6416A_PUPDSEL_REG0_ARRAY = const(16)
PCAL6416A_PUPDSEL_REG1_ARRAY = const(17)
PCAL6416A_INTMSK_REG0_ARRAY = const(18)
PCAL6416A_INTMSK_REG1_ARRAY = const(19)
PCAL6416A_INTSTAT_REG0_ARRAY = const(20)
PCAL6416A_INTSTAT_REG1_ARRAY = const(21)
PCAL6416A_OUTPORT_CONF_ARRAY = const(22)

IO_PIN_A0 = const(0)
IO_PIN_A1 = const(1)
IO_PIN_A2 = const(2)
IO_PIN_A3 = const(3)
IO_PIN_A4 = const(4)
IO_PIN_A5 = const(5)
IO_PIN_A6 = const(6)
IO_PIN_A7 = const(7)
IO_PIN_B0 = const(8)
IO_PIN_B1 = const(9)
IO_PIN_B2 = const(10)
IO_PIN_B3 = const(11)
IO_PIN_B4 = const(12)
IO_PIN_B5 = const(13)
IO_PIN_B6 = const(14)
IO_PIN_B7 = const(15)

modeINPUT = const(0)
modeOUTPUT = const(1)
modeINPUT_PULLUP = const(2)
modeINPUT_PULLDOWN = const(3)

# PCAL6416A is a minimal driver for an 16-bit I2C I/O expander
class PCAL6416A:
    def __init__(self, i2c, addr=0x20):
        self.i2c = i2c
        self.addr = addr
        self.ioRegsInt = bytearray(23)

        self.ioRegsInt[0] = self.read(PCAL6416A_INPORT0)
        self.ioRegsInt[1] = self.read(PCAL6416A_INPORT1)
        self.ioRegsInt[2] = self.read(PCAL6416A_OUTPORT0)
        self.ioRegsInt[3] = self.read(PCAL6416A_OUTPORT1)
        self.ioRegsInt[4] = self.read(PCAL6416A_POLINVPORT0)
        self.ioRegsInt[5] = self.read(PCAL6416A_POLINVPORT1)
        self.ioRegsInt[6] = self.read(PCAL6416A_CFGPORT0)
        self.ioRegsInt[7] = self.read(PCAL6416A_CFGPORT1)
        self.ioRegsInt[8] = self.read(PCAL6416A_OUTDRVST_REG00)
        self.ioRegsInt[9] = self.read(PCAL6416A_OUTDRVST_REG01)
        self.ioRegsInt[10] = self.read(PCAL6416A_OUTDRVST_REG10)
        self.ioRegsInt[11] = self.read(PCAL6416A_OUTDRVST_REG11)
        self.ioRegsInt[12] = self.read(PCAL6416A_INLAT_REG0)
        self.ioRegsInt[13] = self.read(PCAL6416A_INLAT_REG1)
        self.ioRegsInt[14] = self.read(PCAL6416A_PUPDEN_REG0)
        self.ioRegsInt[15] = self.read(PCAL6416A_PUPDEN_REG1)
        self.ioRegsInt[16] = self.read(PCAL6416A_PUPDSEL_REG0)
        self.ioRegsInt[17] = self.read(PCAL6416A_PUPDSEL_REG1)
        self.ioRegsInt[18] = self.read(PCAL6416A_INTMSK_REG0)
        self.ioRegsInt[19] = self.read(PCAL6416A_INTMSK_REG1)
        self.ioRegsInt[20] = self.read(PCAL6416A_INTSTAT_REG0)
        self.ioRegsInt[21] = self.read(PCAL6416A_INTSTAT_REG1)
        self.ioRegsInt[22] = self.read(PCAL6416A_OUTPORT_CONF)

    # read an 8-bit register, internal method
    def read(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    # write an 8-bit register, internal method
    def write(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes((v,)))

    # write two 8-bit registers, internal method
    def write2(self, reg, v1, v2):
        self.i2c.writeto_mem(self.addr, reg, bytes((v1, v2)))

    # writebuf writes multiple bytes to the same register
    def writebuf(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, v)

    def pinMode(self, pin, mode):

        if (pin > 15):
            return

        port = pin // 8
        pin = pin % 8

        if (mode == modeINPUT):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] |= (1 << pin)
            self.write(PCAL6416A_CFGPORT0 + port,
                       self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
        elif (mode == modeOUTPUT):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] &= ~ (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] &= ~(1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port,
                       self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port,
                       self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
        elif (mode == modeINPUT_PULLUP):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port] |= (1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port,
                       self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port,
                       self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
            self.write(PCAL6416A_PUPDSEL_REG0 + port,
                       self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port])
        elif (mode == modeINPUT_PULLDOWN):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port] &= ~(1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port,
                       self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port,
                       self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
            self.write(PCAL6416A_PUPDSEL_REG0 + port,
                       self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port])

    def digitalWrite(self, pin, state):
        if (pin > 15):
            return

        state &= 1
        port = pin // 8
        pin %= 8

        if (state):
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] |= (1 << pin)
        else:
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] &= ~(1 << pin)

        self.write(PCAL6416A_OUTPORT0 + port,
                   self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])

    def digitalRead(self, pin):
        if (pin > 15):
            return

        port = pin // 8
        pin %= 8

        self.ioRegsInt[PCAL6416A_INPORT0_ARRAY +
            port] = self.read(PCAL6416A_INPORT0_ARRAY + port)
        return (self.ioRegsInt[PCAL6416A_INPORT0 + port] >> pin) & 1

class gpioPin:
    def __init__(self, PCAL6416A, pin, mode):
        self.PCAL6416A = PCAL6416A
        self.pin = pin
        self.PCAL6416A.pinMode(pin,mode)

    def digitalWrite(self, value):
        self.PCAL6416A.digitalWrite(self.pin,value)
    
    def digitalRead(self):
        return self.PCAL6416A.digitalRead(self.pin)