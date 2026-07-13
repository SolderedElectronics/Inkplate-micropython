add_library(usermod_inkplate INTERFACE)

target_sources(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/inkplatemodule.c
    ${CMAKE_CURRENT_LIST_DIR}/expander_bridge.c
    ${CMAKE_CURRENT_LIST_DIR}/board_config.c
    ${CMAKE_CURRENT_LIST_DIR}/epd_bitbang.c
    ${CMAKE_CURRENT_LIST_DIR}/epd_i2s.c
    ${CMAKE_CURRENT_LIST_DIR}/epd_partial_lut.c
    ${CMAKE_CURRENT_LIST_DIR}/waveform.c
    ${CMAKE_CURRENT_LIST_DIR}/bmp_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/bmp_draw.c
    ${CMAKE_CURRENT_LIST_DIR}/gfx.c
    ${CMAKE_CURRENT_LIST_DIR}/jpeg_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/jpeg_draw.c
    ${CMAKE_CURRENT_LIST_DIR}/pngle.c
    ${CMAKE_CURRENT_LIST_DIR}/png_decode.c
    ${CMAKE_CURRENT_LIST_DIR}/png_draw.c
)

target_include_directories(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_inkplate)
