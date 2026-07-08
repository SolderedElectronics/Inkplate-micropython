"""Driver for the Cypress capacitive touchscreen controller on the Inkplate 6FLICK."""
import time
from machine import Pin
from pcal6416a import *

# Constants
CPYRESS_TOUCH_I2C_ADDR = 0x24

# Cypress touchscreen controller I2C regs.
CYPRESS_TOUCH_BASE_ADDR = 0x00
CYPRESS_TOUCH_SOFT_RST_MODE = 0x01
CYPRESS_TOUCH_SYSINFO_MODE = 0x10
CYPRESS_TOUCH_OPERATE_MODE = 0x00
CYPRESS_TOUCH_LOW_POWER_MODE = 0x04
CYPRESS_TOUCH_DEEP_SLEEP_MODE = 0x02

# Default values
CYPRESS_TOUCH_ACT_INTRVL_DFLT = 0x00  # ms
CYPRESS_TOUCH_LP_INTRVL_DFLT = 0x0A  # ms
CYPRESS_TOUCH_TCH_TMOUT_DFLT = 0xFF  # ms

# Max X and Y sizes reported by the TSC.
CYPRESS_TOUCH_MAX_X = 682
CYPRESS_TOUCH_MAX_Y = 1023

TOUCHSCREEN_EN = 12
FRONTLIGHT_ADDRESS = 0x2E
TS_RST = 10
TS_INT = 36
TS_ADDR = 0x24

# Screen dimensions
E_INK_WIDTH = 1024
E_INK_HEIGHT = 758
D_ROWS = 1024
D_COLS = 758


# Data structures
class CyttspBootloaderData:
    def __init__(self):
        self.bl_file_offset = 0
        self.bl_status = 0
        self.bl_error = 0
        self.bl_cmd = 0
        self.bl_key0 = 0
        self.bl_key1 = 0
        self.bl_key2 = 0
        self.bl_key3 = 0
        self.bl_key4 = 0
        self.bl_key5 = 0
        self.bl_key6 = 0
        self.bl_key7 = 0


class CyttspSysinfoData:
    def __init__(self):
        self.hst_mode = 0
        self.reserved1 = 0
        self.tts_verh = 0
        self.tts_verl = 0
        self.reserved2 = 0
        self.reserved3 = 0
        self.reserved4 = 0
        self.reserved5 = 0
        self.reserved6 = 0
        self.reserved7 = 0
        self.reserved8 = 0
        self.reserved9 = 0
        self.reserved10 = 0
        self.reserved11 = 0
        self.reserved12 = 0
        self.reserved13 = 0
        self.reserved14 = 0
        self.reserved15 = 0
        self.reserved16 = 0
        self.reserved17 = 0
        self.reserved18 = 0
        self.reserved19 = 0
        self.reserved20 = 0
        self.reserved21 = 0
        self.reserved22 = 0
        self.reserved23 = 0
        self.reserved24 = 0
        self.reserved25 = 0
        self.reserved26 = 0
        self.reserved27 = 0
        self.reserved28 = 0
        self.reserved29 = 0
        self.reserved30 = 0
        self.reserved31 = 0
        self.act_intrvl = 0
        self.tch_tmout = 0
        self.lp_intrvl = 0


class CypressTouchData:
    def __init__(self):
        self.x = [0, 0]
        self.y = [0, 0]
        self.z = [0, 0]
        self.detectionType = 0
        self.fingers = 0


class Touch:
    # Class variables
    _ts_flag = False
    _ts_init_done = False
    _bl_data = CyttspBootloaderData()
    _sys_data = CyttspSysinfoData()
    touch_t = 0
    touch_n = 0
    touch_x = [0, 0]
    touch_y = [0, 0]

    # Variables for compatibility
    _x_pos = [0, 0]
    _y_pos = [0, 0]
    xraw = [0, 0]
    yraw = [0, 0]
    _ts_x_resolution = 0
    _ts_y_resolution = 0
    rotation = 0

    # I2C and GPIO
    _i2c = None
    _PCAL6416A_1 = None

    @classmethod
    def init(cls, i2c, pcal_instance):
        cls._i2c = i2c
        cls._PCAL6416A_1 = pcal_instance

    @classmethod
    def ts_int(cls, pin):
        # Only set flag if it's not already set (prevent multiple interrupts for same touch)
        if not cls._ts_flag:
            cls._ts_flag = True

    @classmethod
    def ts_init(cls, power_state):
        # Set GPIO pins using PCAL6416A
        GpioPin(cls._PCAL6416A_1, TOUCHSCREEN_EN, mode=1)  # mode_output = 1
        cls._PCAL6416A_1.digital_write(TOUCHSCREEN_EN, 1)

        # Set up interrupt pin
        GpioPin(cls._PCAL6416A_1, TS_RST, mode=0)  # mode_output = 1

        ts_intr = Pin(TS_INT, mode=Pin.IN, pull=Pin.PULL_UP)

        cls._PCAL6416A_1.digital_write(TS_RST, 0)
        ts_intr.irq(trigger=Pin.IRQ_FALLING, handler=cls.ts_int)

        # Do hardware reset
        cls.ts_reset()

        # Try to ping it
        if not cls.ts_ping(5):
            print("Ping")
            return False

        # Issue a SW reset
        cls.ts_send_command(0x01)

        # Read bootloader data
        if not cls.ts_load_bootloader_regs(cls._bl_data):
            print("Bootloader")
            return False

        # Exit bootloader mode
        if not cls.ts_exit_boot_loader_mode():
            print("Exit Bootloader")
            return False

        # Set mode to system info mode
        if not cls.ts_set_sys_info_mode(cls._sys_data):
            print("Sysinfo")
            return False

        # Set system info regs
        if not cls.ts_set_sys_info_regs(cls._sys_data):
            print("InfoReg")
            return False

        # Switch to operate mode
        cls.ts_send_command(CYPRESS_TOUCH_OPERATE_MODE)

        # Set dist value for detection
        dist_default_value = 0xF8
        cls.ts_write_i2c_regs(0x1E, bytearray([dist_default_value]), 1)

        # Wait a bit
        time.sleep_ms(50)

        # Clear interrupt flag
        cls._ts_flag = False

        return True

    @classmethod
    def ts_shutdown(cls):
        # Disable power to touchscreen
        cls.ts_power(False)

    @classmethod
    def ts_get_raw_data(cls):
        data = bytearray(16)
        cls.ts_read_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, data, 16)
        return data

    @classmethod
    def ts_get_xy(cls, data, i):
        # This is a placeholder - you'll need to implement the actual XY extraction
        # based on your specific touch controller protocol
        offset = i * 3
        cls.xraw[i] = (data[1 + offset] & 0xF0) << 4 | data[2 + offset]
        cls.yraw[i] = (data[1 + offset] & 0x0F) << 8 | data[3 + offset]

    @classmethod
    def ts_get_data(cls, x_pos=None, y_pos=None, z=None):
        if x_pos is None or y_pos is None:
            return 0

        # No new data?
        if not cls._ts_flag:
            return 0

        cls._ts_flag = False

        touch_report = CypressTouchData()
        if not cls.ts_get_touch_data(touch_report):
            return 0

        if touch_report.fingers == 0:
            return 0

        # Scale valid data
        cls.ts_scale(touch_report, E_INK_WIDTH - 1, E_INK_HEIGHT - 1, False, True, True)

        for i in range(max(touch_report.fingers, 2)):
            x_pos[i] = touch_report.x[i]
            y_pos[i] = touch_report.y[i]
            if z is not None:
                z[i] = touch_report.z[i]

        return touch_report.fingers

    @classmethod
    def ts_get_resolution(cls):
        # This is a placeholder - implement based on your specific hardware
        cls._ts_x_resolution = 4096
        cls._ts_y_resolution = 4096

    @classmethod
    def ts_set_power_state(cls, state):
        if state in [
            CYPRESS_TOUCH_DEEP_SLEEP_MODE,
            CYPRESS_TOUCH_LOW_POWER_MODE,
            CYPRESS_TOUCH_OPERATE_MODE,
        ]:
            cls.ts_send_command(state)

    @classmethod
    def ts_get_power_state(cls):
        # Send subaddress for System Info
        cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, bytes([CYPRESS_TOUCH_BASE_ADDR]))

        # First byte represents current power mode
        data = cls._i2c.readfrom(CPYRESS_TOUCH_I2C_ADDR, 1)
        return data[0]

    @classmethod
    def ts_available(cls):
        return cls._ts_flag

    @classmethod
    def ts_power(cls, pwr):
        if pwr:
            cls._PCAL6416A_1.digital_write(TOUCHSCREEN_EN, 1)
            time.sleep_ms(50)
            cls._PCAL6416A_1.digital_write(TS_RST, 1)
            time.sleep_ms(50)
        else:
            cls._PCAL6416A_1.digital_write(TOUCHSCREEN_EN, 0)
            time.sleep_ms(50)
            cls._PCAL6416A_1.digital_write(TS_RST, 0)

    @classmethod
    def ts_reset(cls):
        cls._PCAL6416A_1.digital_write(TS_RST, 1)
        time.sleep_ms(10)
        cls._PCAL6416A_1.digital_write(TS_RST, 0)
        time.sleep_ms(2)
        cls._PCAL6416A_1.digital_write(TS_RST, 1)
        time.sleep_ms(10)

    @classmethod
    def ts_sw_reset(cls):
        cls.ts_send_command(CYPRESS_TOUCH_SOFT_RST_MODE)
        time.sleep_ms(20)

    @classmethod
    def ts_load_bootloader_regs(cls, bl_data):
        bootloader_data = bytearray(16)
        if not cls.ts_read_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, bootloader_data, 16):
            return False

        # Parse data into struct
        bl_data.bl_file_offset = bootloader_data[0]
        bl_data.bl_status = bootloader_data[1]
        bl_data.bl_error = bootloader_data[2]
        bl_data.bl_cmd = bootloader_data[3]
        bl_data.bl_key0 = bootloader_data[4]
        bl_data.bl_key1 = bootloader_data[5]
        bl_data.bl_key2 = bootloader_data[6]
        bl_data.bl_key3 = bootloader_data[7]
        bl_data.bl_key4 = bootloader_data[8]
        bl_data.bl_key5 = bootloader_data[9]
        bl_data.bl_key6 = bootloader_data[10]
        bl_data.bl_key7 = bootloader_data[11]

        return True

    @classmethod
    def ts_exit_boot_loader_mode(cls):
        # Bootloader command array
        bl_command_array = bytes(
            [
                0x00,  # File offset
                0xFF,  # Command
                0xA5,  # Exit bootloader command
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,  # Default keys
            ]
        )

        # Write bootloader settings
        cls.ts_write_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, bl_command_array, len(bl_command_array))

        # Wait
        time.sleep_ms(500)

        # Get bootloader data
        bootloader_data = CyttspBootloaderData()
        cls.ts_load_bootloader_regs(bootloader_data)

        # Check if still in bootloader mode
        if (bootloader_data.bl_status & 0x10) >> 4:
            return False

        return True

    @classmethod
    def ts_set_sys_info_mode(cls, sys_data):
        # Change mode to system info
        if not cls.ts_send_command(CYPRESS_TOUCH_SYSINFO_MODE):
            return False

        time.sleep_ms(20)

        # Read system info data - need to read from the correct register
        # System info data starts at register 0x10, not 0x00
        sys_info_array = bytearray(32)
        if not cls.ts_read_i2c_regs(0x10, sys_info_array, 32):
            return False

        sys_data.hst_mode = sys_info_array[0]
        sys_data.tts_verh = sys_info_array[2]
        sys_data.tts_verl = sys_info_array[3]
        sys_data.act_intrvl = sys_info_array[28]  # Corrected index
        sys_data.tch_tmout = sys_info_array[29]  # Corrected index
        sys_data.lp_intrvl = sys_info_array[30]  # Corrected index

        # Do handshake
        cls.ts_handshake()

        if sys_data.tts_verh == 0 and sys_data.tts_verl == 0:
            print("Error: Invalid TTS version")
            return False

        return True

    @classmethod
    def ts_set_sys_info_regs(cls, sys_data):
        # Modify registers to default values
        sys_data.act_intrvl = CYPRESS_TOUCH_ACT_INTRVL_DFLT
        sys_data.tch_tmout = CYPRESS_TOUCH_TCH_TMOUT_DFLT
        sys_data.lp_intrvl = CYPRESS_TOUCH_LP_INTRVL_DFLT

        # Pack into array
        regs = bytes([sys_data.act_intrvl, sys_data.tch_tmout, sys_data.lp_intrvl])

        # Send registers
        if not cls.ts_write_i2c_regs(0x1D, regs, 3):
            return False

        time.sleep_ms(20)
        return True

    @classmethod
    def ts_handshake(cls):
        # Read hst_mode register
        hst_mode_reg = bytearray(1)
        cls.ts_read_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, hst_mode_reg, 1)

        # XOR with 0x80 and write back
        hst_mode_reg[0] ^= 0x80
        cls.ts_write_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, hst_mode_reg, 1)

    @classmethod
    def ts_ping(cls, retries):
        for i in range(retries):
            try:
                cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, b"")
                return True
            except OSError:
                time.sleep_ms(20)
        return False

    @classmethod
    def ts_send_command(cls, cmd):
        try:
            cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, bytes([CYPRESS_TOUCH_BASE_ADDR, cmd]))
            time.sleep_ms(20)
            return True
        except OSError:
            return False

    @classmethod
    def ts_read_i2c_regs(cls, cmd, buffer, length):
        try:
            # Send command byte
            cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, bytes([cmd]))

            # Read data
            index = 0
            while length > 0:
                # Read up to 32 bytes at a time
                i2c_len = min(length, 32)
                data = cls._i2c.readfrom(CPYRESS_TOUCH_I2C_ADDR, i2c_len)

                # Copy to buffer
                for i in range(i2c_len):
                    if index + i < len(buffer):
                        buffer[index + i] = data[i]

                index += i2c_len
                length -= i2c_len

            return True
        except OSError:
            return False

    @classmethod
    def ts_write_i2c_regs(cls, cmd, buffer, length):
        try:
            # Send command byte followed by data
            data = bytes([cmd]) + buffer[:length]
            cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, data)
            return True
        except OSError:
            return False

    @classmethod
    def ts_get_touch_data(cls, touch_data):
        if touch_data is None:
            return False

        regs = bytearray(32)
        if not cls.ts_read_i2c_regs(CYPRESS_TOUCH_BASE_ADDR, regs, 32):
            return False

        cls.ts_handshake()

        fingers = regs[2]
        if fingers == 0:
            touch_data.fingers = 0
            return True  # tell caller "valid read, but nothing pressed"

        # Normal parse
        touch_data.fingers = fingers
        touch_data.x[0] = (regs[3] << 8) | regs[4]
        touch_data.y[0] = (regs[5] << 8) | regs[6]
        touch_data.z[0] = regs[7]
        touch_data.x[1] = (regs[9] << 8) | regs[10]
        touch_data.y[1] = (regs[11] << 8) | regs[12]
        touch_data.z[1] = regs[13]
        touch_data.detectionType = regs[8]

        return True

    @classmethod
    def ts_scale(cls, touch_data, x_size, y_size, flip_x, flip_y, swap_xy):
        # Check for NULL pointer
        if touch_data is None:
            return

        # If the number of detected fingers is different than one or two, return
        if touch_data.fingers != 1 and touch_data.fingers != 2:
            return

        # Map both touch channels
        for i in range(touch_data.fingers):
            # Check for the flip
            if flip_x:
                touch_data.x[i] = CYPRESS_TOUCH_MAX_X - touch_data.x[i]
            if flip_y:
                touch_data.y[i] = CYPRESS_TOUCH_MAX_Y - touch_data.y[i]

            # Check for X and Y swap
            if swap_xy:
                temp = touch_data.x[i]
                touch_data.x[i] = touch_data.y[i]
                touch_data.y[i] = temp

            # Map X value to screen size
            touch_data.x[i] = int((touch_data.x[i] * x_size) / CYPRESS_TOUCH_MAX_X)

            # Map Y value to screen size
            touch_data.y[i] = int((touch_data.y[i] * y_size) / CYPRESS_TOUCH_MAX_Y)

    @classmethod
    def touch_in_area(cls, x1, y1, w, h):
        x2 = x1 + w
        y2 = y1 + h

        # Check if there's a new touch event
        if cls.ts_available():
            x = [0, 0]
            y = [0, 0]
            n = cls.ts_get_data(x, y)

            # Scale coordinates from touch controller resolution (1535x560) to
            # display resolution (1024x758)
            display_width = 1024
            display_height = 758
            touch_width = 1535
            touch_height = 560

            for i in range(n):
                # Scale X coordinate
                x[i] = int((x[i] * display_width) / touch_width)
                # Scale Y coordinate
                y[i] = int((y[i] * display_height) / touch_height)

            # Workaround for multiple INT events
            _ts_int_timeout = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), _ts_int_timeout) < 100:
                if cls._ts_flag:
                    _ts_int_timeout = time.ticks_ms()
                    cls._ts_flag = False
                    cls.ts_handshake()

            if n > 0:
                cls.touch_t = time.ticks_ms()
                cls.touch_n = n
                cls.touch_x = x.copy()
                cls.touch_y = y.copy()
            else:
                cls.touch_n = 0  # mark as released, but don’t overwrite coords
                return

            # Check if this touch is in the specified area
            def bound(low, value, high):
                return low <= value <= high

            if n == 1 and bound(x1, x[0], x2) and bound(y1, y[0], y2):
                return True
            if n == 2 and (
                (bound(x1, x[0], x2) and bound(y1, y[0], y2))
                or (bound(x1, x[1], x2) and bound(y1, y[1], y2))
            ):
                return True
            return False

        # If no new touch, check if we have a recent touch that's still valid
        elif time.ticks_diff(time.ticks_ms(), cls.touch_t) < 150:

            def bound(low, value, high):
                return low <= value <= high

            if cls.touch_n == 1 and bound(x1, cls.touch_x[0], x2) and bound(y1, cls.touch_y[0], y2):
                return True
            if cls.touch_n == 2 and (
                (bound(x1, cls.touch_x[0], x2) and bound(y1, cls.touch_y[0], y2))
                or (bound(x1, cls.touch_x[1], x2) and bound(y1, cls.touch_y[1], y2))
            ):
                return True

        return False
