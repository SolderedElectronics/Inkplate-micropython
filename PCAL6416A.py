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
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x20
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
            self.write(PCAL6416A_CFGPORT0 + port, self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
        elif (mode == modeOUTPUT):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] &= ~ (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] &= ~(1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port, self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port, self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
        elif (mode == modeINPUT_PULLUP):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port] |= (1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port, self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port, self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
            self.write(PCAL6416A_PUPDSEL_REG0 + port, self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port])
        elif (mode == modeINPUT_PULLDOWN):
            self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port] |= (1 << pin)
            self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port] &= ~(1 << pin)
            self.write(PCAL6416A_OUTPORT0 + port, self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])
            self.write(PCAL6416A_CFGPORT0 + port, self.ioRegsInt[PCAL6416A_CFGPORT0_ARRAY + port])
            self.write(PCAL6416A_PUPDSEL_REG0 + port, self.ioRegsInt[PCAL6416A_PUPDSEL_REG0_ARRAY + port])

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

        self.write(PCAL6416A_OUTPORT0 + port, self.ioRegsInt[PCAL6416A_OUTPORT0_ARRAY + port])

    def digitalRead(self, pin):
        if (pin > 15):
            return

        port = pin // 8
        pin %= 8

        self.ioRegsInt[PCAL6416A_INPORT0_ARRAY + port] = self.read(PCAL6416A_INPORT0_ARRAY + port)
        return (self.ioRegsInt[PCAL6416A_INPORT0 + port] >> pin) & 1

    # bit reads or sets a bit in a register, caching the gpio register for performance
    # def bit(self, reg, num, v=None):
    #    if v is None:
    #        data = self.read(reg)
    #        if reg == INPUT0:
    #            self.gpio_input0 = data
    #        elif reg == INPUT1:
    #            self.gpio_input1 = data
    #        return (data >> num) & 1
    #    else:
    #        mask = 0xFF ^ (1 << num)
    #        if reg == OUTPUT0:
    #            self.gpio_output0 = (self.gpio0 & mask) | ((v & 1) << num)
    #            self.write(reg, self.gpio_output0)
    #        elif reg == OUTPUT1:
    #            self.gpio_output1 = (self.gpio1 & mask) | ((v & 1) << num)
    #            self.write(reg, self.gpio_output1)
    #        else:
    #            data = (self.read(reg) & mask) | ((v & 1) << num)
    #            self.write(reg, data)
    # def pin(self, bank, num, mode=mPin.IN, pull=None, value=None):
    #    return Pin(self, bank, num, mode, pull, value)

## Pin implements a minimal machine. Pin look-alike for pins on the PCAL6416A
# class Pin:
#    def __init__(self, PCAL6416A, bank, num, mode=mPin.IN, pull=None, value=None):
#        self.bit = PCAL6416A.bit
#        if(mode == mPin.IN & bank == 0):
#            self.gpio_input0 = INPUT0
#        elif(mode == mPin.IN & bank == 1):
#            self.gpio_input1 = INPUT1
#        elif(mode == mPin.PULL_UP & bank == 0):
#            self.gpio_output0 = OUTPUT0
#        elif(mode==mPin.PULL_UP & bank == 1):
#            self.gpio_output1 = OUTPUT1
#
#        self.num = num
#        if value is not None:
#            self.bit(self.gpio, num, value)
#
#        if(bank == 0):
#            self.bit(IODIR0, num, 1 if mode == mPin.IN else 0)
#            self.bit(PULLUP0, num, 1 if pull == mPin.PULL_UP else 0)
#
#        else:
#            self.bit(IODIR0, num, 1 if mode == mPin.IN else 0)
#            self.bit(PULLUP0, num, 1 if pull == mPin.PULL_UP else 0)
#
#    # value reads or write a pin value (0 or 1)
#    def value(self, v=None):
#        if v is None:
#            return self.bit(self.gpio, self.num)
#        else:
#            self.bit(self.gpio, self.num, v)
#
#    __call__ = value


# Pin implements a minimal machine. Pin look-alike for pins on the PCAL6416A
# class Pin:
#    def __init__(self, PCAL6416A, num, mode=mPin.IN, pull=None, value=None):
#        self.bit = PCAL6416A.bit
#        incr = num >> 3  # bank selector
#        self.gpio = GPIO + incr
#        self.num = num = num & 0x7
#        if value is not None:
#            self.bit(self.gpio, num, value)
#        self.bit(IODIR + incr, num, 1 if mode == mPin.IN else 0)
#        self.bit(GPPU + incr, num, 1 if pull == mPin.PULL_UP else 0)
#
#    # value reads or write a pin value (0 or 1)
#    def value(self, v=None):
#        if v is None:
#            return self.bit(self.gpio, self.num)
#        else:
#            self.bit(self.gpio, self.num, v)
#
#    __call__ = value
#
