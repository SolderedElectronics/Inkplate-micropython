/**
 * @file gfx.h
 * @brief Every primitive here writes directly into a raw framebuf pointer, applying
 *        the same physical/rotation remap and display-mode packing in one consistent
 *        place.
 *
 * display_mode: 0 = 1bpp mono, LSB-first per byte (matches the waveform engine's
 * expected bit order); 2 = 1bpp mono, MSB-first per byte (for boards with dual BW/RED
 * planes whose panel packs the opposite bit order); any other value = 4bpp GS4_HMSB raw
 * 0-7 gray level.
 * rotation: 0 = 0 deg, 1 = 90 deg CW, 2 = 180 deg, 3 = 270 deg CCW (logical-to-physical).
 * phys_w/phys_h: physical (unrotated) framebuffer dimensions in pixels.
 *
 * Pure logic, no MicroPython/ESP-IDF dependency -- host-compilable.
 */
#ifndef INKPLATE_GFX_H
#define INKPLATE_GFX_H

#include <stdint.h>

/**
 * @brief Enable or disable physical column mirroring for boards that scan columns in the
 *        opposite direction.
 *
 * Flips every primitive's physical column (px = phys_w - 1 - px) after the rotation remap.
 * This is a one-time session-constant switch, set once at board init, rather than a
 * per-call parameter threaded through every gfx_* signature -- unlike rotation/display_mode,
 * this never varies call to call once a board is selected. Defaults to off.
 * @param enable Nonzero to enable column mirroring, 0 to disable.
 */
void gfx_set_mirror_x(int enable);

/**
 * @brief Enable or disable swapped nibble order for GS4_HMSB pixel packing.
 *
 * Flips which nibble each pixel writes (even x -> high nibble, odd x -> low nibble, the
 * opposite of gfx_set_pixel's default) for boards whose panel expects that convention. Same
 * one-time session-constant shape as gfx_set_mirror_x, not a per-call param.
 * @param enable Nonzero to swap nibble order, 0 for the default order.
 */
void gfx_set_gs4_nibble_swap(int enable);

/**
 * @brief Set a single pixel, applying the rotation remap and display-mode packing.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x Logical x coordinate.
 * @param y Logical y coordinate.
 * @param color Pixel value: 0/1 for mono, 0-7 gray level for GS4_HMSB.
 */
void gfx_set_pixel(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x,
                   int y, int color);

/**
 * @brief Fill the entire framebuffer with one raw byte value.
 *
 * Rotation/display_mode-agnostic: a full clear touches every byte regardless, so there is
 * no per-pixel remap or packing to do here, unlike every other gfx_* primitive.
 * @param fb Raw framebuffer pointer.
 * @param len Framebuffer length in bytes.
 * @param value Raw byte value to fill with (e.g. 0x00 for mono-black, 0x77 for GS4 white).
 */
void gfx_buf_fill(uint8_t *fb, int len, uint8_t value);

/**
 * @brief Blit a 1bpp source bitmap with a transparent background.
 *
 * Draws `color` wherever the source bit is set and leaves the destination pixel untouched
 * otherwise.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the bitmap's top-left corner.
 * @param y0 Logical y coordinate of the bitmap's top-left corner.
 * @param bitmap Source bitmap data, row_bytes = ceil(bmp_w/8) bytes per row, MSB-first per row.
 * @param bmp_w Source bitmap width in pixels.
 * @param bmp_h Source bitmap height in pixels.
 * @param color Pixel value to draw where the source bit is set.
 */
void gfx_draw_bitmap(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, const uint8_t *bitmap, int bmp_w, int bmp_h, int color);

/**
 * @brief Draw a horizontal line.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the line's left end.
 * @param y0 Logical y coordinate of the line.
 * @param width Line length in pixels.
 * @param color Pixel value to draw.
 */
void gfx_hline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int width, int color);

/**
 * @brief Draw a vertical line.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the line.
 * @param y0 Logical y coordinate of the line's top end.
 * @param height Line length in pixels.
 * @param color Pixel value to draw.
 */
void gfx_vline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int height, int color);

/**
 * @brief Draw a line between two points using Bresenham's algorithm.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the start point.
 * @param y0 Logical y coordinate of the start point.
 * @param x1 Logical x coordinate of the end point.
 * @param y1 Logical y coordinate of the end point.
 * @param color Pixel value to draw.
 */
void gfx_line(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int x1, int y1, int color);

/**
 * @brief Draw an unfilled rectangle outline.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the top-left corner.
 * @param y0 Logical y coordinate of the top-left corner.
 * @param width Rectangle width in pixels.
 * @param height Rectangle height in pixels.
 * @param color Pixel value to draw.
 */
void gfx_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int width, int height, int color);

/**
 * @brief Draw a filled rectangle.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the top-left corner.
 * @param y0 Logical y coordinate of the top-left corner.
 * @param width Rectangle width in pixels.
 * @param height Rectangle height in pixels.
 * @param color Pixel value to draw.
 */
void gfx_fill_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, int width, int height, int color);

/**
 * @brief Draw a circle outline using the midpoint circle algorithm.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the center.
 * @param y0 Logical y coordinate of the center.
 * @param radius Circle radius in pixels.
 * @param color Pixel value to draw.
 */
void gfx_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                int y0, int radius, int color);

/**
 * @brief Draw a filled circle.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the center.
 * @param y0 Logical y coordinate of the center.
 * @param radius Circle radius in pixels.
 * @param color Pixel value to draw.
 */
void gfx_fill_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, int radius, int color);

/**
 * @brief Draw a triangle outline by connecting three vertices with lines.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the first vertex.
 * @param y0 Logical y coordinate of the first vertex.
 * @param x1 Logical x coordinate of the second vertex.
 * @param y1 Logical y coordinate of the second vertex.
 * @param x2 Logical x coordinate of the third vertex.
 * @param y2 Logical y coordinate of the third vertex.
 * @param color Pixel value to draw.
 */
void gfx_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, int x1, int y1, int x2, int y2, int color);

/**
 * @brief Draw a filled triangle using a scanline fill.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the first vertex.
 * @param y0 Logical y coordinate of the first vertex.
 * @param x1 Logical x coordinate of the second vertex.
 * @param y1 Logical y coordinate of the second vertex.
 * @param x2 Logical x coordinate of the third vertex.
 * @param y2 Logical y coordinate of the third vertex.
 * @param color Pixel value to draw.
 */
void gfx_fill_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                       int x0, int y0, int x1, int y1, int x2, int y2, int color);

/**
 * @brief Draw a rectangle outline with rounded corners.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the top-left corner.
 * @param y0 Logical y coordinate of the top-left corner.
 * @param width Rectangle width in pixels.
 * @param height Rectangle height in pixels.
 * @param radius Corner radius in pixels.
 * @param color Pixel value to draw.
 */
void gfx_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                    int y0, int width, int height, int radius, int color);

/**
 * @brief Draw a filled rectangle with rounded corners.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the top-left corner.
 * @param y0 Logical y coordinate of the top-left corner.
 * @param width Rectangle width in pixels.
 * @param height Rectangle height in pixels.
 * @param radius Corner radius in pixels.
 * @param color Pixel value to draw.
 */
void gfx_fill_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                         int x0, int y0, int width, int height, int radius, int color);

/**
 * @brief Blit one pre-rendered glyph bitmap at an integer scale.
 * @param fb Raw framebuffer pointer.
 * @param phys_w Physical (unrotated) framebuffer width in pixels.
 * @param phys_h Physical (unrotated) framebuffer height in pixels.
 * @param rotation 0/1/2/3 for 0/90/180/270 deg logical-to-physical rotation.
 * @param display_mode 0 or 2 for 1bpp mono (LSB- or MSB-first), any other value for 4bpp GS4_HMSB.
 * @param x0 Logical x coordinate of the glyph's top-left corner.
 * @param y0 Logical y coordinate of the glyph's top-left corner.
 * @param char_data Glyph bitmap: char_h rows of ceil(char_w/8) bytes each, MSB-first per row.
 * @param char_w Glyph width in pixels, before scaling.
 * @param char_h Glyph height in pixels, before scaling.
 * @param size Integer scale factor.
 * @param color Pixel value to draw.
 */
void gfx_draw_char(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, const uint8_t *char_data, int char_w, int char_h, int size, int color);

#endif
