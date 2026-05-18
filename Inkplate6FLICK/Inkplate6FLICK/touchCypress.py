import time
from machine import Pin, I2C
from PCAL6416A import *
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
CYPRESS_TOUCH_LP_INTRVL_DFLT = 0x0A   # ms
CYPRESS_TOUCH_TCH_TMOUT_DFLT = 0xFF   # ms

# Max X and Y sizes reported by the TSC.
CYPRESS_TOUCH_MAX_X = 682
CYPRESS_TOUCH_MAX_Y = 1023

TOUCHSCREEN_EN = 12
FRONTLIGHT_ADDRESS  = 0x2E
TS_RST = 10
TS_INT = 36
TS_ADDR = 0x24

# Screen dimensions
E_INK_WIDTH = 1024
E_INK_HEIGHT = 758
D_ROWS = 1024
D_COLS = 758

# Data structures
class cyttspBootloaderData:
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

class cyttspSysinfoData:
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

class cypressTouchData:
    def __init__(self):
        self.x = [0, 0]
        self.y = [0, 0]
        self.z = [0, 0]
        self.detectionType = 0
        self.fingers = 0

class Touch:
    # Class variables
    _tsFlag = False
    _tsInitDone = False
    _blData = cyttspBootloaderData()
    _sysData = cyttspSysinfoData()
    touchT = 0
    touchN = 0
    touchX = [0, 0]
    touchY = [0, 0]
    
    # Variables for compatibility
    _xPos = [0, 0]
    _yPos = [0, 0]
    xraw = [0, 0]
    yraw = [0, 0]
    _tsXResolution = 0
    _tsYResolution = 0
    rotation = 0
    
    # I2C and GPIO
    _i2c = None
    _PCAL6416A_1 = None
    
    @classmethod
    def init(cls, i2c, pcal_instance):
        cls._i2c = i2c
        cls._PCAL6416A_1 = pcal_instance
        
    @classmethod
    def tsInt(cls, pin):
        # Only set flag if it's not already set (prevent multiple interrupts for same touch)
        if not cls._tsFlag:
            cls._tsFlag = True

    @classmethod
    def tsInit(cls, powerState):
        # Set GPIO pins using PCAL6416A
        gpioPin(cls._PCAL6416A_1,TOUCHSCREEN_EN, mode=1)  # modeOUTPUT = 1
        cls._PCAL6416A_1.digitalWrite(TOUCHSCREEN_EN, 1)
        
        # Set up interrupt pin
        gpioPin(cls._PCAL6416A_1,TS_RST, mode=0)  # modeOUTPUT = 1
        
        ts_intr = Pin(TS_INT, mode=Pin.IN, pull=Pin.PULL_UP)
        
        cls._PCAL6416A_1.digitalWrite(TS_RST, 0)
        ts_intr.irq(trigger=Pin.IRQ_FALLING, handler=cls.tsInt)

        # Do hardware reset
        cls.tsReset()
        
        # Try to ping it
        if not cls.tsPing(5):
            print("Ping")
            return False
        
        # Issue a SW reset
        cls.tsSendCommand(0x01)
        
        # Read bootloader data
        if not cls.tsLoadBootloaderRegs(cls._blData):
            print("Bootloader")
            return False
        
        # Exit bootloader mode
        if not cls.tsExitBootLoaderMode():
            print("Exit Bootloader")
            return False
        
        # Set mode to system info mode
        if not cls.tsSetSysInfoMode(cls._sysData):
            print("Sysinfo")
            return False
        
        # Set system info regs
        if not cls.tsSetSysInfoRegs(cls._sysData):
            print("InfoReg")
            return False
        
        # Switch to operate mode
        cls.tsSendCommand(CYPRESS_TOUCH_OPERATE_MODE)
        
        # Set dist value for detection
        dist_default_value = 0xF8
        cls.tsWriteI2CRegs(0x1E, bytearray([dist_default_value]), 1)
        
        # Wait a bit
        time.sleep_ms(50)
        
        # Clear interrupt flag
        cls._tsFlag = False
        
        return True

    @classmethod
    def tsShutdown(cls):
        # Disable power to touchscreen
        cls.tsPower(False)

    @classmethod
    def tsGetRawData(cls):
        data = bytearray(16)
        cls.tsReadI2CRegs(CYPRESS_TOUCH_BASE_ADDR, data, 16)
        return data

    @classmethod
    def tsGetXY(cls, data, i):
        # This is a placeholder - you'll need to implement the actual XY extraction
        # based on your specific touch controller protocol
        offset = i * 3
        cls.xraw[i] = (data[1 + offset] & 0xF0) << 4 | data[2 + offset]
        cls.yraw[i] = (data[1 + offset] & 0x0F) << 8 | data[3 + offset]

    @classmethod
    def tsGetData(cls, xPos=None, yPos=None, z=None):
        if xPos is None or yPos is None:
            return 0

        # No new data?
        if not cls._tsFlag:
            return 0

        cls._tsFlag = False

        touch_report = cypressTouchData()
        if not cls.tsGetTouchData(touch_report):
            return 0

        if touch_report.fingers == 0:
            return 0

        # Scale valid data
        cls.tsScale(touch_report, E_INK_WIDTH - 1, E_INK_HEIGHT - 1, False, True, True)

        for i in range(max(touch_report.fingers,2)):
            xPos[i] = touch_report.x[i]
            yPos[i] = touch_report.y[i]
            if z is not None:
                z[i] = touch_report.z[i]

        return touch_report.fingers



    @classmethod
    def tsGetResolution(cls):
        # This is a placeholder - implement based on your specific hardware
        cls._tsXResolution = 4096
        cls._tsYResolution = 4096

    @classmethod
    def tsSetPowerState(cls, state):
        if state in [CYPRESS_TOUCH_DEEP_SLEEP_MODE, CYPRESS_TOUCH_LOW_POWER_MODE, CYPRESS_TOUCH_OPERATE_MODE]:
            cls.tsSendCommand(state)

    @classmethod
    def tsGetPowerState(cls):
        # Send subaddress for System Info
        cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, bytes([CYPRESS_TOUCH_BASE_ADDR]))
        
        # First byte represents current power mode
        data = cls._i2c.readfrom(CPYRESS_TOUCH_I2C_ADDR, 1)
        return data[0]

    @classmethod
    def tsAvailable(cls):
        return cls._tsFlag

    @classmethod
    def tsPower(cls, pwr):
        if pwr:
            cls._PCAL6416A_1.digitalWrite(TOUCHSCREEN_EN, 1)
            time.sleep_ms(50)
            cls._PCAL6416A_1.digitalWrite(TS_RST, 1)
            time.sleep_ms(50)
        else:
            cls._PCAL6416A_1.digitalWrite(TOUCHSCREEN_EN, 0)
            time.sleep_ms(50)
            cls._PCAL6416A_1.digitalWrite(TS_RST, 0)

    @classmethod
    def tsReset(cls):
        cls._PCAL6416A_1.digitalWrite(TS_RST, 1)
        time.sleep_ms(10)
        cls._PCAL6416A_1.digitalWrite(TS_RST, 0)
        time.sleep_ms(2)
        cls._PCAL6416A_1.digitalWrite(TS_RST, 1)
        time.sleep_ms(10)

    @classmethod
    def tsSwReset(cls):
        cls.tsSendCommand(CYPRESS_TOUCH_SOFT_RST_MODE)
        time.sleep_ms(20)

    @classmethod
    def tsLoadBootloaderRegs(cls, bl_data):
        bootloader_data = bytearray(16)
        if not cls.tsReadI2CRegs(CYPRESS_TOUCH_BASE_ADDR, bootloader_data, 16):
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
    def tsExitBootLoaderMode(cls):
        # Bootloader command array
        bl_command_array = bytes([
            0x00,  # File offset
            0xFF,  # Command
            0xA5,  # Exit bootloader command
            0, 1, 2, 3, 4, 5, 6, 7  # Default keys
        ])
        
        # Write bootloader settings
        cls.tsWriteI2CRegs(CYPRESS_TOUCH_BASE_ADDR, bl_command_array, len(bl_command_array))
        
        # Wait
        time.sleep_ms(500)
        
        # Get bootloader data
        bootloader_data = cyttspBootloaderData()
        cls.tsLoadBootloaderRegs(bootloader_data)
        
        # Check if still in bootloader mode
        if (bootloader_data.bl_status & 0x10) >> 4:
            return False
        
        return True

    @classmethod
    def tsSetSysInfoMode(cls, sys_data):
        # Change mode to system info
        if not cls.tsSendCommand(CYPRESS_TOUCH_SYSINFO_MODE):
            return False
        
        time.sleep_ms(20)
        
        # Read system info data - need to read from the correct register
        # System info data starts at register 0x10, not 0x00
        sys_info_array = bytearray(32)
        if not cls.tsReadI2CRegs(0x10, sys_info_array, 32):
            return False
        
        sys_data.hst_mode = sys_info_array[0]
        sys_data.tts_verh = sys_info_array[2]
        sys_data.tts_verl = sys_info_array[3]
        sys_data.act_intrvl = sys_info_array[28]  # Corrected index
        sys_data.tch_tmout = sys_info_array[29]   # Corrected index
        sys_data.lp_intrvl = sys_info_array[30]   # Corrected index
        
        # Do handshake
        cls.tsHandshake()

        if sys_data.tts_verh == 0 and sys_data.tts_verl == 0:
            print("Error: Invalid TTS version")
            return False
        
        return True

    @classmethod
    def tsSetSysInfoRegs(cls, sys_data):
        # Modify registers to default values
        sys_data.act_intrvl = CYPRESS_TOUCH_ACT_INTRVL_DFLT
        sys_data.tch_tmout = CYPRESS_TOUCH_TCH_TMOUT_DFLT
        sys_data.lp_intrvl = CYPRESS_TOUCH_LP_INTRVL_DFLT
        
        # Pack into array
        regs = bytes([sys_data.act_intrvl, sys_data.tch_tmout, sys_data.lp_intrvl])
        
        # Send registers
        if not cls.tsWriteI2CRegs(0x1D, regs, 3):
            return False
        
        time.sleep_ms(20)
        return True

    @classmethod
    def tsHandshake(cls):
        # Read hst_mode register
        hst_mode_reg = bytearray(1)
        cls.tsReadI2CRegs(CYPRESS_TOUCH_BASE_ADDR, hst_mode_reg, 1)
        
        # XOR with 0x80 and write back
        hst_mode_reg[0] ^= 0x80
        cls.tsWriteI2CRegs(CYPRESS_TOUCH_BASE_ADDR, hst_mode_reg, 1)

    @classmethod
    def tsPing(cls, retries):
        for i in range(retries):
            try:
                cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, b'')
                return True
            except OSError:
                time.sleep_ms(20)
        return False

    @classmethod
    def tsSendCommand(cls, cmd):
        try:
            cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, bytes([CYPRESS_TOUCH_BASE_ADDR, cmd]))
            time.sleep_ms(20)
            return True
        except OSError:
            return False

    @classmethod
    def tsReadI2CRegs(cls, cmd, buffer, length):
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
    def tsWriteI2CRegs(cls, cmd, buffer, length):
        try:
            # Send command byte followed by data
            data = bytes([cmd]) + buffer[:length]
            cls._i2c.writeto(CPYRESS_TOUCH_I2C_ADDR, data)
            return True
        except OSError:
            return False

    @classmethod
    def tsGetTouchData(cls, touch_data):
        if touch_data is None:
            return False

        regs = bytearray(32)
        if not cls.tsReadI2CRegs(CYPRESS_TOUCH_BASE_ADDR, regs, 32):
            return False

        cls.tsHandshake()

        fingers = regs[2]
        if fingers == 0:
            touch_data.fingers = 0
            return True   # tell caller "valid read, but nothing pressed"

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
    def tsScale(cls, touch_data, xSize, ySize, flipX, flipY, swapXY):
        # Check for NULL pointer
        if touch_data is None:
            return

        # If the number of detected fingers is different than one or two, return
        if touch_data.fingers != 1 and touch_data.fingers != 2:
            return

        # Map both touch channels
        for i in range(touch_data.fingers):
            # Check for the flip
            if flipX:
                touch_data.x[i] = CYPRESS_TOUCH_MAX_X - touch_data.x[i]
            if flipY:
                touch_data.y[i] = CYPRESS_TOUCH_MAX_Y - touch_data.y[i]

            # Check for X and Y swap
            if swapXY:
                temp = touch_data.x[i]
                touch_data.x[i] = touch_data.y[i]
                touch_data.y[i] = temp

            # Map X value to screen size
            touch_data.x[i] = int((touch_data.x[i] * xSize) / CYPRESS_TOUCH_MAX_X)

            # Map Y value to screen size
            touch_data.y[i] = int((touch_data.y[i] * ySize) / CYPRESS_TOUCH_MAX_Y)

    @classmethod
    def touchInArea(cls, x1, y1, w, h):
        x2 = x1 + w
        y2 = y1 + h
        
        # Check if there's a new touch event
        if cls.tsAvailable():
            x = [0, 0]
            y = [0, 0]
            n = cls.tsGetData(x, y)
            
            # Scale coordinates from touch controller resolution (1535x560) to display resolution (1024x758)
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
            _tsIntTimeout = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), _tsIntTimeout) < 100:
                if cls._tsFlag:
                    _tsIntTimeout = time.ticks_ms()
                    cls._tsFlag = False
                    cls.tsHandshake()
            
            
            if n > 0:
                cls.touchT = time.ticks_ms()
                cls.touchN = n
                cls.touchX = x.copy()
                cls.touchY = y.copy()
            else:
                cls.touchN = 0   # mark as released, but don’t overwrite coords
                return

            
            # Check if this touch is in the specified area
            def BOUND(low, value, high):
                return low <= value <= high
            
            if n == 1 and BOUND(x1, x[0], x2) and BOUND(y1, y[0], y2):
                return True
            if n == 2 and ((BOUND(x1, x[0], x2) and BOUND(y1, y[0], y2)) or
                           (BOUND(x1, x[1], x2) and BOUND(y1, y[1], y2))):
                return True
            return False
        
        # If no new touch, check if we have a recent touch that's still valid
        elif time.ticks_diff(time.ticks_ms(), cls.touchT) < 150:
            def BOUND(low, value, high):
                return low <= value <= high
            
            if cls.touchN == 1 and BOUND(x1, cls.touchX[0], x2) and BOUND(y1, cls.touchY[0], y2):
                return True
            if cls.touchN == 2 and ((BOUND(x1, cls.touchX[0], x2) and BOUND(y1, cls.touchY[0], y2)) or
                                   (BOUND(x1, cls.touchX[1], x2) and BOUND(y1, cls.touchY[1], y2))):
                return True
        
        return False

