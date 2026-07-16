"""MicroPython driver for the Bosch BME688 environmental sensor (temperature/
pressure/humidity/gas resistance), used on Inkplate4TEMPERA (`INKPLATE_BME688`
sensor-select bit in the pasted pins.h). I2C address 0x76 (`BME68X_I2C_ADDR_LOW`)
-- 0x77 is also valid per the chip's SDO strap, not used on this board.

Ported from the real Bosch `bme68x.c`/`bme68xLibrary.cpp` (BSD-3-Clause, vendored
in this repo) via Soldered's `BME680-SOLDERED.cpp` wrapper, which only exercises a
narrow slice of the full Bosch API: I2C only (no SPI), forced mode only (no
parallel/sequential multi-profile heating), one fixed TPH-oversampling/filter/
heater config applied once at `begin()`. Only that slice is ported -- self-test,
SPI, the multi-profile heater API, and sequential-mode ODR are all dropped
entirely (real driver features Inkplate4TEMPERA's own code never reaches).

Floating-point compensation formulas only, matching the real driver's default
`BME68X_USE_FPU` build (the vendored source's non-FPU integer-math variant is
unreachable dead code on this build, never compiled by the real firmware either).

`init()` only stores the I2C bus/address (no traffic, mirrors bq27441.py's
`init()`) -- actual chip bring-up (soft reset, calibration read, TPH/filter/
heater config) is `begin()`, matching the real `Bme68x::begin()`'s name, called
only from `wake_peripheral(INKPLATE_BME688)` in the board file, same as the real
`EPDDriver::wakePeripheral()`'s `INKPLATE_BME688` branch (this chip has no true
I2C-disabling shutdown like the fuel gauge -- SLEEP mode still ACKs I2C, so no
wake-before-first-touch ordering hazard here).
"""

import time
from micropython import const

_CHIP_ID = const(0x61)

_REG_COEFF3 = const(0x00)
_REG_FIELD0 = const(0x1D)
_REG_RES_HEAT0 = const(0x5A)
_REG_GAS_WAIT0 = const(0x64)
_REG_CTRL_GAS_0 = const(0x70)
_REG_CTRL_GAS_1 = const(0x71)
_REG_CTRL_HUM = const(0x72)
_REG_CTRL_MEAS = const(0x74)
_REG_CONFIG = const(0x75)
_REG_CHIP_ID = const(0xD0)
_REG_SOFT_RESET = const(0xE0)
_REG_COEFF1 = const(0x8A)
_REG_COEFF2 = const(0xE1)
_REG_VARIANT_ID = const(0xF0)

_SOFT_RESET_CMD = const(0xB6)

_VARIANT_GAS_HIGH = const(1)

OS_NONE = const(0)
OS_1X = const(1)
OS_2X = const(2)
OS_4X = const(3)
OS_8X = const(4)
OS_16X = const(5)

FILTER_OFF = const(0)
FILTER_SIZE_1 = const(1)
FILTER_SIZE_3 = const(2)
FILTER_SIZE_7 = const(3)
FILTER_SIZE_15 = const(4)
FILTER_SIZE_31 = const(5)
FILTER_SIZE_63 = const(6)
FILTER_SIZE_127 = const(7)

_SLEEP_MODE = const(0)
_FORCED_MODE = const(1)

_NEW_DATA_MSK = const(0x80)
_GAS_RANGE_MSK = const(0x0F)

_MODE_MSK = const(0x03)
_FILTER_MSK = const(0x1C)
_FILTER_POS = const(2)
_OST_MSK = const(0xE0)
_OST_POS = const(5)
_OSP_MSK = const(0x1C)
_OSP_POS = const(2)
_OSH_MSK = const(0x07)
_HCTRL_MSK = const(0x08)
_HCTRL_POS = const(3)
_RUN_GAS_MSK = const(0x30)
_RUN_GAS_POS = const(4)
_NBCONV_MSK = const(0x0F)

_ENABLE_HEATER = const(0x00)
_ENABLE_GAS_MEAS_L = const(0x01)
_ENABLE_GAS_MEAS_H = const(0x02)

_MEAS_CYCLES = (0, 1, 2, 4, 8, 16)

_GAS_LOOKUP_K1 = (
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    0.0,
    -0.8,
    0.0,
    0.0,
    -0.2,
    -0.5,
    0.0,
    -1.0,
    0.0,
    0.0,
)
_GAS_LOOKUP_K2 = (
    0.0,
    0.0,
    0.0,
    0.0,
    0.1,
    0.7,
    0.0,
    -0.8,
    -0.1,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
)


def _s8(v):
    return v - 256 if v & 0x80 else v


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


class BME688:
    _i2c = None
    _addr = 0x76
    _amb_temp = 25
    _variant_id = 0

    _os_temp = OS_2X
    _os_pres = OS_16X
    _os_hum = OS_1X
    _filter = FILTER_OFF

    _heatr_temp = 300
    _heatr_dur = 100

    @classmethod
    def init(cls, i2c, addr=0x76):
        cls._i2c = i2c
        cls._addr = addr

    @classmethod
    def read_reg(cls, reg):
        return cls._i2c.readfrom_mem(cls._addr, reg, 1)[0]

    @classmethod
    def write_reg(cls, reg, value):
        cls._i2c.writeto_mem(cls._addr, reg, bytes((value & 0xFF,)))

    # Real Bme68x::begin(): soft reset + chip-id check + calibration read, then
    # (Soldered's own BME680-SOLDERED.cpp begin()) apply the fixed TPH 16x/16x/16x
    # + filter-size-3 + 320C/150ms heater profile this board always uses.
    @classmethod
    def begin(cls):
        cls._soft_reset()
        chip_id = cls.read_reg(_REG_CHIP_ID)
        if chip_id != _CHIP_ID:
            raise OSError("BME688 not found (chip id 0x%02x)" % chip_id)
        cls._variant_id = cls.read_reg(_REG_VARIANT_ID)
        cls._read_calib_data()

        cls._os_temp = OS_16X
        cls._os_pres = OS_16X
        cls._os_hum = OS_16X
        cls._filter = FILTER_SIZE_3
        cls._set_conf()

        cls._heatr_temp = 320
        cls._heatr_dur = 150
        cls._set_heater_conf()
        return True

    @classmethod
    def read_temperature(cls):
        return cls._read_data()[0]

    @classmethod
    def read_pressure(cls):
        return cls._read_data()[1] / 100.0

    @classmethod
    def read_humidity(cls):
        return cls._read_data()[2]

    # matches the real readGasResistance()'s literal /100.0f -- an odd unit
    # scaling (unlike pressure's Pa->hPa /100), but ported as-is, not "fixed"
    @classmethod
    def read_gas_resistance(cls):
        return cls._read_data()[3] / 100.0

    @classmethod
    def read_sensor_data(cls):
        temperature, pressure, humidity, gas = cls._read_data()
        return temperature, humidity, pressure / 100.0, gas / 100.0

    @classmethod
    def read_altitude(cls, sea_level_hpa=1013.25):
        _, pressure, _, _ = cls._read_data()
        return cls.calculate_altitude(pressure / 100.0, sea_level_hpa)

    @classmethod
    def calculate_altitude(cls, pressure_hpa, sea_level_hpa=1013.25):
        return 44330.0 * (1.0 - (pressure_hpa / sea_level_hpa) ** 0.1903)

    # -- Internals --

    @classmethod
    def _soft_reset(cls):
        cls.write_reg(_REG_SOFT_RESET, _SOFT_RESET_CMD)
        time.sleep_us(10000)

    @classmethod
    def _read_calib_data(cls):
        c = bytearray(23 + 14 + 5)
        c[0:23] = cls._i2c.readfrom_mem(cls._addr, _REG_COEFF1, 23)
        c[23:37] = cls._i2c.readfrom_mem(cls._addr, _REG_COEFF2, 14)
        c[37:42] = cls._i2c.readfrom_mem(cls._addr, _REG_COEFF3, 5)

        cls._par_t1 = (c[32] << 8) | c[31]
        cls._par_t2 = _s16((c[1] << 8) | c[0])
        cls._par_t3 = _s8(c[2])

        cls._par_p1 = (c[5] << 8) | c[4]
        cls._par_p2 = _s16((c[7] << 8) | c[6])
        cls._par_p3 = _s8(c[8])
        cls._par_p4 = _s16((c[11] << 8) | c[10])
        cls._par_p5 = _s16((c[13] << 8) | c[12])
        cls._par_p7 = _s8(c[14])
        cls._par_p6 = _s8(c[15])
        cls._par_p8 = _s16((c[19] << 8) | c[18])
        cls._par_p9 = _s16((c[21] << 8) | c[20])
        cls._par_p10 = c[22]

        cls._par_h1 = (c[25] << 4) | (c[24] & 0x0F)
        cls._par_h2 = (c[23] << 4) | (c[24] >> 4)
        cls._par_h3 = _s8(c[26])
        cls._par_h4 = _s8(c[27])
        cls._par_h5 = _s8(c[28])
        cls._par_h6 = c[29]
        cls._par_h7 = _s8(c[30])

        cls._par_gh1 = _s8(c[35])
        cls._par_gh2 = _s16((c[34] << 8) | c[33])
        cls._par_gh3 = _s8(c[36])

        cls._res_heat_range = (c[39] & 0x30) // 16
        cls._res_heat_val = _s8(c[37])
        cls._range_sw_err = _s8(c[41] & 0xF0) // 16

    @classmethod
    def _set_op_mode(cls, op_mode):
        # bounded (real driver polls unbounded every 10ms) -- 200 tries * 10ms = 2s
        current = 0
        tries = 200
        while tries:
            current = cls.read_reg(_REG_CTRL_MEAS)
            if (current & _MODE_MSK) == _SLEEP_MODE:
                break
            cls.write_reg(_REG_CTRL_MEAS, current & ~_MODE_MSK)
            time.sleep_us(10000)
            tries -= 1
        else:
            raise OSError("BME688 stuck out of sleep mode")

        if op_mode != _SLEEP_MODE:
            cls.write_reg(_REG_CTRL_MEAS, (current & ~_MODE_MSK) | (op_mode & _MODE_MSK))

    # Real bme68x_set_regs() doesn't do a plain auto-increment burst write for
    # multi-register writes -- it interleaves reg_addr/reg_data pairs
    # ([addr0,data0,addr1,data1,...]) into one write transaction. Confirmed
    # empirically (not guessed): a plain writeto_mem() burst here only landed the
    # first byte, silently no-op'ing the rest -- this chip's I2C register map does
    # not auto-increment through a simple multi-byte write the way the PCAL6416A/
    # MCP4018 on this same board do.
    @classmethod
    def _write_regs(cls, addrs, data):
        buf = bytearray(2 * len(addrs))
        for i, addr in enumerate(addrs):
            buf[2 * i] = addr
            buf[2 * i + 1] = data[i]
        cls._i2c.writeto(cls._addr, bytes(buf))

    @classmethod
    def _set_conf(cls):
        cls._set_op_mode(_SLEEP_MODE)
        data = bytearray(cls._i2c.readfrom_mem(cls._addr, _REG_CTRL_GAS_1, 5))
        data[4] = (data[4] & ~_FILTER_MSK) | ((cls._filter << _FILTER_POS) & _FILTER_MSK)
        data[3] = (data[3] & ~_OST_MSK) | ((cls._os_temp << _OST_POS) & _OST_MSK)
        data[3] = (data[3] & ~_OSP_MSK) | ((cls._os_pres << _OSP_POS) & _OSP_MSK)
        data[1] = (data[1] & ~_OSH_MSK) | (cls._os_hum & _OSH_MSK)
        # odr left at BME68X_ODR_NONE (sequential mode unused): odr20=0, odr3=1
        data[4] = data[4] & ~0xE0
        data[0] = (data[0] & ~0x80) | 0x80
        cls._write_regs((_REG_CTRL_GAS_1, _REG_CTRL_HUM, 0x73, _REG_CTRL_MEAS, _REG_CONFIG), data)

    @classmethod
    def _set_heater_conf(cls):
        cls._set_op_mode(_SLEEP_MODE)
        cls.write_reg(_REG_RES_HEAT0, cls._calc_res_heat(cls._heatr_temp))
        cls.write_reg(_REG_GAS_WAIT0, cls._calc_gas_wait(cls._heatr_dur))

        ctrl = bytearray(cls._i2c.readfrom_mem(cls._addr, _REG_CTRL_GAS_0, 2))
        run_gas = _ENABLE_GAS_MEAS_H if cls._variant_id == _VARIANT_GAS_HIGH else _ENABLE_GAS_MEAS_L
        ctrl[0] = (ctrl[0] & ~_HCTRL_MSK) | ((_ENABLE_HEATER << _HCTRL_POS) & _HCTRL_MSK)
        ctrl[1] = ctrl[1] & ~_NBCONV_MSK  # nb_conv=0, forced mode
        ctrl[1] = (ctrl[1] & ~_RUN_GAS_MSK) | ((run_gas << _RUN_GAS_POS) & _RUN_GAS_MSK)
        cls._write_regs((_REG_CTRL_GAS_0, _REG_CTRL_GAS_1), ctrl)

    @classmethod
    def _get_meas_dur(cls):
        meas_cycles = (
            _MEAS_CYCLES[cls._os_temp] + _MEAS_CYCLES[cls._os_pres] + _MEAS_CYCLES[cls._os_hum]
        )
        meas_dur = meas_cycles * 1963
        meas_dur += 477 * 4  # TPH switching duration
        meas_dur += 477 * 5  # gas measurement duration
        meas_dur += 1000  # wake-up duration (forced mode)
        return meas_dur

    @classmethod
    def _read_data(cls):
        cls._set_op_mode(_FORCED_MODE)
        time.sleep_us(cls._get_meas_dur() + cls._heatr_dur * 1000)
        return cls._read_field_data()

    @classmethod
    def _read_field_data(cls):
        for _ in range(5):
            buf = cls._i2c.readfrom_mem(cls._addr, _REG_FIELD0, 17)
            if buf[0] & _NEW_DATA_MSK:
                adc_pres = (buf[2] << 12) | (buf[3] << 4) | (buf[4] >> 4)
                adc_temp = (buf[5] << 12) | (buf[6] << 4) | (buf[7] >> 4)
                adc_hum = (buf[8] << 8) | buf[9]

                if cls._variant_id == _VARIANT_GAS_HIGH:
                    adc_gas_res = (buf[15] << 2) | (buf[16] >> 6)
                    gas_range = buf[16] & _GAS_RANGE_MSK
                    gas_resistance = cls._calc_gas_resistance_high(adc_gas_res, gas_range)
                else:
                    adc_gas_res = (buf[13] << 2) | (buf[14] >> 6)
                    gas_range = buf[14] & _GAS_RANGE_MSK
                    gas_resistance = cls._calc_gas_resistance_low(adc_gas_res, gas_range)

                temperature, t_fine = cls._calc_temperature(adc_temp)
                pressure = cls._calc_pressure(adc_pres, t_fine)
                humidity = cls._calc_humidity(adc_hum, t_fine)
                return temperature, pressure, humidity, gas_resistance

            time.sleep_us(10000)

        raise OSError("BME688: no new data")

    @classmethod
    def _calc_temperature(cls, temp_adc):
        var1 = ((temp_adc / 16384.0) - (cls._par_t1 / 1024.0)) * cls._par_t2
        var2 = ((temp_adc / 131072.0) - (cls._par_t1 / 8192.0)) ** 2 * (cls._par_t3 * 16.0)
        t_fine = var1 + var2
        return t_fine / 5120.0, t_fine

    @classmethod
    def _calc_pressure(cls, pres_adc, t_fine):
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * (cls._par_p6 / 131072.0)
        var2 = var2 + (var1 * cls._par_p5 * 2.0)
        var2 = (var2 / 4.0) + (cls._par_p4 * 65536.0)
        var1 = (((cls._par_p3 * var1 * var1) / 16384.0) + (cls._par_p2 * var1)) / 524288.0
        var1 = (1.0 + (var1 / 32768.0)) * cls._par_p1
        calc_pres = 1048576.0 - pres_adc

        if int(var1) == 0:
            return 0.0

        calc_pres = ((calc_pres - (var2 / 4096.0)) * 6250.0) / var1
        var1 = (cls._par_p9 * calc_pres * calc_pres) / 2147483648.0
        var2 = calc_pres * (cls._par_p8 / 32768.0)
        var3 = (calc_pres / 256.0) ** 3 * (cls._par_p10 / 131072.0)
        return calc_pres + (var1 + var2 + var3 + (cls._par_p7 * 128.0)) / 16.0

    @classmethod
    def _calc_humidity(cls, hum_adc, t_fine):
        temp_comp = t_fine / 5120.0
        var1 = hum_adc - ((cls._par_h1 * 16.0) + ((cls._par_h3 / 2.0) * temp_comp))
        var2 = var1 * (
            (cls._par_h2 / 262144.0)
            * (
                1.0
                + ((cls._par_h4 / 16384.0) * temp_comp)
                + ((cls._par_h5 / 1048576.0) * temp_comp * temp_comp)
            )
        )
        var3 = cls._par_h6 / 16384.0
        var4 = cls._par_h7 / 2097152.0
        calc_hum = var2 + ((var3 + (var4 * temp_comp)) * var2 * var2)
        return min(max(calc_hum, 0.0), 100.0)

    @classmethod
    def _calc_gas_resistance_low(cls, gas_res_adc, gas_range):
        var1 = 1340.0 + (5.0 * cls._range_sw_err)
        var2 = var1 * (1.0 + _GAS_LOOKUP_K1[gas_range] / 100.0)
        var3 = 1.0 + (_GAS_LOOKUP_K2[gas_range] / 100.0)
        return 1.0 / (
            var3 * 0.000000125 * (1 << gas_range) * (((gas_res_adc - 512.0) / var2) + 1.0)
        )

    @classmethod
    def _calc_gas_resistance_high(cls, gas_res_adc, gas_range):
        var1 = 262144 >> gas_range
        var2 = ((gas_res_adc - 512) * 3) + 4096
        return 1000000.0 * var1 / var2

    @classmethod
    def _calc_res_heat(cls, temp):
        temp = min(temp, 400)
        var1 = (cls._par_gh1 / 16.0) + 49.0
        var2 = ((cls._par_gh2 / 32768.0) * 0.0005) + 0.00235
        var3 = cls._par_gh3 / 1024.0
        var4 = var1 * (1.0 + (var2 * temp))
        var5 = var4 + (var3 * cls._amb_temp)
        res_heat = 3.4 * (
            (var5 * (4 / (4 + cls._res_heat_range)) * (1 / (1 + (cls._res_heat_val * 0.002)))) - 25
        )
        return int(res_heat) & 0xFF

    @classmethod
    def _calc_gas_wait(cls, dur):
        if dur >= 0xFC0:
            return 0xFF
        factor = 0
        d = dur
        while d > 0x3F:
            d //= 4
            factor += 1
        return d + factor * 64
