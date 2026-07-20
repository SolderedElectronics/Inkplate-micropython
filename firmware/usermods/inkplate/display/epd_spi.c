/**
 * @file epd_spi.c
 * @brief SPI transport implementation for single- and dual-chip SPI panels.
 */
#include "epd_spi.h"

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_rom_sys.h"
#include <stdbool.h>

// VSPI/SPI3_HOST -- matches the pre-refactor Python driver's machine.SPI(2) choice,
// whose default pins (sck=18, mosi=23) are this panel's own pin_clk/pin_din. This panel
// and SD's slot=3 (SPI2_HOST/HSPI, per SDSPI_DEFAULT_HOST in
// esp_driver_sdspi/include/driver/sdspi_host.h) never share a peripheral, so no
// separation logic is needed here.
#define EPD_SPI_HOST SPI3_HOST

// Classic ESP32 has only 2 SPI-capable DMA channels total. machine.SDCard(slot=3)
// hardcodes DMA channel 1 for its own HSPI/SPI2_HOST bus (spi_dma_channel_defaults[1] ==
// 1 in ports/esp32/machine_sdcard.c). Letting this panel's own spi_bus_initialize()
// auto-pick a channel (SPI_DMA_CH_AUTO) risks it grabbing channel 1 first (this panel's
// begin() runs before SD ever inits), leaving none free for SD and breaking its mount.
// Pin this panel to channel 2 explicitly instead -- the same channel that table's own
// slot=2/VSPI entry already uses, so the two boards' DMA channel choices can never
// collide regardless of init order.
#define EPD_SPI_DMA_CHAN 2

// ESP-IDF's spi_master driver caps a single spi_device_transmit() transaction at
// max_transfer_sz bytes (4092 by default) -- far smaller than a full framebuffer (600x448
// 4bpp = 134400 bytes for Inkplate6COLOR). epd_spi_transfer() below chunks any payload
// into pieces this size; bus_conf.max_transfer_sz is set to match explicitly rather than
// relying on the driver's own default, so the two can't silently drift apart.
#define EPD_SPI_CHUNK_BYTES 4092

static spi_device_handle_t s_spi_dev = NULL;

void epd_spi_init(const spi_panel_config_t *cfg)
{
    gpio_config_t out_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_rst) | (1ULL << cfg->pin_dc) | (1ULL << cfg->pin_cs),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&out_conf);

    // Pull-up enabled: Inkplate2 needs it on BUSY; harmless no-op for Inkplate6COLOR
    // since a pull-up is a no-op once the panel's controller actively drives the line.
    gpio_config_t busy_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_busy),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&busy_conf);

    // De-select the panel (and let DC settle high) before the SPI bus/device even exists.
    gpio_set_level(cfg->pin_dc, 1);
    gpio_set_level(cfg->pin_cs, 1);

    spi_bus_config_t bus_conf = {
        .mosi_io_num = cfg->pin_din,
        .miso_io_num = -1,
        .sclk_io_num = cfg->pin_clk,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = EPD_SPI_CHUNK_BYTES,
    };
    spi_bus_initialize(EPD_SPI_HOST, &bus_conf, EPD_SPI_DMA_CHAN);

    spi_device_interface_config_t dev_conf = {
        .clock_speed_hz = (int)cfg->spi_freq_hz,
        .mode = 0,          // SPI_MODE0
        .spics_io_num = -1, // CS is toggled manually below, framing DC transitions
        .queue_size = 1,
    };
    spi_bus_add_device(EPD_SPI_HOST, &dev_conf, &s_spi_dev);
}

void epd_spi_deinit(const spi_panel_config_t *cfg)
{
    (void)cfg;
    if (s_spi_dev != NULL) {
        spi_bus_remove_device(s_spi_dev);
        s_spi_dev = NULL;
        spi_bus_free(EPD_SPI_HOST);
    }
}

void epd_spi_reset(const spi_panel_config_t *cfg)
{
    gpio_set_level(cfg->pin_rst, 0);
    esp_rom_delay_us(100000);
    gpio_set_level(cfg->pin_rst, 1);
    esp_rom_delay_us(200000);
}

void epd_spi_set_rst(const spi_panel_config_t *cfg, int level)
{
    gpio_set_level(cfg->pin_rst, level);
}

int epd_spi_wait_busy(const spi_panel_config_t *cfg, int level, uint32_t timeout_ms)
{
    uint32_t waited_us = 0;
    const uint32_t timeout_us = timeout_ms * 1000u;
    while (gpio_get_level(cfg->pin_busy) != level) {
        esp_rom_delay_us(1000);
        if (timeout_ms == 0) {
            continue; // Wait forever
        }
        waited_us += 1000;
        if (waited_us >= timeout_us) {
            return 0;
        }
    }
    return 1;
}

// Splits `len` bytes into EPD_SPI_CHUNK_BYTES-sized spi_device_transmit() calls on the
// given device -- CS/DC framing stays the caller's responsibility (epd_spi_send_command/
// send_data, epd_spi_dual_write), this is purely the per-transaction size limit the SPI
// driver imposes. Takes an explicit device handle since the dual-chip transport below
// uses a second, separate spi_device_handle_t from this file's single-chip path.
static void epd_spi_transfer(spi_device_handle_t dev, const uint8_t *data, size_t len)
{
    size_t offset = 0;
    while (offset < len) {
        size_t chunk = len - offset;
        if (chunk > EPD_SPI_CHUNK_BYTES) {
            chunk = EPD_SPI_CHUNK_BYTES;
        }
        spi_transaction_t t = {0};
        t.length = chunk * 8;
        t.tx_buffer = data + offset;
        spi_device_transmit(dev, &t);
        offset += chunk;
    }
}

void epd_spi_send_command(const spi_panel_config_t *cfg, uint8_t command)
{
    gpio_set_level(cfg->pin_cs, 0);
    gpio_set_level(cfg->pin_dc, 0);
    esp_rom_delay_us(10);
    epd_spi_transfer(s_spi_dev, &command, 1);
    gpio_set_level(cfg->pin_cs, 1);
    esp_rom_delay_us(1000);
}

void epd_spi_send_data(const spi_panel_config_t *cfg, const uint8_t *data, size_t len)
{
    if (len == 0) {
        return;
    }
    gpio_set_level(cfg->pin_cs, 0);
    gpio_set_level(cfg->pin_dc, 1);
    esp_rom_delay_us(10);
    epd_spi_transfer(s_spi_dev, data, len);
    gpio_set_level(cfg->pin_cs, 1);
    esp_rom_delay_us(1000);
}

// Inkplate13SPECTRA dual-chip transport: this is an ESP32-S3 board, built as its own
// firmware target, never linked into the same binary as the classic-ESP32 6COLOR/
// Inkplate2 build -- reusing EPD_SPI_DUAL_HOST's numeric value alongside EPD_SPI_HOST
// above is safe since only one of the two transports is ever live in a given firmware
// image.
#define EPD_SPI_DUAL_HOST SPI3_HOST

static spi_device_handle_t s_spi_dev_dual = NULL;
static bool s_dual_bus_initialized = false;

void epd_spi_dual_pins_low(const spi_panel_config_t *cfg)
{
    gpio_config_t out_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_dc) | (1ULL << cfg->pin_cs) | (1ULL << cfg->pin_cs2) |
                        (1ULL << cfg->pin_rst) | (1ULL << cfg->pin_busy) |
                        (1ULL << cfg->pin_pwr_en) | (1ULL << cfg->pin_bs0) |
                        (1ULL << cfg->pin_bs1),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&out_conf);

    gpio_set_level(cfg->pin_dc, 0);
    gpio_set_level(cfg->pin_cs, 0);
    gpio_set_level(cfg->pin_cs2, 0);
    gpio_set_level(cfg->pin_rst, 0);
    gpio_set_level(cfg->pin_busy, 0);
    gpio_set_level(cfg->pin_pwr_en, 0);
    gpio_set_level(cfg->pin_bs0, 0);
    gpio_set_level(cfg->pin_bs1, 0);
}

void epd_spi_dual_power_up_io(const spi_panel_config_t *cfg)
{
    gpio_config_t out_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_dc) | (1ULL << cfg->pin_cs) | (1ULL << cfg->pin_cs2) |
                        (1ULL << cfg->pin_rst) | (1ULL << cfg->pin_pwr_en) |
                        (1ULL << cfg->pin_bs0) | (1ULL << cfg->pin_bs1),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&out_conf);

    gpio_config_t busy_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_busy),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&busy_conf);

    // Power-up idle levels for DC/CS/CS2/RST/PWR_EN/BS0/BS1.
    gpio_set_level(cfg->pin_dc, 1);
    gpio_set_level(cfg->pin_cs, 1);
    gpio_set_level(cfg->pin_cs2, 1);
    gpio_set_level(cfg->pin_rst, 0);
    gpio_set_level(cfg->pin_pwr_en, 0);
    gpio_set_level(cfg->pin_bs0, 0);
    gpio_set_level(cfg->pin_bs1, 1);

    // The SPI bus/device is reconstructed every power-on cycle; tear down a
    // previously-added device/bus first since ESP-IDF errors on re-initializing an
    // already-initialized host.
    if (s_dual_bus_initialized) {
        spi_bus_remove_device(s_spi_dev_dual);
        s_spi_dev_dual = NULL;
        spi_bus_free(EPD_SPI_DUAL_HOST);
        s_dual_bus_initialized = false;
    }

    spi_bus_config_t bus_conf = {
        .mosi_io_num = cfg->pin_din,
        .miso_io_num = -1,
        .sclk_io_num = cfg->pin_clk,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = EPD_SPI_CHUNK_BYTES,
    };
    spi_bus_initialize(EPD_SPI_DUAL_HOST, &bus_conf, SPI_DMA_CH_AUTO);

    spi_device_interface_config_t dev_conf = {
        .clock_speed_hz = (int)cfg->spi_freq_hz,
        .mode = 0,          // SPI_MODE0
        .spics_io_num = -1, // both CS lines are toggled manually, not by the driver
        .queue_size = 1,
    };
    spi_bus_add_device(EPD_SPI_DUAL_HOST, &dev_conf, &s_spi_dev_dual);
    s_dual_bus_initialized = true;
}

void epd_spi_dual_power_down_io(const spi_panel_config_t *cfg)
{
    gpio_config_t in_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_dc) | (1ULL << cfg->pin_cs) | (1ULL << cfg->pin_cs2) |
                        (1ULL << cfg->pin_rst) | (1ULL << cfg->pin_busy) |
                        (1ULL << cfg->pin_pwr_en),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&in_conf);
    // Pre-arms the PWR_EN output latch for the next power-up.
    gpio_set_level(cfg->pin_pwr_en, 0);
}

void epd_spi_dual_set_power(const spi_panel_config_t *cfg, int level)
{
    gpio_set_level(cfg->pin_pwr_en, level);
}

void epd_spi_dual_select(const spi_panel_config_t *cfg, int chip_mask)
{
    if (chip_mask & EPD_SPI_CHIP_SLAVE) {
        gpio_set_level(cfg->pin_cs2, 0);
    }
    if (chip_mask & EPD_SPI_CHIP_MASTER) {
        gpio_set_level(cfg->pin_cs, 0);
    }
}

void epd_spi_dual_deselect(const spi_panel_config_t *cfg, int chip_mask)
{
    if (chip_mask & EPD_SPI_CHIP_SLAVE) {
        gpio_set_level(cfg->pin_cs2, 1);
    }
    if (chip_mask & EPD_SPI_CHIP_MASTER) {
        gpio_set_level(cfg->pin_cs, 1);
    }
}

void epd_spi_dual_write(const uint8_t *data, size_t len)
{
    epd_spi_transfer(s_spi_dev_dual, data, len);
}
