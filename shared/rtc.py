# PCF85263-style onboard RTC driver (I2C address 0x51). Shared across every board that
# wires one (Inkplate10/6/5v2) -- byte-for-byte identical logic on all three.

from micropython import const

RTC_I2C_ADDR = const(0x51)
_RTC_RAM_BYTE = const(0x03)
_RTC_DAY_ADDR = const(0x07)
_RTC_SECOND_ADDR = const(0x04)


def _dec_to_bcd(val):
    return (val // 10 * 16) + (val % 10)


def _bcd_to_dec(val):
    return (val // 16 * 10) + (val % 16)


class RTC:
    def __init__(self, i2c):
        self._i2c = i2c

    def set_time(self, hour, minute, second):
        data = bytearray(
            [
                _RTC_RAM_BYTE,
                170,  # Write in RAM 170 to know that RTC is set
                _dec_to_bcd(second),
                _dec_to_bcd(minute),
                _dec_to_bcd(hour),
            ]
        )

        self._i2c.writeto(RTC_I2C_ADDR, data)

    def set_date(self, weekday, day, month, yr):
        year = yr - 2000

        data = bytearray(
            [
                _RTC_RAM_BYTE,
                170,  # Write in RAM 170 to know that RTC is set
            ]
        )

        self._i2c.writeto(RTC_I2C_ADDR, data)

        data = bytearray(
            [
                _RTC_DAY_ADDR,
                _dec_to_bcd(day),
                _dec_to_bcd(weekday),
                _dec_to_bcd(month),
                _dec_to_bcd(year),
            ]
        )

        self._i2c.writeto(RTC_I2C_ADDR, data)

    def get_data(self):
        self._i2c.writeto(RTC_I2C_ADDR, bytearray([_RTC_SECOND_ADDR]))
        data = self._i2c.readfrom(RTC_I2C_ADDR, 7)

        second = _bcd_to_dec(data[0] & 0x7F)  # Ignore bit 7
        minute = _bcd_to_dec(data[1] & 0x7F)
        hour = _bcd_to_dec(data[2] & 0x3F)  # Ignore bits 7 & 6
        day = _bcd_to_dec(data[3] & 0x3F)
        weekday = _bcd_to_dec(data[4] & 0x07)  # Ignore bits 7,6,5,4 & 3
        month = _bcd_to_dec(data[5] & 0x1F)  # Ignore bits 7,6 & 5
        year = _bcd_to_dec(data[6]) + 2000

        return {
            "second": second,
            "minute": minute,
            "hour": hour,
            "day": day,
            "weekday": weekday,
            "month": month,
            "year": year,
        }
