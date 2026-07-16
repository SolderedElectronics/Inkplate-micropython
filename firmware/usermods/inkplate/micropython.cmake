add_library(usermod_inkplate INTERFACE)

target_sources(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/inkplatemodule.c
    ${CMAKE_CURRENT_LIST_DIR}/display/expander_bridge.c
    ${CMAKE_CURRENT_LIST_DIR}/display/board_config.c
    ${CMAKE_CURRENT_LIST_DIR}/display/epd_control.c
    ${CMAKE_CURRENT_LIST_DIR}/display/epd_i2s.c
    ${CMAKE_CURRENT_LIST_DIR}/display/epd_partial_lut.c
    ${CMAKE_CURRENT_LIST_DIR}/display/waveform.c
    ${CMAKE_CURRENT_LIST_DIR}/image/bmp_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/image/bmp_draw.c
    ${CMAKE_CURRENT_LIST_DIR}/image/dither.c
    ${CMAKE_CURRENT_LIST_DIR}/display/gfx.c
    ${CMAKE_CURRENT_LIST_DIR}/image/jpeg_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/image/jpeg_draw.c
    ${CMAKE_CURRENT_LIST_DIR}/image/pngle.c
    ${CMAKE_CURRENT_LIST_DIR}/image/png_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/image/png_draw.c
    ${CMAKE_CURRENT_LIST_DIR}/display/spi_panel_config.c
    ${CMAKE_CURRENT_LIST_DIR}/image/spi_panel_palette.c
    ${CMAKE_CURRENT_LIST_DIR}/display/epd_spi.c
)

target_include_directories(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_inkplate)
