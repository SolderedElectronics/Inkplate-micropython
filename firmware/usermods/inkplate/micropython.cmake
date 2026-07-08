add_library(usermod_inkplate INTERFACE)

target_sources(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/inkplatemodule.c
    ${CMAKE_CURRENT_LIST_DIR}/expander_bridge.c
    ${CMAKE_CURRENT_LIST_DIR}/board_config.c
    ${CMAKE_CURRENT_LIST_DIR}/epd_bitbang.c
    ${CMAKE_CURRENT_LIST_DIR}/epd_i2s.c
    ${CMAKE_CURRENT_LIST_DIR}/waveform.c
    ${CMAKE_CURRENT_LIST_DIR}/gs_pack.c
)

target_include_directories(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_inkplate)
