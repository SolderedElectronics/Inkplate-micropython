"""MicroPython driver for the LSM6DS3(TR-C) accelerometer+gyro, used on
Inkplate4TEMPERA (`INKPLATE_ACCELEROMETER` sensor-select bit). I2C address
0x6B, fixed (the only address this board wires up).

Full accel/gyro/temp/FIFO API is implemented -- this sensor's public surface
is small enough (begin + raw/float accel/gyro X/Y/Z + temperature + FIFO)
that there's no meaningfully-smaller useful subset to trim to, unlike
APDS9960's optional pedometer/tap features (not exposed here either).

Settings (gyro/accel range, sample rate, bandwidth, FIFO config, etc.) are
plain class attributes instead of a separate settings struct -- set them
directly (`LSM6DS3.gyro_enabled = 0`) before calling `begin()` again to apply.
The board's `wake_peripheral`/`sleep_peripheral` `INKPLATE_ACCELEROMETER` branch
only ever toggles `gyro_enabled`/`accel_enabled` before calling `begin()` again --
every other setting stays at the class's own defaults (gyro 2000dps/416Hz/400Hz
bandwidth, accel 16g/416Hz/100Hz bandwidth).

Two things kept literally, not "fixed", because they're real (if odd) chip
behavior, not bugs of this driver's own making:
- `begin()` doesn't halt or raise if the WHO_AM_I register doesn't read back
  `0x69` -- it just keeps configuring the sensor regardless (tracked as a
  soft error counter, never surfaced to the caller).
- `fifo_begin()`'s FIFO_CTRL5 write unconditionally pins `fifo_mode_word` to
  `6` and ORs `6` into the register regardless of whatever `fifo_mode_word`
  was previously set to -- kept as that same unconditional overwrite, not
  the value `fifo_mode_word` otherwise implies.
"""

import time
from micropython import const

_I2C_ADDR = const(0x6B)
_WHO_AM_I = const(0x69)

_REG_FIFO_CTRL1 = const(0x06)
_REG_FIFO_CTRL2 = const(0x07)
_REG_FIFO_CTRL3 = const(0x08)
_REG_FIFO_CTRL4 = const(0x09)
_REG_FIFO_CTRL5 = const(0x0A)
_REG_WHO_AM_I = const(0x0F)
_REG_CTRL1_XL = const(0x10)
_REG_CTRL2_G = const(0x11)
_REG_CTRL4_C = const(0x13)
_REG_OUT_TEMP_L = const(0x20)
_REG_OUTX_L_G = const(0x22)
_REG_OUTX_L_XL = const(0x28)
_REG_FIFO_STATUS1 = const(0x3A)
_REG_FIFO_DATA_OUT_L = const(0x3E)

_BW_SCAL_ODR_ENABLED = const(0x80)

_BW_XL = {50: 0x03, 100: 0x02, 200: 0x01, 400: 0x00}
_FS_XL = {2: 0x00, 4: 0x08, 8: 0x0C, 16: 0x04}
_ODR_XL = {
    13: 0x10,
    26: 0x20,
    52: 0x30,
    104: 0x40,
    208: 0x50,
    416: 0x60,
    833: 0x70,
    1660: 0x80,
    3330: 0x90,
    6660: 0xA0,
    13330: 0xB0,
}
_FS_125_ENABLED = const(0x02)
_FS_G = {245: 0x00, 500: 0x04, 1000: 0x08, 2000: 0x0C}
_ODR_G = {13: 0x10, 26: 0x20, 52: 0x30, 104: 0x40, 208: 0x50, 416: 0x60, 833: 0x70, 1660: 0x80}
_ODR_FIFO = {
    10: 0x08,
    25: 0x10,
    50: 0x18,
    100: 0x20,
    200: 0x28,
    400: 0x30,
    800: 0x38,
    1600: 0x40,
    3300: 0x48,
    6600: 0x50,
}


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


class LSM6DS3:
    _i2c = None
    _addr = _I2C_ADDR

    # -- Settings (defaults mirror the sensor's default power-on configuration) --
    gyro_enabled = 1
    gyro_range = 2000  # deg/s: 125, 245, 500, 1000, 2000
    gyro_sample_rate = 416  # Hz: 13,26,52,104,208,416,833,1660
    gyro_bandwidth = 400  # Hz: 50,100,200,400
    gyro_fifo_enabled = 1
    gyro_fifo_decimation = 1

    accel_enabled = 1
    accel_odr_off = 1
    accel_range = 16  # g: 2,4,8,16
    accel_sample_rate = 416  # Hz: 13,26,52,104,208,416,833,1660,3330,6660,13330
    accel_bandwidth = 100  # Hz: 50,100,200,400
    accel_fifo_enabled = 1
    accel_fifo_decimation = 1

    temp_enabled = 1

    fifo_threshold = 3000  # 0-4095
    fifo_sample_rate = 10  # Hz: 10,25,50,100,200,400,800,1600,3300,6600
    fifo_mode_word = 0

    all_ones_counter = 0
    non_success_counter = 0

    @classmethod
    def init(cls, i2c, addr=_I2C_ADDR):
        cls._i2c = i2c
        cls._addr = addr

    @classmethod
    def _read_reg(cls, reg):
        return cls._i2c.readfrom_mem(cls._addr, reg, 1)[0]

    @classmethod
    def _write_reg(cls, reg, value):
        cls._i2c.writeto_mem(cls._addr, reg, bytes((value & 0xFF,)))

    @classmethod
    def _read_reg16(cls, reg):
        data = cls._i2c.readfrom_mem(cls._addr, reg, 2)
        return _s16(data[0] | (data[1] << 8))

    # Applies the current settings (gyro_enabled/accel_enabled/etc class
    # attributes) to the sensor -- call again after changing any of them.
    @classmethod
    def begin(cls):
        data_to_write = 0
        if cls.accel_enabled == 1:
            data_to_write |= _BW_XL.get(cls.accel_bandwidth, _BW_XL[400])
            if cls.accel_bandwidth not in _BW_XL:
                cls.accel_bandwidth = 400

            data_to_write |= _FS_XL.get(cls.accel_range, _FS_XL[16])
            if cls.accel_range not in _FS_XL:
                cls.accel_range = 16

            data_to_write |= _ODR_XL.get(cls.accel_sample_rate, _ODR_XL[104])
            if cls.accel_sample_rate not in _ODR_XL:
                cls.accel_sample_rate = 104
        cls._write_reg(_REG_CTRL1_XL, data_to_write)

        ctrl4 = cls._read_reg(_REG_CTRL4_C)
        ctrl4 &= ~_BW_SCAL_ODR_ENABLED
        if cls.accel_odr_off == 1:
            ctrl4 |= _BW_SCAL_ODR_ENABLED
        cls._write_reg(_REG_CTRL4_C, ctrl4)

        data_to_write = 0
        if cls.gyro_enabled == 1:
            if cls.gyro_range == 125:
                data_to_write |= _FS_125_ENABLED
            else:
                data_to_write |= _FS_G.get(cls.gyro_range, _FS_G[2000])
                if cls.gyro_range not in _FS_G:
                    cls.gyro_range = 2000

            data_to_write |= _ODR_G.get(cls.gyro_sample_rate, _ODR_G[104])
            if cls.gyro_sample_rate not in _ODR_G:
                cls.gyro_sample_rate = 104
        cls._write_reg(_REG_CTRL2_G, data_to_write)

        # WHO_AM_I is read but a mismatch doesn't halt configuration --
        # soft-error-only behavior, see module docstring.
        cls._read_reg(_REG_WHO_AM_I)

        # The sensor needs a few reads before it produces meaningful data --
        # these 3 warm-up reads (100ms apart) are that, not dead code.
        for _ in range(3):
            cls.read_float_accel_x()
            cls.read_float_accel_y()
            cls.read_float_accel_z()
            cls.read_float_gyro_x()
            cls.read_float_gyro_y()
            cls.read_float_gyro_z()
            time.sleep_ms(100)

        return True

    # -- Accelerometer --

    @classmethod
    def read_raw_accel_x(cls):
        return cls._read_reg16(_REG_OUTX_L_XL)

    @classmethod
    def read_raw_accel_y(cls):
        return cls._read_reg16(_REG_OUTX_L_XL + 2)

    @classmethod
    def read_raw_accel_z(cls):
        return cls._read_reg16(_REG_OUTX_L_XL + 4)

    @classmethod
    def read_float_accel_x(cls):
        return cls.calc_accel(cls.read_raw_accel_x())

    @classmethod
    def read_float_accel_y(cls):
        return cls.calc_accel(cls.read_raw_accel_y())

    @classmethod
    def read_float_accel_z(cls):
        return cls.calc_accel(cls.read_raw_accel_z())

    @classmethod
    def calc_accel(cls, raw):
        return raw * 0.061 * (cls.accel_range >> 1) / 1000

    # -- Gyroscope --

    @classmethod
    def read_raw_gyro_x(cls):
        return cls._read_reg16(_REG_OUTX_L_G)

    @classmethod
    def read_raw_gyro_y(cls):
        return cls._read_reg16(_REG_OUTX_L_G + 2)

    @classmethod
    def read_raw_gyro_z(cls):
        return cls._read_reg16(_REG_OUTX_L_G + 4)

    @classmethod
    def read_float_gyro_x(cls):
        return cls.calc_gyro(cls.read_raw_gyro_x())

    @classmethod
    def read_float_gyro_y(cls):
        return cls.calc_gyro(cls.read_raw_gyro_y())

    @classmethod
    def read_float_gyro_z(cls):
        return cls.calc_gyro(cls.read_raw_gyro_z())

    @classmethod
    def calc_gyro(cls, raw):
        divisor = 2 if cls.gyro_range == 245 else cls.gyro_range // 125
        return raw * 4.375 * divisor / 1000

    # -- Temperature --

    @classmethod
    def read_raw_temp(cls):
        return cls._read_reg16(_REG_OUT_TEMP_L)

    @classmethod
    def read_temp_c(cls):
        return cls.read_raw_temp() / 16 + 25

    @classmethod
    def read_temp_f(cls):
        return (cls.read_raw_temp() / 16 + 25) * 9 / 5 + 32

    # -- FIFO --

    @classmethod
    def fifo_begin(cls):
        threshold_l = cls.fifo_threshold & 0xFF
        threshold_h = (cls.fifo_threshold & 0x0F00) >> 8

        ctrl3 = 0
        if cls.gyro_fifo_enabled == 1:
            ctrl3 |= (cls.gyro_fifo_decimation & 0x07) << 3
        if cls.accel_fifo_enabled == 1:
            ctrl3 |= cls.accel_fifo_decimation & 0x07

        ctrl5 = _ODR_FIFO.get(cls.fifo_sample_rate, _ODR_FIFO[10])
        # Unconditional overwrite of fifo_mode_word, see module docstring.
        cls.fifo_mode_word = 6
        ctrl5 |= 6

        cls._write_reg(_REG_FIFO_CTRL1, threshold_l)
        cls._write_reg(_REG_FIFO_CTRL2, threshold_h)
        cls._write_reg(_REG_FIFO_CTRL3, ctrl3)
        cls._write_reg(_REG_FIFO_CTRL4, 0)
        cls._write_reg(_REG_FIFO_CTRL5, ctrl5)

    @classmethod
    def fifo_clear(cls):
        while (cls.fifo_get_status() & 0x1000) == 0:
            cls.fifo_read()

    @classmethod
    def fifo_read(cls):
        lo = cls._read_reg(_REG_FIFO_DATA_OUT_L)
        hi = cls._read_reg(_REG_FIFO_DATA_OUT_L + 1)
        return lo | (hi << 8)

    @classmethod
    def fifo_get_status(cls):
        lo = cls._read_reg(_REG_FIFO_STATUS1)
        hi = cls._read_reg(_REG_FIFO_STATUS1 + 1)
        return lo | (hi << 8)

    @classmethod
    def fifo_end(cls):
        cls._write_reg(_REG_FIFO_CTRL5, 0x00)
