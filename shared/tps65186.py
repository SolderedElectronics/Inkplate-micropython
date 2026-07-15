# TPS65186 e-paper power-management IC driver (I2C address 0x48). Shared across every
# parallel-bus board (Inkplate10/6/6V2/5v2/6FLICK/6PLUSV2/4TEMPERA) -- same chip, same
# register sequence, ported from the real Arduino reference driver (TPS65186.cpp/.h).
# The Arduino source guards its I2C transactions with a semaphore (shared with something
# else on the same bus); not needed here since this project's I2C bus is single-owner.

import time

TPS65186_ADDR = const(0x48)

_REG_TEMP = const(0x00)
_REG_ENABLE = const(0x01)
_REG_UPSEQ0 = const(0x09)
_REG_DWNSEQ0 = const(0x0B)
_REG_TMST1 = const(0x0D)
_REG_PWRGOOD = const(0x0F)

_PWR_GOOD_OK = const(0b11111010)


class TPS65186:
    def __init__(self, i2c, wakeup_pin, pwrup_pin, vcom_pin):
        self._i2c = i2c
        self._wakeup = wakeup_pin
        self._pwrup = pwrup_pin
        self._vcom = vcom_pin
        self._powered_up = False

    # Program the power-up/power-down sequencer registers. Called once, before the
    # first power_up().
    def begin(self):
        self._wakeup.digital_write(1)
        time.sleep_ms(1)
        self._i2c.writeto_mem(TPS65186_ADDR, _REG_UPSEQ0, bytes((0x1B, 0x00, 0x1B, 0x00)))
        time.sleep_ms(1)
        self._wakeup.digital_write(0)

    def write_reg(self, reg, value):
        self._i2c.writeto_mem(TPS65186_ADDR, reg, bytes((value,)))

    def read_reg(self, reg):
        return self._i2c.readfrom_mem(TPS65186_ADDR, reg, 1)[0]

    def enable_rails(self, enable):
        self.write_reg(_REG_ENABLE, 0x20 if enable else 0x00)

    def read_power_good(self):
        return self.read_reg(_REG_PWRGOOD)

    def is_power_good(self):
        return self.read_power_good() == _PWR_GOOD_OK

    # Wake, enable rails, program the sequencers, assert PWRUP, wait for all rails to
    # report good, then enable VCOM. Returns False if PWR_GOOD didn't clear in time.
    def power_up(self, timeout_ms=250):
        self._wakeup.digital_write(1)
        time.sleep_ms(5)

        self.enable_rails(True)
        self.write_reg(_REG_UPSEQ0, 0xE4)
        self.write_reg(_REG_DWNSEQ0, 0x1B)

        self._pwrup.digital_write(1)

        start = time.ticks_ms()
        while not self.is_power_good() and time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            time.sleep_ms(1)

        if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
            return False

        self._vcom.digital_write(1)
        self._powered_up = True
        return True

    # Disable VCOM, de-assert PWRUP, wait for rails to collapse, then de-assert WAKEUP
    # and disable rails via I2C.
    def power_down(self, timeout_ms=250):
        self._vcom.digital_write(0)
        self._pwrup.digital_write(0)

        start = time.ticks_ms()
        while self.read_power_good() != 0 and time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            time.sleep_ms(1)

        self._wakeup.digital_write(0)
        self.enable_rails(False)
        self._powered_up = False

    # Reads the panel temperature from the TPS65186's internal sensor (-10..85 C, +-1C
    # from 0-50C per datasheet). Temporarily wakes the PMIC if it isn't already powered.
    def read_temperature(self):
        wake_for_temp = not self._powered_up
        if wake_for_temp:
            self._wakeup.digital_write(1)
            self._pwrup.digital_write(1)
            time.sleep_ms(5)

        self.write_reg(_REG_TMST1, 0x80)
        time.sleep_ms(5)
        temp = self.read_reg(_REG_TEMP)
        if temp > 127:  # int8_t cast, per the real driver
            temp -= 256

        if wake_for_temp:
            self._pwrup.digital_write(0)
            self._wakeup.digital_write(0)
            time.sleep_ms(5)

        return temp


# Reads the battery voltage via the ESP32's own ADC (GPIO35 through a resistor divider,
# unrelated to the TPS65186) -- duplicated identically across every board that wires it.
def read_battery_voltage(vbat_adc, vbat_en_pin):
    vbat_en_pin.digital_write(1)
    time.sleep_ms(1)
    value = vbat_adc.read()
    vbat_en_pin.digital_write(0)
    return (value / 4095.0) * 1.1 * 3.548133892 * 2


# Reads battery voltage via the same ESP32 ADC + resistor-divider scheme, but
# auto-detects which battery-MOSFET polarity the board uses instead of assuming one
# fixed revision: older boards pull the enable pin high at rest (PMOS-only), newer
# boards pull it low (PMOS+NMOS) -- ported from the real Arduino readBattery()
# (Inkplate6FLICK/Inkplate6PLUSV2). Takes the raw expander object (not a GpioPin
# wrapper) since the pin's mode must flip between input/output every call. Uses the
# ADC's calibrated microvolt reading (read_uv()), matching the Arduino driver's own
# analogReadMilliVolts(), rather than the raw-code/magic-constant formula above.
def read_battery_voltage_autodetect(expander, adc, pin=9):
    expander.pin_mode(pin, 0)  # mode_input
    state = expander.digital_read(pin)
    expander.pin_mode(pin, 1)  # mode_output
    expander.digital_write(pin, 0 if state else 1)
    time.sleep_ms(5)

    micro_volts = adc.read_uv()

    expander.digital_write(pin, 1 if state else 0)

    return micro_volts * 2.0 / 1_000_000
