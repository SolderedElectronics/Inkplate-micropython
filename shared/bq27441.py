"""MicroPython driver for the BQ27441-G1 LiPo fuel gauge, used on
Inkplate4TEMPERA for battery monitoring (`INKPLATE_FUEL_GAUGE` sensor-select
bit / `FG_GPOUT` pin in the pasted pins.h -- this pass only wires the plain
I2C reads, not the GPOUT interrupt pin, same precedent as deferring
INT_APDS/INT1_LSM/INT2_LSM until their own sensors are ported).

Ported from the real SparkFun_BQ27441_Arduino_Library (vendored here under
Soldered's `BQ27441-G1-SOLDERED` wrapper, which subclasses it with no added
functionality of its own). Default I2C address 0x55 (`BQ72441_I2C_ADDRESS`).

Two of the reference driver's own conditionals are dead code, verified by
reading the whole reference source rather than guessed, and simplified away
here rather than ported literally:
- `i2cReadBytes()`/`i2cWriteBytes()` always return a truthy/`true` value (a
  `timeout` local that's initialized then never decremented, and a bare
  `return true`), so every `if (i2cReadBytes(...))`/`if (i2cWriteBytes(...))`
  guard built on top of them (`readControlWord`, `executeControlWord`,
  `blockDataControl`) is unreachable-false and always takes the true branch.
`_unseal()`'s own `if (readControlWord(UNSEAL_KEY))` is different -- that
checks the actual 16-bit word read back from the chip, a real (if unlikely)
conditional -- and is kept as a real `if` below.
"""

import time
from micropython import const

_I2C_ADDR = const(0x55)
_UNSEAL_KEY = const(0x8000)
_DEVICE_ID = const(0x0421)
_TIMEOUT_MS = const(2000)

# Standard commands
_CMD_TEMP = const(0x02)
_CMD_VOLTAGE = const(0x04)
_CMD_FLAGS = const(0x06)
_CMD_NOM_CAPACITY = const(0x08)
_CMD_AVAIL_CAPACITY = const(0x0A)
_CMD_REM_CAPACITY = const(0x0C)
_CMD_FULL_CAPACITY = const(0x0E)
_CMD_AVG_CURRENT = const(0x10)
_CMD_STDBY_CURRENT = const(0x12)
_CMD_MAX_CURRENT = const(0x14)
_CMD_AVG_POWER = const(0x18)
_CMD_SOC = const(0x1C)
_CMD_INT_TEMP = const(0x1E)
_CMD_SOH = const(0x20)
_CMD_REM_CAP_UNFL = const(0x28)
_CMD_REM_CAP_FIL = const(0x2A)
_CMD_FULL_CAP_UNFL = const(0x2C)
_CMD_FULL_CAP_FIL = const(0x2E)
_CMD_SOC_UNFL = const(0x30)

# Control sub-commands
_CTRL_STATUS = const(0x00)
_CTRL_DEVICE_TYPE = const(0x01)
_CTRL_SET_CFGUPDATE = const(0x13)
_CTRL_SHUTDOWN_ENABLE = const(0x1B)
_CTRL_SHUTDOWN = const(0x1C)
_CTRL_SEALED = const(0x20)
_CTRL_PULSE_SOC_INT = const(0x23)
_CTRL_SOFT_RESET = const(0x42)
_CTRL_EXIT_CFGUPDATE = const(0x43)

# Status/flags word bits
_STATUS_SS = const(1 << 13)
_FLAG_FC = const(1 << 9)
_FLAG_CHG = const(1 << 8)
_FLAG_ITPOR = const(1 << 5)
_FLAG_CFGUPMODE = const(1 << 4)
_FLAG_SOC1 = const(1 << 2)
_FLAG_SOCF = const(1 << 1)
_FLAG_DSG = const(1 << 0)

# Extended data commands
_EXT_OPCONFIG = const(0x3A)
_EXT_CAPACITY = const(0x3C)
_EXT_DATACLASS = const(0x3E)
_EXT_DATABLOCK = const(0x3F)
_EXT_BLOCKDATA = const(0x40)
_EXT_CHECKSUM = const(0x60)
_EXT_CONTROL = const(0x61)

# Configuration class IDs
_ID_DISCHARGE = const(49)
_ID_REGISTERS = const(64)
_ID_STATE = const(82)

# OpConfig register bits
_OPCONFIG_GPIOPOL = const(1 << 11)
_OPCONFIG_BATLOWEN = const(1 << 2)

# current() measurement-type selectors
CURRENT_AVG = const(0)
CURRENT_STBY = const(1)
CURRENT_MAX = const(2)

# capacity() measurement-type selectors
CAPACITY_REMAIN = const(0)
CAPACITY_FULL = const(1)
CAPACITY_AVAIL = const(2)
CAPACITY_AVAIL_FULL = const(3)
CAPACITY_REMAIN_F = const(4)
CAPACITY_REMAIN_UF = const(5)
CAPACITY_FULL_F = const(6)
CAPACITY_FULL_UF = const(7)
CAPACITY_DESIGN = const(8)

# soc() measurement-type selectors
SOC_FILTERED = const(0)
SOC_UNFILTERED = const(1)

# soh() measurement-type selectors
SOH_PERCENT = const(0)
SOH_STAT = const(1)

# temperature() measurement-type selectors
TEMP_BATTERY = const(0)
TEMP_INTERNAL = const(1)

# setGPOUTFunction() selectors
GPOUT_SOC_INT = const(0)
GPOUT_BAT_LOW = const(1)


def _to_int16(word):
    return word - 0x10000 if word & 0x8000 else word


class BQ27441:
    _i2c = None
    _addr = _I2C_ADDR
    _seal_flag = False
    _user_config_control = False

    @classmethod
    def init(cls, i2c, addr=_I2C_ADDR):
        cls._i2c = i2c
        cls._addr = addr

    @classmethod
    def begin(cls):
        return cls.device_type() == _DEVICE_ID

    # -- Configuration (design capacity/energy/terminate-voltage/taper-rate) --

    @classmethod
    def set_capacity(cls, capacity):
        return cls._write_extended_data(
            _ID_STATE, 10, bytes(((capacity >> 8) & 0xFF, capacity & 0xFF))
        )

    @classmethod
    def set_design_energy(cls, energy):
        return cls._write_extended_data(_ID_STATE, 12, bytes(((energy >> 8) & 0xFF, energy & 0xFF)))

    @classmethod
    def set_terminate_voltage(cls, voltage):
        voltage = min(max(voltage, 2500), 3700)
        return cls._write_extended_data(
            _ID_STATE, 16, bytes(((voltage >> 8) & 0xFF, voltage & 0xFF))
        )

    @classmethod
    def set_taper_rate(cls, rate):
        rate = min(rate, 2000)
        return cls._write_extended_data(_ID_STATE, 27, bytes(((rate >> 8) & 0xFF, rate & 0xFF)))

    # -- Battery characteristics --

    @classmethod
    def voltage(cls):
        return cls._read_word(_CMD_VOLTAGE)

    @classmethod
    def current(cls, measure=CURRENT_AVG):
        if measure == CURRENT_STBY:
            return _to_int16(cls._read_word(_CMD_STDBY_CURRENT))
        if measure == CURRENT_MAX:
            return _to_int16(cls._read_word(_CMD_MAX_CURRENT))
        return _to_int16(cls._read_word(_CMD_AVG_CURRENT))

    @classmethod
    def capacity(cls, measure=CAPACITY_REMAIN):
        if measure == CAPACITY_REMAIN:
            return cls._read_word(_CMD_REM_CAPACITY)
        if measure == CAPACITY_FULL:
            return cls._read_word(_CMD_FULL_CAPACITY)
        if measure == CAPACITY_AVAIL:
            return cls._read_word(_CMD_NOM_CAPACITY)
        if measure == CAPACITY_AVAIL_FULL:
            return cls._read_word(_CMD_AVAIL_CAPACITY)
        if measure == CAPACITY_REMAIN_F:
            return cls._read_word(_CMD_REM_CAP_FIL)
        if measure == CAPACITY_REMAIN_UF:
            return cls._read_word(_CMD_REM_CAP_UNFL)
        if measure == CAPACITY_FULL_F:
            return cls._read_word(_CMD_FULL_CAP_FIL)
        if measure == CAPACITY_FULL_UF:
            return cls._read_word(_CMD_FULL_CAP_UNFL)
        if measure == CAPACITY_DESIGN:
            return cls._read_word(_EXT_CAPACITY)
        return 0

    @classmethod
    def power(cls):
        return _to_int16(cls._read_word(_CMD_AVG_POWER))

    @classmethod
    def soc(cls, measure=SOC_FILTERED):
        if measure == SOC_UNFILTERED:
            return cls._read_word(_CMD_SOC_UNFL)
        return cls._read_word(_CMD_SOC)

    @classmethod
    def soh(cls, measure=SOH_PERCENT):
        raw = cls._read_word(_CMD_SOH)
        return raw & 0xFF if measure == SOH_PERCENT else raw >> 8

    @classmethod
    def temperature(cls, measure=TEMP_BATTERY):
        return cls._read_word(_CMD_INT_TEMP if measure == TEMP_INTERNAL else _CMD_TEMP)

    # -- GPOUT control --

    @classmethod
    def gpout_polarity(cls):
        return bool(cls._op_config() & _OPCONFIG_GPIOPOL)

    @classmethod
    def set_gpout_polarity(cls, active_high):
        old = cls._op_config()
        if bool(active_high) == bool(old & _OPCONFIG_GPIOPOL):
            return True
        new = (old | _OPCONFIG_GPIOPOL) if active_high else (old & ~_OPCONFIG_GPIOPOL)
        return cls._write_op_config(new)

    @classmethod
    def gpout_function(cls):
        return bool(cls._op_config() & _OPCONFIG_BATLOWEN)

    @classmethod
    def set_gpout_function(cls, function):
        old = cls._op_config()
        if bool(function) == bool(old & _OPCONFIG_BATLOWEN):
            return True
        new = (old | _OPCONFIG_BATLOWEN) if function else (old & ~_OPCONFIG_BATLOWEN)
        return cls._write_op_config(new)

    @classmethod
    def soc1_set_threshold(cls):
        return cls._read_extended_data(_ID_DISCHARGE, 0)

    @classmethod
    def soc1_clear_threshold(cls):
        return cls._read_extended_data(_ID_DISCHARGE, 1)

    @classmethod
    def set_soc1_thresholds(cls, set_pct, clear_pct):
        data = bytes((min(max(set_pct, 0), 100), min(max(clear_pct, 0), 100)))
        return cls._write_extended_data(_ID_DISCHARGE, 0, data)

    @classmethod
    def socf_set_threshold(cls):
        return cls._read_extended_data(_ID_DISCHARGE, 2)

    @classmethod
    def socf_clear_threshold(cls):
        return cls._read_extended_data(_ID_DISCHARGE, 3)

    @classmethod
    def set_socf_thresholds(cls, set_pct, clear_pct):
        data = bytes((min(max(set_pct, 0), 100), min(max(clear_pct, 0), 100)))
        return cls._write_extended_data(_ID_DISCHARGE, 2, data)

    @classmethod
    def soc_flag(cls):
        return bool(cls.flags() & _FLAG_SOC1)

    @classmethod
    def socf_flag(cls):
        return bool(cls.flags() & _FLAG_SOCF)

    @classmethod
    def itpor_flag(cls):
        return bool(cls.flags() & _FLAG_ITPOR)

    @classmethod
    def fc_flag(cls):
        return bool(cls.flags() & _FLAG_FC)

    @classmethod
    def chg_flag(cls):
        return bool(cls.flags() & _FLAG_CHG)

    @classmethod
    def dsg_flag(cls):
        return bool(cls.flags() & _FLAG_DSG)

    @classmethod
    def soci_delta(cls):
        return cls._read_extended_data(_ID_STATE, 26)

    @classmethod
    def set_soci_delta(cls, delta):
        return cls._write_extended_data(_ID_STATE, 26, bytes((min(max(delta, 0), 100),)))

    @classmethod
    def pulse_gpout(cls):
        return cls._execute_control_word(_CTRL_PULSE_SOC_INT)

    # -- Control sub-commands --

    @classmethod
    def device_type(cls):
        return cls._read_control_word(_CTRL_DEVICE_TYPE)

    @classmethod
    def enter_config(cls, user_control=True):
        if user_control:
            cls._user_config_control = True

        if cls._sealed():
            cls._seal_flag = True
            cls._unseal()  # must be unsealed before making changes

        cls._execute_control_word(_CTRL_SET_CFGUPDATE)
        timeout = _TIMEOUT_MS
        while timeout > 0 and not (cls.flags() & _FLAG_CFGUPMODE):
            time.sleep_ms(1)
            timeout -= 1
        return timeout > 0

    @classmethod
    def exit_config(cls, resim=True):
        # real driver's SOFT_RESET path (resim=True) forces a fresh OCV measurement
        # and SoC resimulation; EXIT_CFGUPDATE (resim=False) skips both
        if not resim:
            return cls._execute_control_word(_CTRL_EXIT_CFGUPDATE)

        cls._execute_control_word(_CTRL_SOFT_RESET)
        timeout = _TIMEOUT_MS
        while timeout > 0 and (cls.flags() & _FLAG_CFGUPMODE):
            time.sleep_ms(1)
            timeout -= 1
        if timeout <= 0:
            return False
        if cls._seal_flag:
            cls._seal()  # seal back up if the IC was sealed coming in
        return True

    @classmethod
    def flags(cls):
        return cls._read_word(_CMD_FLAGS)

    @classmethod
    def status(cls):
        return cls._read_control_word(_CTRL_STATUS)

    @classmethod
    def shutdown(cls):
        cls._read_control_word(_CTRL_SHUTDOWN_ENABLE)
        cls._read_control_word(_CTRL_SHUTDOWN)

    # -- Private helpers --

    @classmethod
    def _sealed(cls):
        return bool(cls.status() & _STATUS_SS)

    @classmethod
    def _seal(cls):
        return cls._read_control_word(_CTRL_SEALED)

    @classmethod
    def _unseal(cls):
        # real driver writes the unseal key twice in a row, but only attempts the
        # second write if the first one's readback came back nonzero
        if cls._read_control_word(_UNSEAL_KEY):
            return cls._read_control_word(_UNSEAL_KEY)
        return False

    @classmethod
    def _op_config(cls):
        return cls._read_word(_EXT_OPCONFIG)

    @classmethod
    def _write_op_config(cls, value):
        data = bytes(((value >> 8) & 0xFF, value & 0xFF))
        return cls._write_extended_data(_ID_REGISTERS, 0, data)

    @classmethod
    def _read_word(cls, sub_address):
        data = cls._i2c.readfrom_mem(cls._addr, sub_address, 2)
        return data[1] << 8 | data[0]

    @classmethod
    def _read_control_word(cls, function):
        command = bytes((function & 0xFF, (function >> 8) & 0xFF))
        cls._i2c.writeto_mem(cls._addr, 0, command)
        data = cls._i2c.readfrom_mem(cls._addr, 0, 2)
        return data[1] << 8 | data[0]

    @classmethod
    def _execute_control_word(cls, function):
        command = bytes((function & 0xFF, (function >> 8) & 0xFF))
        cls._i2c.writeto_mem(cls._addr, 0, command)
        return True

    # -- Extended data commands --

    @classmethod
    def _block_data_control(cls):
        cls._i2c.writeto_mem(cls._addr, _EXT_CONTROL, bytes((0x00,)))

    @classmethod
    def _block_data_class(cls, class_id):
        cls._i2c.writeto_mem(cls._addr, _EXT_DATACLASS, bytes((class_id,)))

    @classmethod
    def _block_data_offset(cls, offset):
        cls._i2c.writeto_mem(cls._addr, _EXT_DATABLOCK, bytes((offset,)))

    @classmethod
    def _block_data_checksum(cls):
        return cls._i2c.readfrom_mem(cls._addr, _EXT_CHECKSUM, 1)[0]

    @classmethod
    def _read_block_data(cls, offset):
        return cls._i2c.readfrom_mem(cls._addr, _EXT_BLOCKDATA + offset, 1)[0]

    @classmethod
    def _write_block_data(cls, offset, data):
        cls._i2c.writeto_mem(cls._addr, _EXT_BLOCKDATA + offset, bytes((data,)))

    @classmethod
    def _compute_block_checksum(cls):
        data = cls._i2c.readfrom_mem(cls._addr, _EXT_BLOCKDATA, 32)
        return 255 - (sum(data) & 0xFF)

    @classmethod
    def _write_block_checksum(cls, csum):
        cls._i2c.writeto_mem(cls._addr, _EXT_CHECKSUM, bytes((csum,)))

    @classmethod
    def _read_extended_data(cls, class_id, offset):
        if not cls._user_config_control:
            cls.enter_config(False)

        cls._block_data_control()
        cls._block_data_class(class_id)
        cls._block_data_offset(offset // 32)
        # real driver computes+reads the checksum here but never uses either
        # result before the actual data read below -- dead code, ported as-is
        cls._compute_block_checksum()
        cls._block_data_checksum()
        ret = cls._read_block_data(offset % 32)

        if not cls._user_config_control:
            cls.exit_config()

        return ret

    @classmethod
    def _write_extended_data(cls, class_id, offset, data):
        if len(data) > 32:
            return False

        if not cls._user_config_control:
            cls.enter_config(False)

        cls._block_data_control()
        cls._block_data_class(class_id)
        cls._block_data_offset(offset // 32)
        cls._compute_block_checksum()  # dead read, same as _read_extended_data above

        for i, byte in enumerate(data):
            cls._write_block_data((offset % 32) + i, byte)

        cls._write_block_checksum(cls._compute_block_checksum())

        if not cls._user_config_control:
            cls.exit_config()

        return True
