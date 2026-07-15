#include "epd_spi.h"

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_rom_sys.h"

// VSPI/SPI3_HOST -- matches the pre-refactor Python driver's machine.SPI(2) choice,
// whose default pins (sck=18, mosi=23) are this panel's own pin_clk/pin_din.
#define EPD_SPI_HOST SPI3_HOST

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

    gpio_config_t busy_conf = {
        .pin_bit_mask = (1ULL << cfg->pin_busy),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&busy_conf);

    // De-select the panel (and let DC settle high) before the SPI bus/device even
    // exists, same ordering as the Arduino reference's setPanelDeepSleep(false).
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
    spi_bus_initialize(EPD_SPI_HOST, &bus_conf, SPI_DMA_CH_AUTO);

    spi_device_interface_config_t dev_conf = {
        .clock_speed_hz = (int)cfg->spi_freq_hz,
        .mode = 0,          // SPI_MODE0, matches the Arduino reference's SPISettings
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
    esp_rom_delay_us(1000);
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
            continue; // wait forever
        }
        waited_us += 1000;
        if (waited_us >= timeout_us) {
            return 0;
        }
    }
    return 1;
}

// Splits `len` bytes into EPD_SPI_CHUNK_BYTES-sized spi_device_transmit() calls -- CS/DC
// framing stays the caller's responsibility (epd_spi_send_command/send_data), this is
// purely the per-transaction size limit the SPI driver imposes.
static void epd_spi_transfer(const uint8_t *data, size_t len)
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
        spi_device_transmit(s_spi_dev, &t);
        offset += chunk;
    }
}

void epd_spi_send_command(const spi_panel_config_t *cfg, uint8_t command)
{
    gpio_set_level(cfg->pin_cs, 0);
    gpio_set_level(cfg->pin_dc, 0);
    esp_rom_delay_us(10);
    epd_spi_transfer(&command, 1);
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
    epd_spi_transfer(data, len);
    gpio_set_level(cfg->pin_cs, 1);
    esp_rom_delay_us(1000);
}
