"""Draw various shapes in different colors across the full 1600x1200 canvas."""

from inkplate13_spectra import Inkplate

inkplate = Inkplate()
inkplate.begin()
inkplate.clear_display()
inkplate.display()

inkplate.draw_pixel(800, 600, inkplate.BLACK)

inkplate.draw_rect(60, 60, 1480, 1080, inkplate.BLACK)
inkplate.draw_rect(80, 80, 1440, 1040, inkplate.BLUE)
inkplate.draw_round_rect(110, 110, 1380, 980, 40, inkplate.YELLOW)

inkplate.draw_line(60, 60, 1540, 1140, inkplate.BLACK)
inkplate.draw_line(1540, 60, 60, 1140, inkplate.BLACK)

inkplate.draw_fast_hline(60, 600, 1480, inkplate.RED)
inkplate.draw_fast_vline(800, 60, 1080, inkplate.GREEN)

inkplate.draw_circle(400, 300, 120, inkplate.BLUE)
inkplate.fill_circle(1200, 300, 120, inkplate.GREEN)
inkplate.draw_circle(1200, 300, 120, inkplate.BLACK)

inkplate.fill_round_rect(220, 760, 420, 300, 35, inkplate.YELLOW)
inkplate.draw_round_rect(220, 760, 420, 300, 35, inkplate.BLACK)

inkplate.fill_rect(980, 760, 420, 300, inkplate.WHITE)
inkplate.draw_rect(980, 760, 420, 300, inkplate.BLACK)

inkplate.draw_triangle(800, 140, 680, 360, 920, 360, inkplate.RED)
inkplate.fill_triangle(800, 520, 650, 720, 950, 720, inkplate.BLUE)
inkplate.draw_triangle(800, 520, 650, 720, 950, 720, inkplate.BLACK)

inkplate.draw_fast_hline(200, 180, 1200, inkplate.YELLOW)
inkplate.draw_fast_hline(200, 1020, 1200, inkplate.YELLOW)
inkplate.draw_fast_vline(220, 200, 800, inkplate.BLUE)
inkplate.draw_fast_vline(1380, 200, 800, inkplate.BLUE)

inkplate.fill_circle(100, 100, 18, inkplate.RED)
inkplate.fill_circle(1500, 100, 18, inkplate.GREEN)
inkplate.fill_circle(100, 1100, 18, inkplate.BLUE)
inkplate.fill_circle(1500, 1100, 18, inkplate.BLACK)

inkplate.draw_rect(50, 50, 75, 75, inkplate.BLUE)
inkplate.draw_circle(200, 200, 30, inkplate.GREEN)
inkplate.fill_circle(300, 300, 30, inkplate.BLACK)
inkplate.draw_fast_hline(20, 100, 50, inkplate.RED)
inkplate.draw_fast_vline(100, 20, 50, inkplate.BLACK)
inkplate.draw_line(100, 100, 400, 400, inkplate.BLACK)
inkplate.draw_round_rect(100, 10, 100, 100, 10, inkplate.YELLOW)
inkplate.fill_round_rect(10, 100, 100, 100, 10, inkplate.BLACK)
inkplate.draw_triangle(300, 100, 400, 150, 400, 100, inkplate.BLACK)


inkplate.display()
