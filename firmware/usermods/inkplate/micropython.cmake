add_library(usermod_inkplate INTERFACE)

target_sources(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/inkplatemodule.c
)

target_include_directories(usermod_inkplate INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_inkplate)
