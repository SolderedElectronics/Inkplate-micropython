#!/usr/bin/env python3
"""Self-discovering host build/test runner for firmware/usermods/inkplate.

Usage:
    run_ci.py build   -- compile every host-compilable .c file standalone (catches
                          syntax/type errors without needing the real xtensa toolchain)
    run_ci.py test    -- compile+link+run every tests/test_*.c against its real deps

`test`'s dependency resolution: a test file's own local #include "...X.h" lines seed a
set of required .c files, then each pulled-in .c file's own local #include "Y.h" lines
are followed transitively. Headers are matched by basename regardless of which
subfolder they live in or how the including file spells the path (plain, "../", or
subfolder-qualified) -- a new test/source pair needs no entry added here or in CI, and
sources may live in any subfolder under this directory.
"""

import re
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = SRC_DIR / "tests"

# These depend on ESP-IDF/MicroPython headers (py/runtime.h, driver/gpio.h, rom/tjpgd.h,
# esp_heap_caps.h, sdkconfig.h, miniz.h, ...) that don't exist for a host gcc -- they're
# only checked by the real firmware build + HIL, not host-compiled here.
HARDWARE_ONLY = {
    "epd_control.c",
    "epd_i2s.c",
    "epd_spi.c",
    "expander_bridge.c",
    "inkplatemodule.c",
    "jpeg_decode.c",
    "jpeg_draw.c",
    "png_decode.c",
    "png_draw.c",
    "pngle.c",
}

INCLUDE_RE = re.compile(r'#include\s*"([^"]+\.h)"')


def all_sources():
    """Every .c file under SRC_DIR, keyed by basename stem, excluding tests/."""
    return {p.stem: p for p in SRC_DIR.rglob("*.c") if TESTS_DIR not in p.parents}


def local_includes(path):
    """Basenames (no extension) of this file's own quoted local #includes."""
    return {Path(h).stem for h in INCLUDE_RE.findall(path.read_text())}


def resolve_deps(test_path, sources_by_stem):
    """Sources a test must be compiled+linked with, resolved from #include chains."""
    seen = set()
    deps = []
    frontier = list(local_includes(test_path))
    while frontier:
        stem = frontier.pop()
        if stem in seen:
            continue
        seen.add(stem)
        src = sources_by_stem.get(stem)
        if src is None:
            continue
        deps.append(src)
        frontier.extend(local_includes(src) - seen)
    return sorted(deps, key=lambda p: p.name)


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def cmd_build():
    sources = sorted(
        (p for p in all_sources().values() if p.name not in HARDWARE_ONLY),
        key=lambda p: p.name,
    )
    if not sources:
        sys.exit("no host-compilable sources found")
    for src in sources:
        run(
            [
                "gcc",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(SRC_DIR),
                "-c",
                str(src),
                "-o",
                "/dev/null",
            ]
        )
    print(f"build: {len(sources)} source(s) compiled clean")


def cmd_test():
    test_files = sorted(TESTS_DIR.glob("test_*.c"))
    if not test_files:
        sys.exit("no test_*.c files found")
    sources_by_stem = all_sources()
    for test_path in test_files:
        deps = resolve_deps(test_path, sources_by_stem)
        binary = f"/tmp/{test_path.stem}"
        run(
            [
                "gcc",
                "-Wall",
                "-Wextra",
                "-I",
                str(SRC_DIR),
                str(test_path),
                *[str(d) for d in deps],
                "-o",
                binary,
            ]
        )
        run([binary])
    print(f"test: {len(test_files)} test binaries passed")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("build", "test"):
        sys.exit(f"usage: {sys.argv[0]} build|test")
    {"build": cmd_build, "test": cmd_test}[sys.argv[1]]()
