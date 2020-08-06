#! /usr/bin/env python3
import sys, re

state = "outer"
name = "unknown"
data = bytearray()
for line in sys.stdin:
    if state == "outer" and line.startswith("/*"):
        state = "comment"
    elif state == "comment":
        if "*/" in line:
            state = "outer"
        elif "Fontname:" in line:
            fn = re.sub(r"\s*Fontname:\s*(\S+)\s*", r"\1", line)
            print(f"Font name: '{fn}'")
    elif state == "outer" and line.startswith("const uint8_t"):
        name = re.sub(r'.*"u8g2_font_([^"]*)".*\s*', r"\1", line) + ".u8f"
        print(f"Font filename: '{name}'")
        of = open(name, "wb")
        state = "data"
    elif state == "data" and line.startswith("  "):
        if line[-2] == ";":
            line = line[:-3] + '\\0"'  # patch bug in u8g2 library
            state = "outer"
        d = eval(line.replace('"', 'b"', 1))
        # print("Got:", d)
        of.write(d)
