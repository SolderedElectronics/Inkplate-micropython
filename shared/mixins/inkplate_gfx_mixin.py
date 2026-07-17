"""Shared pixel/shape drawing primitives for the GS4-framebuffer Inkplate boards
(Inkplate10/6/6PLUSV2/6FLICK/5V2/4TEMPERA).

Host class contract -- must provide before any of these are called:
    self._d_cols, self._d_rows   native (unrotated) panel dimensions
    self.rotation                 0-3, current rotation
    self.display_mode             0 (mono) or 1 (GS), passed straight to gfx_* calls
    self._framebuf()              method returning the active bytearray for display_mode
    self.width(), self.height()   current (rotation-aware) dimensions
"""

import inkplate


class GfxMixin:
    def draw_pixel(self, x, y, c):
        self.start_write()
        self.write_pixel(x, y, c)
        self.end_write()

    def start_write(self):
        pass

    def write_pixel(self, x, y, c):
        inkplate.gfx_set_pixel(
            self._framebuf(), self._d_cols, self._d_rows, self.rotation, self.display_mode, x, y, c
        )

    def draw_bitmap(self, x, y, data, w, h, c=1):
        inkplate.gfx_draw_bitmap(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            data,
            w,
            h,
            c,
        )

    def write_fill_rect(self, x, y, w, h, c):
        inkplate.gfx_fill_rect(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            w,
            h,
            c,
        )

    def write_fast_vline(self, x, y, h, c):
        inkplate.gfx_vline(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            h,
            c,
        )

    def write_fast_hline(self, x, y, w, c):
        inkplate.gfx_hline(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            w,
            c,
        )

    def write_line(self, x0, y0, x1, y1, c):
        inkplate.gfx_line(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            x1,
            y1,
            c,
        )

    def end_write(self):
        pass

    def draw_fast_vline(self, x, y, h, c):
        self.start_write()
        self.write_fast_vline(x, y, h, c)
        self.end_write()

    def draw_fast_hline(self, x, y, w, c):
        self.start_write()
        self.write_fast_hline(x, y, w, c)
        self.end_write()

    def fill_rect(self, x, y, w, h, c):
        self.start_write()
        self.write_fill_rect(x, y, w, h, c)
        self.end_write()

    def fill_screen(self, c):
        self.fill_rect(0, 0, self.width(), self.height(), c)

    def draw_line(self, x0, y0, x1, y1, c):
        self.start_write()
        self.write_line(x0, y0, x1, y1, c)
        self.end_write()

    def draw_rect(self, x, y, w, h, c):
        inkplate.gfx_rect(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            w,
            h,
            c,
        )

    def draw_circle(self, x, y, r, c):
        inkplate.gfx_circle(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            r,
            c,
        )

    def fill_circle(self, x, y, r, c):
        inkplate.gfx_fill_circle(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            r,
            c,
        )

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_triangle(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            c,
        )

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        inkplate.gfx_fill_triangle(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x0,
            y0,
            x1,
            y1,
            x2,
            y2,
            c,
        )

    def draw_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_round_rect(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            q,
            h,
            r,
            c,
        )

    def fill_round_rect(self, x, y, q, h, r, c):
        inkplate.gfx_fill_round_rect(
            self._framebuf(),
            self._d_cols,
            self._d_rows,
            self.rotation,
            self.display_mode,
            x,
            y,
            q,
            h,
            r,
            c,
        )

    def set_display_mode(self, mode):
        self.display_mode = mode

    def get_display_mode(self):
        return self.display_mode
