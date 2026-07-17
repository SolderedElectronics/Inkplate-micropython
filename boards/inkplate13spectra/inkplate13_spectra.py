"""MicroPython driver for the Inkplate 13 SPECTRA e-paper display.

Ported from the Arduino Inkplate13Driver implementation.
"""

import time
import os
from machine import ADC, I2C, SDCard, Pin
from micropython import const
from pcal6416a import *
from rtc import RTC
import gfx_standard_font_01 as montserrat_black
import machine
import inkplate

machine.freq(240000000)

# RST/DC/CS_M/CS_S/BUSY/CLK/DIN, PWR_EN, BS0/BS1 and the SPI peripheral itself are owned
# by the C dual-chip spi transport (firmware/usermods/inkplate/epd_spi.c's epd_spi_dual_*
# functions, docs/refactor_plan.md Phase 9 step 31) -- no Python-side pin constants
# needed for the panel.

# Spectra133 register addresses
SPECTRA133_REG_PSR = const(0x00)
SPECTRA133_REG_PWR = const(0x01)
SPECTRA133_REG_POF = const(0x02)
SPECTRA133_REG_PON = const(0x04)
SPECTRA133_REG_BTST_N = const(0x05)
SPECTRA133_REG_BTST_P = const(0x06)
SPECTRA133_REG_DTM = const(0x10)
SPECTRA133_REG_DRF = const(0x12)
SPECTRA133_REG_PLL = const(0x30)
SPECTRA133_REG_TSC = const(0x40)
SPECTRA133_REG_CDI = const(0x50)
SPECTRA133_REG_TCON = const(0x60)
SPECTRA133_REG_TRES = const(0x61)
SPECTRA133_REG_AN_TM = const(0x74)
SPECTRA133_REG_AGID = const(0x86)
SPECTRA133_REG_BUCK_BOOST_VDDN = const(0xB0)
SPECTRA133_REG_TFT_VCOM_POWER = const(0xB1)
SPECTRA133_REG_EN_BUF = const(0xB6)
SPECTRA133_REG_BOOST_VDDP_EN = const(0xB7)
SPECTRA133_REG_CCSET = const(0xE0)
SPECTRA133_REG_PWS = const(0xE3)
SPECTRA133_REG_CMD66 = const(0xF0)
# Partial Load Window (GDEP133C02) -- selects a sub-rectangle of the panel for
# display_partial() instead of a full refresh.
SPECTRA133_REG_PTLW = const(0x83)

# Spectra133 register values (from manufacturer)
REG_PSR_V = bytes([0xDF, 0x6B])
REG_PWR_V = bytes([0x0F, 0x00, 0x28, 0x2C, 0x28, 0x38])
REG_POF_V = bytes([0x00])
REG_DRF_V = bytes([0x00])
REG_PLL_V = bytes([0x08])
REG_CDI_V = bytes([0xF7])
REG_TCON_V = bytes([0x03, 0x03])
REG_TRES_V = bytes([0x04, 0xB0, 0x03, 0x20])
REG_CMD66_V = bytes([0x49, 0x55, 0x13, 0x5D, 0x05, 0x10])
REG_EN_BUF_V = bytes([0x07])
REG_CCSET_V = bytes([0x01])
REG_PWS_V = bytes([0x22])
REG_AN_TM_V = bytes([0xC0, 0x1C, 0x1C, 0xCC, 0xCC, 0xCC, 0x15, 0x15, 0x55])
REG_AGID_V = bytes([0x10])
REG_BTST_P_V = bytes([0xD8, 0x18])
REG_BOOST_VDDP_EN_V = bytes([0x01])
REG_BTST_N_V = bytes([0xD8, 0x18])
REG_BUCK_BOOST_VDDN_V = bytes([0x01])
REG_TFT_VCOM_POWER_V = bytes([0x02])

# Epaper resolution
D_COLS = const(1200)
D_ROWS = const(1600)

# Chip select targets for dual-driver architecture
CHIP_MASTER = const(1)
CHIP_SLAVE = const(2)
CHIP_BOTH = const(3)

# User pins on PCAL6416A for Inkplate COLOR
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


class Inkplate:
    # Color constants - values are panel color indices
    # User passes 0-5, _color_palette maps to actual panel values
    BLACK = const(0)
    WHITE = const(1)
    YELLOW = const(2)
    RED = const(3)
    BLUE = const(4)
    GREEN = const(5)

    # Maps user color index (0-5) to panel register value
    _color_palette = [0, 1, 2, 3, 5, 6]

    KERNEL_FLOYD_STEINBERG = 0
    KERNEL_JJN = 1
    KERNEL_STUCKI = 2
    KERNEL_BURKES = 3

    _width = D_COLS
    _height = D_ROWS

    rotation = 0
    # gfx_* calls use a rotation numbering mirrored from this board's own `rotation`
    # (board rotation 0 is physically what gfx.c's rotation-remap calls rotation 2, and
    # 1/3 swap relative to Inkplate6COLOR/Inkplate2's own +2 offset -- confirmed against
    # this board's own pre-refactor write_pixel). Kept separate from `rotation` itself
    # since the dual-chip palette image-decode path still expects this board's native
    # rotation numbering unchanged. See set_rotation().
    _gfx_rotation = 2
    text_size = 1

    _panel_state = False

    _framebuf = None

    @classmethod
    def begin(cls):
        cls.wire = I2C(0)
        cls._PCAL6416A = PCAL6416A(cls.wire)
        cls._rtc = RTC(cls.wire)

        # RST/DC/CS_M/CS_S/BUSY/CLK/DIN/PWR_EN/BS0/BS1 + the SPI peripheral itself are
        # owned by the C dual-chip spi transport from here on
        # (firmware/usermods/inkplate/epd_spi.c, docs/refactor_plan.md Phase 9 step 31)
        # -- no more machine.SPI/Pin objects for the panel itself.
        inkplate.select_spi_panel("inkplate13spectra")

        # This panel's 4bpp framebuffer packs even physical x into the HIGH nibble --
        # the opposite of gfx_set_pixel's default (confirmed from this board's own
        # pre-refactor write_pixel/pixel_mask_glut). Session-constant, set once here like
        # Inkplate4TEMPERA's own gfx_set_gs4_nibble_swap(True) call.
        inkplate.gfx_set_gs4_nibble_swap(True)

        # Discharge panel capacitors first, matching the real Arduino reference driver's
        # initDriver() -- setIO() (which brings up the SPI bus itself) only runs later,
        # on the first set_panel_state(True).
        cls.set_panel_pins_to_low()

        cls.VBAT = ADC(Pin(1))
        cls.VBAT.atten(ADC.ATTN_11DB)
        cls.VBAT.width(ADC.WIDTH_12BIT)
        cls.VBAT_EN = GpioPin(cls._PCAL6416A, 9, mode_output)
        cls.VBAT_EN.digital_write(0)

        cls.cursor = [0, 0]
        cls.textColor = 0
        cls.textWrapping = 1

        cls.SD_ENABLE = GpioPin(cls._PCAL6416A, 10, mode_output)

        # Allocate framebuffer (4bpp, 2 pixels per byte)
        # Single C-level bytes multiply + bytearray copy - no Python loop
        cls._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))

        # Set default rotation (landscape, matching Arduino initDriver)
        cls.rotation = 1
        cls._gfx_rotation = (2 - cls.rotation) % 4
        cls._width = D_ROWS
        cls._height = D_COLS

        cls.font_family = montserrat_black
        cls.font = cls.font_family._font

        cls.set_pcal_for_low_power()

        cls._panel_state = False

        return True

    def init_sd_card(self, fast_boot=False):
        self.SD_ENABLE.digital_write(0)
        try:
            os.mount(
                SDCard(slot=3, miso=Pin(13), mosi=Pin(11), sck=Pin(12), cs=Pin(10)),
                "/sd",
            )
            if fast_boot is True:
                if (
                    machine.reset_cause() == machine.PWRON_RESET
                    or machine.reset_cause() == machine.HARD_RESET
                    or machine.reset_cause() == machine.WDT_RESET
                ):
                    machine.soft_reset()
        except Exception:
            print("Sd card could not be read")

    def sd_card_sleep(self):
        self.SD_ENABLE.digital_write(1)
        time.sleep_ms(5)

    def sd_card_wake(self):
        self.SD_ENABLE.digital_write(0)
        time.sleep_ms(5)

    @classmethod
    def set_pcal_for_low_power(cls):
        for x in range(16):
            cls._PCAL6416A.pin_mode(int(x), mode_output)
            cls._PCAL6416A.digital_write(int(x), 0)

    @classmethod
    def get_panel_state(cls):
        return cls._panel_state

    @classmethod
    def set_panel_pins_to_low(cls):
        """Discharge panel capacitors by driving all pins low."""
        inkplate.spi_dual_pins_low()

    @classmethod
    def set_io(cls):
        """Configure GPIOs and SPI for panel communication."""
        inkplate.spi_dual_power_up_io()

    @classmethod
    def reset_panel(cls):
        """Hardware reset of the panel.

        Reuses the single-chip family's epd_spi_reset() (100ms low / 200ms recovery)
        rather than a dual-chip-specific 100ms/100ms pulse -- the real Arduino reference
        driver's own resetPanel() only asks for 100ms/100ms, and a longer recovery delay
        can't hurt, same reasoning already applied to Inkplate2's reset pulse width
        (docs/refactor_plan.md Phase 9 step 31).
        """
        inkplate.spi_panel_reset()

    @classmethod
    def wait_for_busy(cls):
        """Wait until the panel signals ready (BUSY pin goes high)."""
        inkplate.spi_panel_wait_busy(1, 0)

    @classmethod
    def screen_init(cls):
        """Send manufacturer register init sequence to the panel."""
        cls.send_command(SPECTRA133_REG_AN_TM, REG_AN_TM_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_CMD66, REG_CMD66_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PSR, REG_PSR_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PLL, REG_PLL_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_CDI, REG_CDI_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_TCON, REG_TCON_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_AGID, REG_AGID_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PWS, REG_PWS_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_CCSET, REG_CCSET_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_TRES, REG_TRES_V, CHIP_BOTH)
        cls.send_command(SPECTRA133_REG_PWR, REG_PWR_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_EN_BUF, REG_EN_BUF_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BTST_P, REG_BTST_P_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BOOST_VDDP_EN, REG_BOOST_VDDP_EN_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BTST_N, REG_BTST_N_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_BUCK_BOOST_VDDN, REG_BUCK_BOOST_VDDN_V, CHIP_MASTER)
        cls.send_command(SPECTRA133_REG_TFT_VCOM_POWER, REG_TFT_VCOM_POWER_V, CHIP_MASTER)

    @classmethod
    def set_panel_state(cls, state):
        """Power on/off the panel. When powering on, performs full init sequence."""
        if state == cls._panel_state:
            return

        if state:
            # Power up sequence
            cls.set_panel_pins_to_low()
            time.sleep_ms(50)

            # Configure GPIOs (also (re)inits the SPI bus/device, matching the real
            # Arduino reference driver's setIO(), which reconstructs its SPI object here
            # too -- see epd_spi_dual_power_up_io()'s own comment)
            cls.set_io()

            # Enable power
            inkplate.spi_dual_set_power(1)
            time.sleep_ms(100)

            # Hardware reset
            cls.reset_panel()
            time.sleep_ms(100)

            # Send init registers
            cls.screen_init()

            # Power on command
            cls.send_command(SPECTRA133_REG_PON, None, CHIP_BOTH)
            cls.wait_for_busy()
        else:
            # Power off sequence
            cls.send_command(SPECTRA133_REG_POF, REG_POF_V, CHIP_BOTH)
            cls.wait_for_busy()

            # Float DC/CS_M/CS_S/RST/BUSY/PWR_EN to save power (BS0/BS1 deliberately left
            # alone, matching the real Arduino reference driver -- see
            # epd_spi_dual_power_down_io()'s own comment).
            inkplate.spi_dual_power_down_io()

        cls._panel_state = state

    @classmethod
    def send_command(cls, cmd, data=None, chip_id=CHIP_BOTH):
        """Send a command (and optional data) to master, slave, or both chips."""
        inkplate.spi_dual_select(chip_id)
        inkplate.spi_dual_write(bytes([cmd]))
        if data is not None:
            inkplate.spi_dual_write(data)
        inkplate.spi_dual_deselect(chip_id)

    @classmethod
    def clear_display(cls):
        if cls._framebuf is None:
            cls._framebuf = bytearray(b"\x11" * (D_COLS * D_ROWS // 2))
        else:
            cls._framebuf[:] = b"\x11" * len(cls._framebuf)

    @classmethod
    def display(cls, leave_on=False):
        """Update display with framebuffer data using dual-chip architecture."""
        # Power up the panel
        cls.set_panel_state(True)

        mv = memoryview(cls._framebuf)
        half_row = D_COLS // 4  # 300 bytes per half-row

        # Send data to master chip (left side of screen)
        inkplate.spi_dual_select(CHIP_MASTER)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2)
            inkplate.spi_dual_write(mv[row_start : row_start + half_row])
        inkplate.spi_dual_deselect(CHIP_MASTER)

        # Send data to slave chip (right side of screen)
        cls.wait_for_busy()
        inkplate.spi_dual_select(CHIP_SLAVE)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            row_start = i * (D_COLS // 2) + half_row
            inkplate.spi_dual_write(mv[row_start : row_start + half_row])
        inkplate.spi_dual_deselect(CHIP_SLAVE)

        cls.wait_for_busy()

        # Force display refresh on both chips
        cls.send_command(SPECTRA133_REG_DRF, REG_DRF_V, CHIP_BOTH)
        cls.wait_for_busy()

        # Power off if not requested to leave on
        if not leave_on:
            cls.set_panel_state(False)

    # Ported from the real Arduino reference driver's EPDDriver::displayPartial() --
    # refreshes only a sub-rectangle of the panel via the GDEP133C02 controller's PTLW
    # (Partial Load Window) register, instead of a full-frame refresh. Unlike
    # Inkplate10's InkplatePartial (which diffs an old/new framebuffer pair pixel-by-
    # pixel to suppress ghosting), this does no diffing at all -- it unconditionally
    # re-sends the current framebuffer contents inside the given window, exactly
    # matching the Arduino driver's own behavior. x/y/w/h are in this board's normal
    # rotation-aware user-space coordinates (same space as draw_rect/write_pixel/etc).
    @classmethod
    def display_partial(cls, x, y, w, h, leave_on=False):
        # Clip to the screen bounds for the current rotation.
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if x + w > cls.width():
            w = cls.width() - x
        if y + h > cls.height():
            h = cls.height() - y
        if w <= 0 or h <= 0:
            return

        # Map user rectangle to panel-native rectangle (col: 0..D_COLS-1, row:
        # 0..D_ROWS-1). Each case mirrors write_pixel's pre-gfx-port rotation
        # transform -- this uses `cls.rotation` (this board's own Arduino-compatible
        # numbering), NOT `_gfx_rotation` (gfx.c's offset numbering used by the
        # drawing primitives) -- these are the same cases the real Arduino driver's
        # displayPartial() itself switches on.
        r = cls.rotation
        if r == 0:
            # User space: D_COLS x D_ROWS. panel_col = (D_COLS-1)-x, panel_row = (D_ROWS-1)-y.
            col_start = D_COLS - x - w
            col_end = D_COLS - 1 - x
            row_start = D_ROWS - y - h
            row_end = D_ROWS - 1 - y
        elif r == 2:
            # User space: D_COLS x D_ROWS. Identity -- no transform.
            col_start = x
            col_end = x + w - 1
            row_start = y
            row_end = y + h - 1
        elif r == 3:
            # User space: D_ROWS x D_COLS. panel_col = (D_COLS-1)-y, panel_row = x.
            col_start = D_COLS - y - h
            col_end = D_COLS - 1 - y
            row_start = x
            row_end = x + w - 1
        else:  # r == 1
            # User space: D_ROWS x D_COLS. panel_col = y, panel_row = (D_ROWS-1)-x.
            col_start = y
            col_end = y + h - 1
            row_start = D_ROWS - x - w
            row_end = D_ROWS - 1 - x

        # PTLW alignment requirements (GDEP133C02): H: col_start and (col_end+1) must
        # both be multiples of 4. V: row_start must be even; (row_end+1) must be even.
        col_start = (col_start // 4) * 4
        col_end = (((col_end + 4) // 4) * 4) - 1
        if col_end >= D_COLS:
            col_end = D_COLS - 1
        if row_start % 2 != 0:
            row_start -= 1
        if row_start < 0:
            row_start = 0
        if (row_end + 1) % 2 != 0:
            row_end += 1
        if row_end >= D_ROWS:
            row_end = D_ROWS - 1

        cls.set_panel_state(True)

        half_width = D_COLS // 2  # 600 px per chip
        half_bytes = half_width // 2  # 300 bytes per row per chip
        row_stride = D_COLS // 2  # 600 bytes per full framebuffer row

        master_needed = col_start < half_width
        slave_needed = col_end >= half_width

        # Both chips must receive a full PTLW+DTM cycle before DRF, otherwise the
        # uninvolved chip falls back to a full-panel refresh when DRF fires. For the
        # uninvolved chip, a minimal 4x4 null window is used: it re-sends the existing
        # framebuffer data (same as what's already on screen), so the refresh produces
        # no visible change on that side.
        ptlw_null = bytes(
            [
                0x00,
                0x00,  # HRST = 0
                0x00,
                0x07,  # HRED = 7
                0x00,
                0x00,  # VRST = 0
                0x00,
                0x01,  # VRED = 1
                0x01,  # PT = 1 (enable)
            ]
        )

        mv = memoryview(cls._framebuf)

        def send_chip(chip_id, needed, local_col_start, local_col_end, mem_col_off):
            if needed:
                hrst = local_col_start * 2
                hred = (local_col_end + 1) * 2 - 1
                vrst = row_start // 2
                vred = (row_end + 1) // 2 - 1
                ptlw = bytes(
                    [
                        (hrst >> 8) & 0xFF,
                        hrst & 0xFF,
                        (hred >> 8) & 0xFF,
                        hred & 0xFF,
                        (vrst >> 8) & 0xFF,
                        vrst & 0xFF,
                        (vred >> 8) & 0xFF,
                        vred & 0xFF,
                        0x01,
                    ]
                )
                bytes_per_row = (local_col_end - local_col_start + 1) // 2
                r_start, r_end = row_start, row_end
            else:
                ptlw = ptlw_null
                bytes_per_row = 2  # 4 px / 2 px-per-byte
                r_start, r_end = 0, 3

            cls.send_command(SPECTRA133_REG_CMD66, REG_CMD66_V, chip_id)
            cls.send_command(SPECTRA133_REG_PTLW, ptlw, chip_id)

            inkplate.spi_dual_select(chip_id)
            inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
            for row in range(r_start, r_end + 1):
                off = row * row_stride + mem_col_off
                inkplate.spi_dual_write(mv[off : off + bytes_per_row])
            inkplate.spi_dual_deselect(chip_id)

        # Master chip (left half of the screen)
        if master_needed:
            lcs = col_start
            lce = col_end if col_end < half_width else half_width - 1
            send_chip(CHIP_MASTER, True, lcs, lce, lcs // 2)
        else:
            send_chip(CHIP_MASTER, False, 0, 0, 0)

        # Slave chip (right half of the screen)
        cls.wait_for_busy()
        if slave_needed:
            lcs = (col_start - half_width) if col_start >= half_width else 0
            lce = col_end - half_width
            send_chip(CHIP_SLAVE, True, lcs, lce, half_bytes + lcs // 2)
        else:
            send_chip(CHIP_SLAVE, False, 0, 0, half_bytes)

        cls.wait_for_busy()

        # Both chips have received PTLW+DTM; trigger a coordinated refresh.
        cls.send_command(SPECTRA133_REG_DRF, REG_DRF_V, CHIP_BOTH)
        cls.wait_for_busy()

        if not leave_on:
            cls.set_panel_state(False)

    @classmethod
    def gpio_expander_pin(cls, pin, mode):
        return GpioPin(cls._PCAL6416A, pin, mode)

    # Same PCF85263-style RTC chip every parallel-bus board wires -- delegates to
    # shared/rtc.py instead of the hand-rolled BCD conversion/I2C read-write this used to
    # duplicate (never backported when that shared module landed).
    @classmethod
    def rtc_set_time(cls, rtc_hour, rtc_minute, rtc_second):
        cls._rtc.set_time(rtc_hour, rtc_minute, rtc_second)

    @classmethod
    def rtc_set_date(cls, rtc_weekday, rtc_day, rtc_month, rtc_yr):
        cls._rtc.set_date(rtc_weekday, rtc_day, rtc_month, rtc_yr)

    @classmethod
    def rtc_get_rtc_data(cls):
        return cls._rtc.get_data()

    @classmethod
    def clean(cls):
        """Clear the physical display by sending all-white data."""
        cls.set_panel_state(True)

        half_row = D_COLS // 4  # 300 bytes per half-row
        white_half = b"\x11" * half_row

        # Send white data to master chip (left side)
        inkplate.spi_dual_select(CHIP_MASTER)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            inkplate.spi_dual_write(white_half)
        inkplate.spi_dual_deselect(CHIP_MASTER)

        # Send white data to slave chip (right side)
        cls.wait_for_busy()
        inkplate.spi_dual_select(CHIP_SLAVE)
        inkplate.spi_dual_write(bytes([SPECTRA133_REG_DTM]))
        for i in range(D_ROWS):
            inkplate.spi_dual_write(white_half)
        inkplate.spi_dual_deselect(CHIP_SLAVE)

        cls.wait_for_busy()

        # Force display refresh
        cls.send_command(SPECTRA133_REG_DRF, REG_DRF_V, CHIP_BOTH)
        cls.wait_for_busy()

        cls.set_panel_state(False)

    @classmethod
    def width(cls):
        return cls._width

    @classmethod
    def height(cls):
        return cls._height

    # Arduino compatibility functions
    @classmethod
    def set_rotation(cls, x):
        cls.rotation = x % 4
        cls._gfx_rotation = (2 - cls.rotation) % 4
        if cls.rotation == 0 or cls.rotation == 2:
            cls._width = D_COLS
            cls._height = D_ROWS
        elif cls.rotation == 1 or cls.rotation == 3:
            cls._width = D_ROWS
            cls._height = D_COLS

    @classmethod
    def get_rotation(cls):
        return cls.rotation

    @classmethod
    def draw_pixel(cls, x, y, c):
        cls.start_write()
        cls.write_pixel(x, y, c)
        cls.end_write()

    @classmethod
    def start_write(cls):
        pass

    # Maps a user color index (0-5) to the panel's real register value, or None if out
    # of range -- every gfx_* wrapper below does this once per call instead of once per
    # pixel (this board's own pre-refactor write_pixel did the equivalent check/lookup
    # per pixel, since every shape was drawn via a write_pixel-per-point Python loop).
    @classmethod
    def _map_color(cls, c):
        if c > 5:
            return None
        return cls._color_palette[c]

    @classmethod
    def write_pixel(cls, x, y, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_set_pixel(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, c)

    @classmethod
    def write_fill_rect(cls, x, y, w, h, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_rect(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, w, h, c)

    @classmethod
    def write_fast_vline(cls, x, y, h, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_vline(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, h, c)

    @classmethod
    def write_fast_hline(cls, x, y, w, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_hline(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, w, c)

    @classmethod
    def set_text_color(cls, c):
        cls.textColor = c

    @classmethod
    def write_line(cls, x0, y0, x1, y1, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_line(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x0, y0, x1, y1, c)

    @classmethod
    def end_write(cls):
        pass

    @classmethod
    def draw_fast_vline(cls, x, y, h, c):
        cls.start_write()
        cls.write_fast_vline(x, y, h, c)
        cls.end_write()

    @classmethod
    def draw_fast_hline(cls, x, y, w, c):
        cls.start_write()
        cls.write_fast_hline(x, y, w, c)
        cls.end_write()

    @classmethod
    def fill_rect(cls, x, y, w, h, c):
        cls.start_write()
        cls.write_fill_rect(x, y, w, h, c)
        cls.end_write()

    @classmethod
    def fill_screen(cls, c):
        cls.fill_rect(0, 0, cls.width(), cls.height(), c)

    @classmethod
    def draw_line(cls, x0, y0, x1, y1, c):
        cls.start_write()
        cls.write_line(x0, y0, x1, y1, c)
        cls.end_write()

    @classmethod
    def draw_rect(cls, x, y, w, h, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_rect(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, w, h, c)

    @classmethod
    def draw_circle(cls, x, y, r, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_circle(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, r, c)

    @classmethod
    def fill_circle(cls, x, y, r, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_circle(cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, r, c)

    @classmethod
    def draw_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_triangle(
            cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    @classmethod
    def fill_triangle(cls, x0, y0, x1, y1, x2, y2, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_triangle(
            cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x0, y0, x1, y1, x2, y2, c
        )

    @classmethod
    def draw_round_rect(cls, x, y, q, h, r, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_round_rect(
            cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, q, h, r, c
        )

    @classmethod
    def fill_round_rect(cls, x, y, q, h, r, c):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_fill_round_rect(
            cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, q, h, r, c
        )

    @classmethod
    def set_text_wrapping(cls, state: bool):
        cls.textWrapping = state

    @classmethod
    def set_display_mode(cls, mode):
        cls.displayMode = mode

    @classmethod
    def get_display_mode(cls):
        return cls.displayMode

    @classmethod
    def set_text_size(cls, s):
        cls.text_size = s

    @classmethod
    def set_font(cls, f):
        cls.font_family = f
        cls.font = cls.font_family._font

    def reset_cursor(self):
        self.cursor = [0, 0]

    def set_cursor(self, x, y):
        self.cursor = [x, y]

    # Ported from this board's own gfx.py GFX._print_text/_draw_char_4bpp, with the
    # per-char blit routed through inkplate.gfx_draw_char instead (same shape as
    # boards/inkplate6/inkplate6.py's _print_text). Color goes through _color_palette
    # once here instead of once per pixel, like every other gfx_* wrapper on this board.
    def _print_text(self, framebuf, x0, y0, string, size, color, text_wrap=False):
        display_width = self._width
        color = self._color_palette[min(max(color, 0), 5)]

        x = int(x0)
        y = int(y0)
        line_height = 0

        def blit(cx, cy, char_data, ch_w, ch_h):
            inkplate.gfx_draw_char(
                framebuf,
                D_COLS,
                D_ROWS,
                self._gfx_rotation,
                1,
                cx,
                cy,
                char_data,
                ch_w,
                ch_h,
                size,
                color,
            )

        for chunk in string.split("__"):
            try:
                char_data, ch_h, ch_w = self.font_family.get_ch(chunk)
                line_height = max(line_height, ch_h * size)

                if text_wrap is True and x + ch_w * size > display_width:
                    x = 0
                    y += line_height
                    line_height = ch_h * size

                blit(x, y, char_data, ch_w, ch_h)
                x += ch_w * size
            except (ValueError, TypeError):
                for char in chunk:
                    if char == "\n":
                        x = x0
                        y += line_height
                        line_height = 0
                        continue

                    try:
                        char_data, ch_h, ch_w = self.font_family.get_ch(char)
                    except (ValueError, TypeError):
                        char_data, ch_h, ch_w = self.font_family.get_ch("?")

                    line_height = max(line_height, ch_h * size)

                    if text_wrap is True and x + ch_w * size > display_width:
                        x = 0
                        y += line_height
                        line_height = ch_h * size

                    blit(x, y, char_data, ch_w, ch_h)
                    x += ch_w * size
        return [x, y], line_height

    def print_text(self, x, y, s):
        self._print_text(
            self._framebuf,
            x,
            y,
            s,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )

    def println(self, text):
        self.cursor, line_height = self._print_text(
            self._framebuf,
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )
        self.cursor[1] += line_height
        self.cursor[0] = 0

    def print(self, text):
        self.cursor, line_height = self._print_text(
            self._framebuf,
            self.cursor[0],
            self.cursor[1],
            text,
            self.text_size,
            self.textColor,
            text_wrap=self.textWrapping,
        )

    def wrap_text(self, text, max_chars):
        lines = []
        for paragraph in text.split("\n"):
            while len(paragraph) > max_chars:
                # Find last space within limit
                wrap_at = paragraph.rfind(" ", 0, max_chars)
                if wrap_at == -1:
                    wrap_at = max_chars
                lines.append(paragraph[:wrap_at])
                paragraph = paragraph[wrap_at:].lstrip()
            if paragraph:
                lines.append(paragraph)
        return lines

    def draw_text_box(self, x0, y0, x1, y1, text, line_height=20, text_size=None):
        if text_size is not None:
            self.set_text_size(text_size)
        max_width = x1 - x0
        char_width = 6 * self.text_size  # rough estimate
        max_chars = max_width // char_width
        lines = self.wrap_text(text, max_chars)
        y = y0
        for line in lines:
            if y > y1 - 2 * line_height:
                s = list(line)
                s[-1] = "."
                s[-2] = "."
                s[-3] = "."
                s = "".join(s)
                self.print_text(x0, y, s)
                break
            self.print_text(x0, y, line)
            y += line_height

    def read_battery(self):
        self.VBAT_EN.digital_write(1)
        # Probably don't need to delay since Micropython is slow, but we do it anyway
        time.sleep_ms(1)
        value = self.VBAT.read()
        self.VBAT_EN.digital_write(0)
        result = (value / 4095.0) * 1.1 * 3.548133892 * 2
        return result

    @classmethod
    def draw_bitmap(cls, x, y, data, w, h, c=BLACK):
        c = cls._map_color(c)
        if c is None:
            return
        inkplate.gfx_draw_bitmap(
            cls._framebuf, D_COLS, D_ROWS, cls._gfx_rotation, 1, x, y, data, w, h, c
        )

    def draw_color_image(self, x, y, width, height, image):
        for i in range(0, len(image)):
            # Unpack the byte into two pixel values
            pixel_value1 = (image[i] & 0b11110000) >> 4
            pixel_value2 = image[i] & 0b00001111

            # Calculate the x and y coordinates of the pixels
            x1 = (2 * i) % width
            y1 = (2 * i) // width
            x2 = (2 * i + 1) % width
            y2 = (2 * i + 1) // width

            # Check if the coordinates are within the image bounds
            if x1 < width and y1 < height:
                self.write_pixel(x1 + x, y1 + y, pixel_value1)
            if x2 < width and y2 < height:
                self.write_pixel(x2 + x, y2 + y, pixel_value2)

    def rtc_get_data(self):
        return self.rtc_get_rtc_data()

    def draw_image(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """
        Draw an image from either web URL or local file system
        Args:
            path: Either a web URL (http/https) or local file path
            x0, y0: Coordinates for top-left corner of image
            dither: Whether to apply dithering
            kernel_type: Dithering kernel type (0=Floyd-Steinberg, etc.)
            invert: Invert colors
        """
        # Check if path is a web URL
        if path.startswith(("http://", "https://")):
            # Determine image type from URL
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_web(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_web(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_web(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported web image format. Must be .bmp, .jpg, or .png")
        else:
            # Handle local file
            if path.lower().endswith(".bmp"):
                self.draw_bmp_from_sd(path, x0, y0, invert, dither)
            elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                self.draw_jpg_from_sd(path, x0, y0, invert, dither, kernel_type)
            elif path.lower().endswith(".png"):
                self.draw_png_from_sd(path, x0, y0, invert, dither, kernel_type)
            else:
                raise ValueError("Unsupported local image format. Must be .bmp, .jpg, or .png")

    def draw_jpg_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        with open(path, "rb") as f:
            jpg_data = f.read()
        inkplate.jpeg_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, jpg_data
        )
        gc.collect()

    def draw_png_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        with open(path, "rb") as f:
            png_data = f.read()
        # No scratch buffer passed: png_draw_palette only needs one for a rare
        # Adam7-interlaced source (dithers non-interlaced PNGs -- the common case --
        # inline, per pixel, no whole-image buffer at all). Pre-allocating one here
        # unconditionally used to reliably MemoryError on real Inkplate6COLOR
        # hardware for completely ordinary photos (docs/refactor_plan.md Phase 7
        # step 21's follow-up) -- worse than the rare case this was meant to serve.
        inkplate.png_draw_palette(
            self._framebuf,
            None,
            self.rotation,
            x0,
            y0,
            invert,
            dither,
            kernel_type,
            png_data,
            None,
        )
        gc.collect()

    def draw_png_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            png_data = response.content
            response.close()

            # See draw_png_from_sd's identical comment on why no scratch buffer.
            inkplate.png_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                png_data,
                None,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_png_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def draw_jpg_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=20)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            jpg_data = response.content
            response.close()

            inkplate.jpeg_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                jpg_data,
            )
            gc.collect()
        except Exception as e:
            print("Error in draw_jpg_from_web:", e)
            if "response" in locals():
                response.close()
            raise

    def draw_bmp_from_sd(self, path, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        import gc

        gc.collect()
        with open(path, "rb") as f:
            bmp_data = f.read()

        inkplate.bmp_draw_palette(
            self._framebuf, None, self.rotation, x0, y0, invert, dither, kernel_type, bmp_data
        )
        del bmp_data
        gc.collect()

    def draw_bmp_from_web(self, url, x0=0, y0=0, invert=False, dither=False, kernel_type=0):
        """Display a BMP image downloaded from the web

        Args:
            bmp_data (bytes): Raw BMP file data
            x0 (int): X position to start drawing
            y0 (int): Y position to start drawing
            invert (bool): Whether to invert colors
            dither (bool): Whether to apply dithering
        """
        import gc
        import urequests

        try:
            response = urequests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"HTTP Error {response.status_code}")

            bmp_data = response.content
            response.close()

            inkplate.bmp_draw_palette(
                self._framebuf,
                None,
                self.rotation,
                x0,
                y0,
                invert,
                dither,
                kernel_type,
                bmp_data,
            )
            del bmp_data
            gc.collect()
        except Exception as e:
            print("Error in draw_bmp_from_web:", e)
            if "response" in locals():
                response.close()
            raise


if __name__ == "__main__":
    print(
        "WARNING: You are running the Inkplate module itself, import this module "
        "into your example and use it that way"
    )
