# Manual HIL checklist

Repeatable smoke-test run by hand on real hardware, per board, per release.
Not automated (e-paper visual/bistable behavior can't be asserted in a host
test) — this catches what `run_ci.py test` structurally can't.

Not yet run against real hardware as of this doc's creation (docs/refactor_plan.md
Phase 12 step 37) — checklist authored ahead of first real pass; check off /
date each board's row only once actually flashed and eyeballed.

## Per-board checks

Parallel-bus mono/grayscale boards (Inkplate10 v1/v2, Inkplate6 v1/v2, 5v2,
6FLICK, 6PLUSv2, 4TEMPERA): clear/mono/grayscale/photo/partial all apply.

SPI color-panel boards (Inkplate2, 6COLOR, 13SPECTRA): palette-driven,
full-refresh-only — grayscale ramp and partial update are N/A.

6FLICK, 6PLUSv2, 4TEMPERA additionally have a touchscreen + frontlight
(Elan touch controller on PLUSv2/4TEMPERA, Cypress on 6FLICK) — extra columns,
N/A elsewhere.

| Board            | Clear | Mono text | Grayscale ramp | Photo (dithered) | Partial update | Touchscreen | Frontlight |
|-------------------|-------|-----------|----------------|------------------|-----------------|-------------|------------|
| Inkplate10v1      | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | N/A         | N/A        |
| Inkplate10v2      | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | N/A         | N/A        |
| Inkplate6v1       | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | N/A         | N/A        |
| Inkplate6v2       | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | N/A         | N/A        |
| Inkplate5v2       | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | N/A         | N/A        |
| Inkplate6FLICK    | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | [ ]         | [ ]        |
| Inkplate6PLUSv2   | [ ]   | [ ]       | [ ]            | [ ]              | [ ]             | [ ]         | [ ]        |
| Inkplate4TEMPERA  | [x]   | [x]       | [x]            | [x]              | [x]             | [x]         | [x]        |
| Inkplate2         | [ ]   | [ ]       | N/A            | [ ]              | N/A             | N/A         | N/A        |
| Inkplate6COLOR    | [ ]   | [ ]       | N/A            | [ ]              | N/A             | N/A         | N/A        |
| Inkplate13SPECTRA | [ ]   | [ ]       | N/A            | [ ]              | N/A             | N/A         | N/A        |

## Check definitions

- **Clear** — `display.clear()` (or equivalent), screen goes to blank white, no ghosting from prior content.
- **Mono text** — draw text, confirm crisp black-on-white, no missing/garbled glyphs.
- **Grayscale ramp** — draw all supported gray levels side by side, confirm each level visually distinct, no banding/reversal (see `mono_waveform_polarity_per_board` — a board's GS levels can come out inverted if LUT roles are wrong).
- **Photo (dithered)** — draw a real photo via `draw_jpg_from_sd`/`draw_png_from_sd`/`draw_bmp_from_sd`, confirm recognizable image, correct orientation/rotation.
- **Partial update** — change a small region, confirm only that region refreshes, fast, no visible flash/ghosting outside the changed area.
- **Touchscreen** — touch a known region, confirm `touch_in_area` reports the touch.
- **Frontlight** — `set_frontlight(True)`/`set_frontlight_brightness(v)`, confirm light turns on and brightness visibly changes.

## Failure log

Record failures here with date, board, firmware commit hash, and what was observed.

(none yet)
