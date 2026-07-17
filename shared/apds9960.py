"""MicroPython driver for the APDS-9960 gesture/proximity/ambient-light
sensor, used on Inkplate4TEMPERA (`INKPLATE_APDS9960` sensor-select bit). I2C
address 0x39, fixed -- not configurable on the chip either.

Full API surface is implemented -- gesture detection + proximity + ambient
light/color + interrupt config -- not a trimmed subset like the fuel gauge/
BME688 drivers. Gesture detection specifically is a nontrivial state machine
(FIFO buffering, then first/last-sample ratio deltas -> swipe direction).

Two things worth noting about how this is structured:
- Every register accessor's repeated "read register, clear a bitfield mask, OR
  in the shifted new value, write back" boilerplate is collapsed into two
  small helpers (`_get_bits`/`_set_bits`); each (register, mask, position)
  triple was derived from the chip's own register map.
- There's no per-call success-checking on I2C transactions: a failed I2C
  transaction raises `OSError` naturally in MicroPython, so there's no
  silent-failure mode to guard against.

`begin()` (chip bring-up: ID check + full register defaults) is left for the
*caller* to invoke, not run automatically -- `wake_peripheral(INKPLATE_APDS9960)`
in the board file only powers the chip on; call `APDS9960.begin()` yourself
afterward before using gesture/proximity/light.
"""

import time
from micropython import const

_I2C_ADDR = const(0x39)

_ID_1 = const(0xAB)
_ID_2 = const(0x9C)

_FIFO_PAUSE_MS = const(30)

# Registers
_REG_ENABLE = const(0x80)
_REG_ATIME = const(0x81)
_REG_WTIME = const(0x83)
_REG_AILTL = const(0x84)
_REG_AILTH = const(0x85)
_REG_AIHTL = const(0x86)
_REG_AIHTH = const(0x87)
_REG_PILT = const(0x89)
_REG_PIHT = const(0x8B)
_REG_PERS = const(0x8C)
_REG_CONFIG1 = const(0x8D)
_REG_PPULSE = const(0x8E)
_REG_CONTROL = const(0x8F)
_REG_CONFIG2 = const(0x90)
_REG_ID = const(0x92)
_REG_STATUS = const(0x93)
_REG_CDATAL = const(0x94)
_REG_CDATAH = const(0x95)
_REG_RDATAL = const(0x96)
_REG_RDATAH = const(0x97)
_REG_GDATAL = const(0x98)
_REG_GDATAH = const(0x99)
_REG_BDATAL = const(0x9A)
_REG_BDATAH = const(0x9B)
_REG_PDATA = const(0x9C)
_REG_POFFSET_UR = const(0x9D)
_REG_POFFSET_DL = const(0x9E)
_REG_CONFIG3 = const(0x9F)
_REG_GPENTH = const(0xA0)
_REG_GEXTH = const(0xA1)
_REG_GCONF1 = const(0xA2)
_REG_GCONF2 = const(0xA3)
_REG_GOFFSET_U = const(0xA4)
_REG_GOFFSET_D = const(0xA5)
_REG_GPULSE = const(0xA6)
_REG_GOFFSET_L = const(0xA7)
_REG_GOFFSET_R = const(0xA9)
_REG_GCONF3 = const(0xAA)
_REG_GCONF4 = const(0xAB)
_REG_GFLVL = const(0xAE)
_REG_GSTATUS = const(0xAF)
_REG_PICLEAR = const(0xE5)
_REG_AICLEAR = const(0xE7)
_REG_GFIFO_U = const(0xFC)

_GVALID = const(0x01)
_PON_GEN_MSK = const(0b01000001)  # PON (bit0) | GEN (bit6)

# setMode() mode selectors
MODE_POWER = const(0)
MODE_AMBIENT_LIGHT = const(1)
MODE_PROXIMITY = const(2)
MODE_WAIT = const(3)
MODE_AMBIENT_LIGHT_INT = const(4)
MODE_PROXIMITY_INT = const(5)
MODE_GESTURE = const(6)
MODE_ALL = const(7)

LED_DRIVE_100MA = const(0)
LED_DRIVE_50MA = const(1)
LED_DRIVE_25MA = const(2)
LED_DRIVE_12_5MA = const(3)

PGAIN_1X = const(0)
PGAIN_2X = const(1)
PGAIN_4X = const(2)
PGAIN_8X = const(3)

AGAIN_1X = const(0)
AGAIN_4X = const(1)
AGAIN_16X = const(2)
AGAIN_64X = const(3)

GGAIN_1X = const(0)
GGAIN_2X = const(1)
GGAIN_4X = const(2)
GGAIN_8X = const(3)

LED_BOOST_100 = const(0)
LED_BOOST_150 = const(1)
LED_BOOST_200 = const(2)
LED_BOOST_300 = const(3)

GWTIME_0MS = const(0)
GWTIME_2_8MS = const(1)
GWTIME_5_6MS = const(2)
GWTIME_8_4MS = const(3)
GWTIME_14_0MS = const(4)
GWTIME_22_4MS = const(5)
GWTIME_30_8MS = const(6)
GWTIME_39_2MS = const(7)

_DEFAULT_ATIME = const(219)
_DEFAULT_WTIME = const(246)
_DEFAULT_PROX_PPULSE = const(0x87)
_DEFAULT_GESTURE_PPULSE = const(0x89)
_DEFAULT_CONFIG1 = const(0x60)
_DEFAULT_LDRIVE = LED_DRIVE_100MA
_DEFAULT_PGAIN = PGAIN_4X
_DEFAULT_AGAIN = AGAIN_4X
_DEFAULT_PILT = const(0)
_DEFAULT_PIHT = const(50)
_DEFAULT_AILT = const(0xFFFF)
_DEFAULT_AIHT = const(0)
_DEFAULT_PERS = const(0x11)
_DEFAULT_CONFIG2 = const(0x01)
_DEFAULT_CONFIG3 = const(0)
_DEFAULT_GPENTH = const(40)
_DEFAULT_GEXTH = const(30)
_DEFAULT_GCONF1 = const(0x40)
_DEFAULT_GGAIN = GGAIN_4X
_DEFAULT_GLDRIVE = LED_DRIVE_100MA
_DEFAULT_GWTIME = GWTIME_2_8MS
_DEFAULT_GPULSE = const(0xC9)
_DEFAULT_GCONF3 = const(0)
_DEFAULT_GIEN = const(0)

_GESTURE_THRESHOLD_OUT = const(10)
_GESTURE_SENSITIVITY_1 = const(50)
_GESTURE_SENSITIVITY_2 = const(20)

DIR_NONE = const(0)
DIR_LEFT = const(1)
DIR_RIGHT = const(2)
DIR_UP = const(3)
DIR_DOWN = const(4)
DIR_NEAR = const(5)
DIR_FAR = const(6)
DIR_ALL = const(7)

_NA_STATE = const(0)
_NEAR_STATE = const(1)
_FAR_STATE = const(2)


def _c_idiv(a, b):
    # C-style truncate-toward-zero integer division, unlike Python's floor `//`
    # -- the first/last-ratio deltas below go negative routinely.
    q = a // b
    if a % b != 0 and (a < 0) != (b < 0):
        q += 1
    return q


class APDS9960:
    _i2c = None
    _addr = _I2C_ADDR

    _gesture_index = 0
    _gesture_total = 0
    _gesture_ud_delta = 0
    _gesture_lr_delta = 0
    _gesture_ud_count = 0
    _gesture_lr_count = 0
    _gesture_near_count = 0
    _gesture_far_count = 0
    _gesture_state = _NA_STATE
    _gesture_motion = DIR_NONE

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
    def _get_bits(cls, reg, mask, pos=0):
        return (cls._read_reg(reg) & mask) >> pos

    @classmethod
    def _set_bits(cls, reg, mask, pos, value):
        val = cls._read_reg(reg)
        val = (val & ~mask) | ((value << pos) & mask)
        cls._write_reg(reg, val)

    @classmethod
    def _read_word(cls, reg_low, reg_high):
        return cls._read_reg(reg_low) | (cls._read_reg(reg_high) << 8)

    @classmethod
    def _write_word(cls, reg_low, reg_high, value):
        cls._write_reg(reg_low, value & 0xFF)
        cls._write_reg(reg_high, (value >> 8) & 0xFF)

    # Chip bring-up (ID check + full register defaults) -- not run
    # automatically, see module docstring. Call before enable_*_sensor()/reads.
    @classmethod
    def begin(cls):
        chip_id = cls._read_reg(_REG_ID)
        if chip_id not in (_ID_1, _ID_2):
            raise OSError("APDS9960 not found (id 0x%02x)" % chip_id)

        cls.set_mode(MODE_ALL, 0)

        cls._write_reg(_REG_ATIME, _DEFAULT_ATIME)
        cls._write_reg(_REG_WTIME, _DEFAULT_WTIME)
        cls._write_reg(_REG_PPULSE, _DEFAULT_PROX_PPULSE)
        cls._write_reg(_REG_POFFSET_UR, 0)
        cls._write_reg(_REG_POFFSET_DL, 0)
        cls._write_reg(_REG_CONFIG1, _DEFAULT_CONFIG1)
        cls.set_led_drive(_DEFAULT_LDRIVE)
        cls.set_proximity_gain(_DEFAULT_PGAIN)
        cls.set_ambient_light_gain(_DEFAULT_AGAIN)
        cls._write_reg(_REG_PILT, _DEFAULT_PILT)
        cls._write_reg(_REG_PIHT, _DEFAULT_PIHT)
        cls.set_light_int_low_threshold(_DEFAULT_AILT)
        cls.set_light_int_high_threshold(_DEFAULT_AIHT)
        cls._write_reg(_REG_PERS, _DEFAULT_PERS)
        cls._write_reg(_REG_CONFIG2, _DEFAULT_CONFIG2)
        cls._write_reg(_REG_CONFIG3, _DEFAULT_CONFIG3)

        cls._write_reg(_REG_GPENTH, _DEFAULT_GPENTH)
        cls._write_reg(_REG_GEXTH, _DEFAULT_GEXTH)
        cls._write_reg(_REG_GCONF1, _DEFAULT_GCONF1)
        cls.set_gesture_gain(_DEFAULT_GGAIN)
        cls.set_gesture_led_drive(_DEFAULT_GLDRIVE)
        cls.set_gesture_wait_time(_DEFAULT_GWTIME)
        cls._write_reg(_REG_GOFFSET_U, 0)
        cls._write_reg(_REG_GOFFSET_D, 0)
        cls._write_reg(_REG_GOFFSET_L, 0)
        cls._write_reg(_REG_GOFFSET_R, 0)
        cls._write_reg(_REG_GPULSE, _DEFAULT_GPULSE)
        cls._write_reg(_REG_GCONF3, _DEFAULT_GCONF3)
        cls.set_gesture_int_enable(_DEFAULT_GIEN)
        return True

    # -- Power / mode --

    @classmethod
    def get_status_register(cls):
        return cls._read_reg(_REG_STATUS)

    @classmethod
    def get_mode(cls):
        return cls._read_reg(_REG_ENABLE)

    @classmethod
    def set_mode(cls, mode, enable):
        reg_val = cls.get_mode()
        enable = enable & 0x01
        if 0 <= mode <= 6:
            if enable:
                reg_val |= 1 << mode
            else:
                reg_val &= ~(1 << mode)
        elif mode == MODE_ALL:
            reg_val = 0x7F if enable else 0x00
        cls._write_reg(_REG_ENABLE, reg_val)

    @classmethod
    def enable_power(cls):
        cls.set_mode(MODE_POWER, 1)

    @classmethod
    def disable_power(cls):
        cls.set_mode(MODE_POWER, 0)

    # -- Sensor enable/disable --

    @classmethod
    def enable_light_sensor(cls, interrupts=False):
        cls.set_ambient_light_gain(_DEFAULT_AGAIN)
        cls.set_ambient_light_int_enable(1 if interrupts else 0)
        cls.enable_power()
        cls.set_mode(MODE_AMBIENT_LIGHT, 1)

    @classmethod
    def disable_light_sensor(cls):
        cls.set_ambient_light_int_enable(0)
        cls.set_mode(MODE_AMBIENT_LIGHT, 0)

    @classmethod
    def enable_proximity_sensor(cls, interrupts=False):
        cls.set_proximity_gain(_DEFAULT_PGAIN)
        cls.set_led_drive(_DEFAULT_LDRIVE)
        cls.set_proximity_int_enable(1 if interrupts else 0)
        cls.enable_power()
        cls.set_mode(MODE_PROXIMITY, 1)

    @classmethod
    def disable_proximity_sensor(cls):
        cls.set_proximity_int_enable(0)
        cls.set_mode(MODE_PROXIMITY, 0)

    @classmethod
    def enable_gesture_sensor(cls, interrupts=True):
        cls._reset_gesture_parameters()
        cls._write_reg(_REG_WTIME, 0xFF)
        cls._write_reg(_REG_PPULSE, _DEFAULT_GESTURE_PPULSE)
        cls.set_led_boost(LED_BOOST_300)
        cls.set_gesture_int_enable(1 if interrupts else 0)
        cls.set_gesture_mode(1)
        cls.enable_power()
        cls.set_mode(MODE_WAIT, 1)
        cls.set_mode(MODE_PROXIMITY, 1)
        cls.set_mode(MODE_GESTURE, 1)

    @classmethod
    def disable_gesture_sensor(cls):
        cls._reset_gesture_parameters()
        cls.set_gesture_int_enable(0)
        cls.set_gesture_mode(0)
        cls.set_mode(MODE_GESTURE, 0)

    # -- LED drive / gain --

    @classmethod
    def get_led_drive(cls):
        return cls._get_bits(_REG_CONTROL, 0xC0, 6)

    @classmethod
    def set_led_drive(cls, drive):
        cls._set_bits(_REG_CONTROL, 0xC0, 6, drive)

    @classmethod
    def get_gesture_led_drive(cls):
        return cls._get_bits(_REG_GCONF2, 0x18, 3)

    @classmethod
    def set_gesture_led_drive(cls, drive):
        cls._set_bits(_REG_GCONF2, 0x18, 3, drive)

    @classmethod
    def get_ambient_light_gain(cls):
        return cls._get_bits(_REG_CONTROL, 0x03, 0)

    @classmethod
    def set_ambient_light_gain(cls, gain):
        cls._set_bits(_REG_CONTROL, 0x03, 0, gain)

    @classmethod
    def get_proximity_gain(cls):
        return cls._get_bits(_REG_CONTROL, 0x0C, 2)

    @classmethod
    def set_proximity_gain(cls, gain):
        cls._set_bits(_REG_CONTROL, 0x0C, 2, gain)

    @classmethod
    def get_gesture_gain(cls):
        return cls._get_bits(_REG_GCONF2, 0x60, 5)

    @classmethod
    def set_gesture_gain(cls, gain):
        cls._set_bits(_REG_GCONF2, 0x60, 5, gain)

    @classmethod
    def get_led_boost(cls):
        return cls._get_bits(_REG_CONFIG2, 0x30, 4)

    @classmethod
    def set_led_boost(cls, boost):
        cls._set_bits(_REG_CONFIG2, 0x30, 4, boost)

    # -- Proximity photodiode config --

    @classmethod
    def get_prox_gain_comp_enable(cls):
        return cls._get_bits(_REG_CONFIG3, 0x20, 5)

    @classmethod
    def set_prox_gain_comp_enable(cls, enable):
        cls._set_bits(_REG_CONFIG3, 0x20, 5, enable)

    @classmethod
    def get_prox_photo_mask(cls):
        return cls._get_bits(_REG_CONFIG3, 0x0F, 0)

    @classmethod
    def set_prox_photo_mask(cls, mask):
        cls._set_bits(_REG_CONFIG3, 0x0F, 0, mask)

    # -- Interrupt thresholds --

    @classmethod
    def get_light_int_low_threshold(cls):
        return cls._read_word(_REG_AILTL, _REG_AILTH)

    @classmethod
    def set_light_int_low_threshold(cls, threshold):
        cls._write_word(_REG_AILTL, _REG_AILTH, threshold)

    @classmethod
    def get_light_int_high_threshold(cls):
        return cls._read_word(_REG_AIHTL, _REG_AIHTH)

    @classmethod
    def set_light_int_high_threshold(cls, threshold):
        cls._write_word(_REG_AIHTL, _REG_AIHTH, threshold)

    @classmethod
    def get_proximity_int_low_threshold(cls):
        return cls._read_reg(_REG_PILT)

    @classmethod
    def set_proximity_int_low_threshold(cls, threshold):
        cls._write_reg(_REG_PILT, threshold)

    @classmethod
    def get_proximity_int_high_threshold(cls):
        return cls._read_reg(_REG_PIHT)

    @classmethod
    def set_proximity_int_high_threshold(cls, threshold):
        cls._write_reg(_REG_PIHT, threshold)

    # -- Interrupt enables --

    @classmethod
    def get_ambient_light_int_enable(cls):
        return cls._get_bits(_REG_ENABLE, 0x10, 4)

    @classmethod
    def set_ambient_light_int_enable(cls, enable):
        cls._set_bits(_REG_ENABLE, 0x10, 4, enable)

    @classmethod
    def get_proximity_int_enable(cls):
        return cls._get_bits(_REG_ENABLE, 0x20, 5)

    @classmethod
    def set_proximity_int_enable(cls, enable):
        cls._set_bits(_REG_ENABLE, 0x20, 5, enable)

    @classmethod
    def get_gesture_int_enable(cls):
        return cls._get_bits(_REG_GCONF4, 0x02, 1)

    @classmethod
    def set_gesture_int_enable(cls, enable):
        cls._set_bits(_REG_GCONF4, 0x02, 1, enable)

    @classmethod
    def clear_ambient_light_int(cls):
        cls._read_reg(_REG_AICLEAR)

    @classmethod
    def clear_proximity_int(cls):
        cls._read_reg(_REG_PICLEAR)

    # -- Gesture threshold / mode --

    @classmethod
    def get_gesture_enter_thresh(cls):
        return cls._read_reg(_REG_GPENTH)

    @classmethod
    def set_gesture_enter_thresh(cls, threshold):
        cls._write_reg(_REG_GPENTH, threshold)

    @classmethod
    def get_gesture_exit_thresh(cls):
        return cls._read_reg(_REG_GEXTH)

    @classmethod
    def set_gesture_exit_thresh(cls, threshold):
        cls._write_reg(_REG_GEXTH, threshold)

    @classmethod
    def get_gesture_wait_time(cls):
        return cls._get_bits(_REG_GCONF2, 0x07, 0)

    @classmethod
    def set_gesture_wait_time(cls, wtime):
        cls._set_bits(_REG_GCONF2, 0x07, 0, wtime)

    @classmethod
    def get_gesture_mode(cls):
        return cls._get_bits(_REG_GCONF4, 0x01, 0)

    @classmethod
    def set_gesture_mode(cls, mode):
        cls._set_bits(_REG_GCONF4, 0x01, 0, mode)

    # -- Ambient light / color --

    @classmethod
    def read_ambient_light(cls):
        return cls._read_word(_REG_CDATAL, _REG_CDATAH)

    @classmethod
    def read_red_light(cls):
        return cls._read_word(_REG_RDATAL, _REG_RDATAH)

    @classmethod
    def read_green_light(cls):
        return cls._read_word(_REG_GDATAL, _REG_GDATAH)

    @classmethod
    def read_blue_light(cls):
        return cls._read_word(_REG_BDATAL, _REG_BDATAH)

    # -- Proximity --

    @classmethod
    def read_proximity(cls):
        return cls._read_reg(_REG_PDATA)

    # -- Gesture --

    @classmethod
    def is_gesture_available(cls):
        return (cls._read_reg(_REG_GSTATUS) & _GVALID) == _GVALID

    @classmethod
    def _reset_gesture_parameters(cls):
        cls._gesture_index = 0
        cls._gesture_total = 0
        cls._gesture_ud_delta = 0
        cls._gesture_lr_delta = 0
        cls._gesture_ud_count = 0
        cls._gesture_lr_count = 0
        cls._gesture_near_count = 0
        cls._gesture_far_count = 0
        cls._gesture_state = _NA_STATE
        cls._gesture_motion = DIR_NONE

    @classmethod
    def read_gesture(cls):
        u_data = bytearray(32)
        d_data = bytearray(32)
        l_data = bytearray(32)
        r_data = bytearray(32)
        cls._gesture_index = 0
        cls._gesture_total = 0

        if not cls.is_gesture_available() or not (cls.get_mode() & _PON_GEN_MSK):
            return DIR_NONE

        while True:
            time.sleep_ms(_FIFO_PAUSE_MS)
            gstatus = cls._read_reg(_REG_GSTATUS)

            if gstatus & _GVALID:
                fifo_level = cls._read_reg(_REG_GFLVL)
                if fifo_level > 0:
                    fifo_data = cls._i2c.readfrom_mem(cls._addr, _REG_GFIFO_U, fifo_level * 4)
                    bytes_read = len(fifo_data)
                    if bytes_read >= 4:
                        for i in range(0, bytes_read, 4):
                            u_data[cls._gesture_index] = fifo_data[i]
                            d_data[cls._gesture_index] = fifo_data[i + 1]
                            l_data[cls._gesture_index] = fifo_data[i + 2]
                            r_data[cls._gesture_index] = fifo_data[i + 3]
                            cls._gesture_index += 1
                            cls._gesture_total += 1

                        if cls._process_gesture_data(u_data, d_data, l_data, r_data):
                            cls._decode_gesture()

                        cls._gesture_index = 0
                        cls._gesture_total = 0
            else:
                time.sleep_ms(_FIFO_PAUSE_MS)
                cls._decode_gesture()
                motion = cls._gesture_motion
                cls._reset_gesture_parameters()
                return motion

    @classmethod
    def _process_gesture_data(cls, u_data, d_data, l_data, r_data):
        total = cls._gesture_total
        if total <= 4:
            return False

        u_first = d_first = l_first = r_first = 0
        u_last = d_last = l_last = r_last = 0

        if 0 < total <= 32:
            for i in range(total):
                if (
                    u_data[i] > _GESTURE_THRESHOLD_OUT
                    and d_data[i] > _GESTURE_THRESHOLD_OUT
                    and l_data[i] > _GESTURE_THRESHOLD_OUT
                    and r_data[i] > _GESTURE_THRESHOLD_OUT
                ):
                    u_first, d_first, l_first, r_first = u_data[i], d_data[i], l_data[i], r_data[i]
                    break

            if u_first == 0 or d_first == 0 or l_first == 0 or r_first == 0:
                return False

            for i in range(total - 1, -1, -1):
                if (
                    u_data[i] > _GESTURE_THRESHOLD_OUT
                    and d_data[i] > _GESTURE_THRESHOLD_OUT
                    and l_data[i] > _GESTURE_THRESHOLD_OUT
                    and r_data[i] > _GESTURE_THRESHOLD_OUT
                ):
                    u_last, d_last, l_last, r_last = u_data[i], d_data[i], l_data[i], r_data[i]
                    break

        ud_ratio_first = _c_idiv((u_first - d_first) * 100, u_first + d_first)
        lr_ratio_first = _c_idiv((l_first - r_first) * 100, l_first + r_first)
        ud_ratio_last = _c_idiv((u_last - d_last) * 100, u_last + d_last)
        lr_ratio_last = _c_idiv((l_last - r_last) * 100, l_last + r_last)

        ud_delta = ud_ratio_last - ud_ratio_first
        lr_delta = lr_ratio_last - lr_ratio_first

        cls._gesture_ud_delta += ud_delta
        cls._gesture_lr_delta += lr_delta

        if cls._gesture_ud_delta >= _GESTURE_SENSITIVITY_1:
            cls._gesture_ud_count = 1
        elif cls._gesture_ud_delta <= -_GESTURE_SENSITIVITY_1:
            cls._gesture_ud_count = -1
        else:
            cls._gesture_ud_count = 0

        if cls._gesture_lr_delta >= _GESTURE_SENSITIVITY_1:
            cls._gesture_lr_count = 1
        elif cls._gesture_lr_delta <= -_GESTURE_SENSITIVITY_1:
            cls._gesture_lr_count = -1
        else:
            cls._gesture_lr_count = 0

        if cls._gesture_ud_count == 0 and cls._gesture_lr_count == 0:
            if abs(ud_delta) < _GESTURE_SENSITIVITY_2 and abs(lr_delta) < _GESTURE_SENSITIVITY_2:
                if ud_delta == 0 and lr_delta == 0:
                    cls._gesture_near_count += 1
                elif ud_delta != 0 or lr_delta != 0:
                    cls._gesture_far_count += 1

                if cls._gesture_near_count >= 10 and cls._gesture_far_count >= 2:
                    if ud_delta == 0 and lr_delta == 0:
                        cls._gesture_state = _NEAR_STATE
                    elif ud_delta != 0 and lr_delta != 0:
                        cls._gesture_state = _FAR_STATE
                    return True
        else:
            if abs(ud_delta) < _GESTURE_SENSITIVITY_2 and abs(lr_delta) < _GESTURE_SENSITIVITY_2:
                if ud_delta == 0 and lr_delta == 0:
                    cls._gesture_near_count += 1

                if cls._gesture_near_count >= 10:
                    cls._gesture_ud_count = 0
                    cls._gesture_lr_count = 0
                    cls._gesture_ud_delta = 0
                    cls._gesture_lr_delta = 0

        return False

    @classmethod
    def _decode_gesture(cls):
        if cls._gesture_state == _NEAR_STATE:
            cls._gesture_motion = DIR_NEAR
            return True
        if cls._gesture_state == _FAR_STATE:
            cls._gesture_motion = DIR_FAR
            return True

        ud, lr = cls._gesture_ud_count, cls._gesture_lr_count
        bigger_ud = abs(cls._gesture_ud_delta) > abs(cls._gesture_lr_delta)

        if ud == -1 and lr == 0:
            cls._gesture_motion = DIR_UP
        elif ud == 1 and lr == 0:
            cls._gesture_motion = DIR_DOWN
        elif ud == 0 and lr == 1:
            cls._gesture_motion = DIR_RIGHT
        elif ud == 0 and lr == -1:
            cls._gesture_motion = DIR_LEFT
        elif ud == -1 and lr == 1:
            cls._gesture_motion = DIR_UP if bigger_ud else DIR_RIGHT
        elif ud == 1 and lr == -1:
            cls._gesture_motion = DIR_DOWN if bigger_ud else DIR_LEFT
        elif ud == -1 and lr == -1:
            cls._gesture_motion = DIR_UP if bigger_ud else DIR_LEFT
        elif ud == 1 and lr == 1:
            cls._gesture_motion = DIR_DOWN if bigger_ud else DIR_RIGHT
        else:
            return False
        return True
