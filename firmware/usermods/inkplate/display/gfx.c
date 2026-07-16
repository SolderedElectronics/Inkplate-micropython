#include "gfx.h"

#include <string.h>

void gfx_buf_fill(uint8_t *fb, int len, uint8_t value)
{
    memset(fb, value, (size_t)len);
}

// Matches Python's `//` (floor division), not C's `/` (truncation toward zero) -- needed by
// gfx_fill_triangle's scanline math, which can see negative numerators/denominators once the
// three vertices aren't sorted left-to-right.
static int floordiv(int a, int b)
{
    int q = a / b;
    int r = a % b;
    if (r != 0 && ((r < 0) != (b < 0))) {
        q--;
    }
    return q;
}

static double min3d(double a, double b, double c)
{
    double m = a;
    if (b < m) {
        m = b;
    }
    if (c < m) {
        m = c;
    }
    return m;
}

static void swap_int(int *a, int *b)
{
    int t = *a;
    *a = *b;
    *b = t;
}

// See gfx_set_mirror_x's declaration (gfx.h) for why this is static session state rather
// than a per-call parameter.
static int s_mirror_x = 0;

void gfx_set_mirror_x(int enable)
{
    s_mirror_x = enable;
}

// See gfx_set_gs4_nibble_swap's declaration (gfx.h) for why this is static session state
// rather than a per-call parameter.
static int s_gs4_nibble_swap = 0;

void gfx_set_gs4_nibble_swap(int enable)
{
    s_gs4_nibble_swap = enable;
}

// Single pixel-write core -- consolidates what was boards/inkplate10/inkplate10.py's
// write_pixel_viper (logical-bounds check with rotation-aware swap, physical remap, then
// 1bpp bit set/clear or 4bpp GS4_HMSB nibble pack). Every primitive below funnels through
// this, so the remap/packing logic exists in exactly one place.
void gfx_set_pixel(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x,
                   int y, int color)
{
    int w = phys_w;
    int h = phys_h;

    if (rotation & 1) {
        if (x < 0 || y < 0 || x >= h || y >= w) {
            return;
        }
    } else {
        if (x < 0 || y < 0 || x >= w || y >= h) {
            return;
        }
    }

    int px, py;
    switch (rotation) {
        case 0:
            px = x;
            py = y;
            break;
        case 1:
            px = y;
            py = h - 1 - x;
            break;
        case 2:
            px = w - 1 - x;
            py = h - 1 - y;
            break;
        default: // 3
            px = w - 1 - y;
            py = x;
            break;
    }

    if (s_mirror_x) {
        px = w - 1 - px;
    }

    if (display_mode == 0) {
        int idx = (py * w + px) >> 3;
        int shift = px & 7;
        if (color) {
            fb[idx] |= (uint8_t)(1 << shift);
        } else {
            fb[idx] &= (uint8_t)~(1 << shift);
        }
    } else {
        color &= 0x07;
        int byte_index = py * (w / 2) + (px >> 1);
        int pixel_index = px & 1;
        if (s_gs4_nibble_swap) {
            pixel_index ^= 1;
        }
        int shift = pixel_index * 4;
        uint8_t mask = pixel_index == 0 ? 0xF0 : 0x0F;
        fb[byte_index] = (uint8_t)((fb[byte_index] & mask) | (color << shift));
    }
}

// Matches boards/inkplate10/inkplate10.py's write_fast_hline/write_fast_vline (a plain
// write_pixel loop, no pre-clip) -- the fast hline/vline that shared/gfx.py's GFX instance
// is actually constructed with on Inkplate10, not GFX's own _slow_hline/_slow_vline
// fallback (which Inkplate10 never uses).
void gfx_hline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int width, int color)
{
    for (int i = 0; i < width; i++) {
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + i, y0, color);
    }
}

void gfx_vline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int height, int color)
{
    for (int i = 0; i < height; i++) {
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0, y0 + i, color);
    }
}

// Bresenham, ported from shared/gfx.py GFX.line.
void gfx_line(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int x1, int y1, int color)
{
    int steep = (y1 > y0 ? y1 - y0 : y0 - y1) > (x1 > x0 ? x1 - x0 : x0 - x1);
    if (steep) {
        swap_int(&x0, &y0);
        swap_int(&x1, &y1);
    }
    if (x0 > x1) {
        swap_int(&x0, &x1);
        swap_int(&y0, &y1);
    }
    int dx = x1 - x0;
    int dy = y1 > y0 ? y1 - y0 : y0 - y1;
    int err = dx / 2; // dx >= 0 here, so truncation == floor
    int ystep = (y0 < y1) ? 1 : -1;

    while (x0 <= x1) {
        if (steep) {
            gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, y0, x0, color);
        } else {
            gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0, y0, color);
        }
        err -= dy;
        if (err < 0) {
            y0 += ystep;
            err += dx;
        }
        x0++;
    }
}

// Ported from shared/gfx.py GFX.rect. The early-return bounds check uses LOGICAL (post-
// rotation) width/height, derived here from phys_w/phys_h + rotation exactly like
// gfx_set_pixel's own bounds check.
void gfx_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int width, int height, int color)
{
    int logical_w = (rotation & 1) ? phys_h : phys_w;
    int logical_h = (rotation & 1) ? phys_w : phys_h;
    if (y0 < -height || y0 > logical_h || x0 < -width || x0 > logical_w) {
        return;
    }
    gfx_hline(fb, phys_w, phys_h, rotation, display_mode, x0, y0, width, color);
    gfx_hline(fb, phys_w, phys_h, rotation, display_mode, x0, y0 + height - 1, width, color);
    gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0, y0, height, color);
    gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + width - 1, y0, height, color);
}

// Matches boards/inkplate10/inkplate10.py's write_fill_rect (a plain write_pixel double
// loop), not shared/gfx.py GFX's own unused _fill_rect fallback.
void gfx_fill_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, int width, int height, int color)
{
    for (int j = 0; j < width; j++) {
        for (int i = 0; i < height; i++) {
            gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + j, y0 + i, color);
        }
    }
}

// Midpoint circle, ported from shared/gfx.py GFX.circle.
void gfx_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                int y0, int radius, int color)
{
    int f = 1 - radius;
    int ddf_x = 1;
    int ddf_y = -2 * radius;
    int x = 0;
    int y = radius;

    gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0, y0 + radius, color);
    gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0, y0 - radius, color);
    gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + radius, y0, color);
    gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - radius, y0, color);

    while (x < y) {
        if (f >= 0) {
            y--;
            ddf_y += 2;
            f += ddf_y;
        }
        x++;
        ddf_x += 2;
        f += ddf_x;

        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + x, y0 + y, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - x, y0 + y, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + x, y0 - y, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - x, y0 - y, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + y, y0 + x, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - y, y0 + x, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + y, y0 - x, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - y, y0 - x, color);
    }
}

// Ported from shared/gfx.py GFX.fill_circle (vline sweep, same midpoint stepping as
// gfx_circle).
void gfx_fill_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, int radius, int color)
{
    gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0, y0 - radius, 2 * radius + 1, color);

    int f = 1 - radius;
    int ddf_x = 1;
    int ddf_y = -2 * radius;
    int x = 0;
    int y = radius;

    while (x < y) {
        if (f >= 0) {
            y--;
            ddf_y += 2;
            f += ddf_y;
        }
        x++;
        ddf_x += 2;
        f += ddf_x;

        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + x, y0 - y, 2 * y + 1, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + y, y0 - x, 2 * x + 1, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 - x, y0 - y, 2 * y + 1, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 - y, y0 - x, 2 * x + 1, color);
    }
}

void gfx_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, int x1, int y1, int x2, int y2, int color)
{
    gfx_line(fb, phys_w, phys_h, rotation, display_mode, x0, y0, x1, y1, color);
    gfx_line(fb, phys_w, phys_h, rotation, display_mode, x1, y1, x2, y2, color);
    gfx_line(fb, phys_w, phys_h, rotation, display_mode, x2, y2, x0, y0, color);
}

// Scanline fill, ported from shared/gfx.py GFX.fill_triangle. Uses floordiv() (not C's `/`)
// to match Python's `//` -- dx01/dx02/dx12 can be negative once vertices are y-sorted but
// not x-sorted, and truncating division there would place edges off by one pixel.
void gfx_fill_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                       int x0, int y0, int x1, int y1, int x2, int y2, int color)
{
    if (y0 > y1) {
        swap_int(&y0, &y1);
        swap_int(&x0, &x1);
    }
    if (y1 > y2) {
        swap_int(&y2, &y1);
        swap_int(&x2, &x1);
    }
    if (y0 > y1) {
        swap_int(&y0, &y1);
        swap_int(&x0, &x1);
    }

    if (y0 == y2) {
        int a = x0, b = x0;
        if (x1 < a) {
            a = x1;
        } else if (x1 > b) {
            b = x1;
        }
        if (x2 < a) {
            a = x2;
        } else if (x2 > b) {
            b = x2;
        }
        gfx_hline(fb, phys_w, phys_h, rotation, display_mode, a, y0, b - a + 1, color);
        return;
    }

    int dx01 = x1 - x0, dy01 = y1 - y0;
    int dx02 = x2 - x0, dy02 = y2 - y0;
    int dx12 = x2 - x1, dy12 = y2 - y1;
    if (dy01 == 0) {
        dy01 = 1;
    }
    if (dy02 == 0) {
        dy02 = 1;
    }
    if (dy12 == 0) {
        dy12 = 1;
    }

    int sa = 0, sb = 0;
    int y = y0;
    int last = (y0 == y1) ? y1 - 1 : y1;
    for (; y <= last; y++) {
        int a = x0 + floordiv(sa, dy01);
        int b = x0 + floordiv(sb, dy02);
        sa += dx01;
        sb += dx02;
        if (a > b) {
            swap_int(&a, &b);
        }
        gfx_hline(fb, phys_w, phys_h, rotation, display_mode, a, y, b - a + 1, color);
    }

    sa = dx12 * (y - y1);
    sb = dx02 * (y - y0);
    for (; y <= y2; y++) {
        int a = x1 + floordiv(sa, dy12);
        int b = x0 + floordiv(sb, dy02);
        sa += dx12;
        sb += dx02;
        if (a > b) {
            swap_int(&a, &b);
        }
        gfx_hline(fb, phys_w, phys_h, rotation, display_mode, a, y, b - a + 1, color);
    }
}

// Ported from shared/gfx.py GFX.round_rect.
void gfx_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                    int y0, int width, int height, int radius, int color)
{
    x0 += radius;
    y0 += radius;
    radius = (int)min3d((double)radius, width / 2.0, height / 2.0);

    if (!radius) {
        return;
    }

    int f = 1 - radius;
    int ddf_x = 1;
    int ddf_y = -2 * radius;
    int x = 0;
    int y = radius;

    gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 - radius, y0,
              height - 2 * radius + 1, color);
    gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + width - radius, y0,
              height - 2 * radius + 1, color);
    gfx_hline(fb, phys_w, phys_h, rotation, display_mode, x0, y0 + height - radius + 1,
              width - 2 * radius + 1, color);
    gfx_hline(fb, phys_w, phys_h, rotation, display_mode, x0, y0 - radius, width - 2 * radius + 1,
              color);

    while (x < y) {
        if (f >= 0) {
            y--;
            ddf_y += 2;
            f += ddf_y;
        }
        x++;
        ddf_x += 2;
        f += ddf_x;

        // top left
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - y, y0 - x, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - x, y0 - y, color);
        // top right
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + x + width - 2 * radius,
                      y0 - y, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + y + width - 2 * radius,
                      y0 - x, color);
        // bottom right
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + y + width - 2 * radius,
                      y0 + x + height - 2 * radius, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + x + width - 2 * radius,
                      y0 + y + height - 2 * radius, color);
        // bottom left
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - x,
                      y0 + y + height - 2 * radius, color);
        gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 - y,
                      y0 + x + height - 2 * radius, color);
    }
}

// Ported from shared/gfx.py GFX.fill_round_rect.
void gfx_fill_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                         int x0, int y0, int width, int height, int radius, int color)
{
    x0 += radius;
    y0 += radius;
    radius = (int)min3d((double)radius, width / 2.0, height / 2.0);

    gfx_fill_rect(fb, phys_w, phys_h, rotation, display_mode, x0, y0 - radius,
                  width - 2 * radius + 2, height + 2, color);

    if (!radius) {
        return;
    }

    int f = 1 - radius;
    int ddf_x = 1;
    int ddf_y = -2 * radius;
    int x = 0;
    int y = radius;

    while (x < y) {
        if (f >= 0) {
            y--;
            ddf_y += 2;
            f += ddf_y;
        }
        x++;
        ddf_x += 2;
        f += ddf_x;

        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 - y, y0 - x,
                  2 * x + 1 + height - 2 * radius, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 - x, y0 - y,
                  2 * y + 1 + height - 2 * radius, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + x + width - 2 * radius, y0 - y,
                  2 * y + 1 + height - 2 * radius, color);
        gfx_vline(fb, phys_w, phys_h, rotation, display_mode, x0 + y + width - 2 * radius, y0 - x,
                  2 * x + 1 + height - 2 * radius, color);
    }
}

// Merges shared/gfx.py's _draw_char_1bpp/_draw_char_2bpp into one display_mode-dispatched
// blit (see gfx.h). Every accepted glyph sub-pixel goes through gfx_set_pixel, so the
// rotation remap + bounds clip + packing live in one place instead of being re-derived here
// -- the original two functions each carried their own copy of that math.
void gfx_draw_char(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, const uint8_t *char_data, int char_w, int char_h, int size, int color)
{
    static const uint8_t shift_mask[8] = {0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01};
    int row_bytes = (char_w + 7) / 8;

    for (int row = 0; row < char_h; row++) {
        int row_offset = row * row_bytes;
        for (int col = 0; col < char_w; col++) {
            int byte_idx = col / 8;
            int bit_mask = shift_mask[col % 8];
            int pixel_on = char_data[row_offset + byte_idx] & bit_mask;
            if (!pixel_on) {
                continue;
            }

            int x_base = x0 + col * size;
            int y_base = y0 + row * size;
            for (int sy = 0; sy < size; sy++) {
                for (int sx = 0; sx < size; sx++) {
                    gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x_base + sx,
                                  y_base + sy, color);
                }
            }
        }
    }
}

// Ports every board's own draw_bitmap Python loop (byte-walking + write_pixel per set bit)
// into one C call -- see docs/refactor_plan.md Phase 12 step 41.
void gfx_draw_bitmap(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, const uint8_t *bitmap, int bmp_w, int bmp_h, int color)
{
    int byte_width = (bmp_w + 7) / 8;
    for (int row = 0; row < bmp_h; row++) {
        uint8_t byte = 0;
        for (int col = 0; col < bmp_w; col++) {
            if (col & 7) {
                byte <<= 1;
            } else {
                byte = bitmap[row * byte_width + col / 8];
            }
            if (byte & 0x80) {
                gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + col, y0 + row,
                              color);
            }
        }
    }
}
