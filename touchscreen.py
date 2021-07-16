from micropython import const
from mcp23017 import MCP23017 as mcp
from mcp23017 import Pin 
from machine import Pin as mPin

import time

tsXResolution = 0
tsYResolution = 0

FRONTLIGHT_EN = 11

# Touchscreen defines
TOUCHSCREEN_EN = 12
TS_RTS = 10
TS_INT = 36
TS_ADDR = 0x15

_tsFlag = False

class Touchscreen:
    def tsInit(self, pwrState):
        Pin.value(TOUCHSCREEN_EN, 0)
        mcp.pin(mcp.mcp23017, TS_INT, mPin.IN, pull=mPin.PULL_UP)
        mcp.pin(mcp.mcp23017, TS_RTS, mode=mPin.OUT)
