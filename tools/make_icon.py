"""Generate amiga/MintRemoteServer.info, the Workbench tool icon.

The icon is a classic four-colour (OS 2/3 palette) DiskObject so it works on
every Workbench from 3.0 up. Its ToolTypes mirror the Shell template; INPUT is
parenthesised (disabled) by default, so double-clicking gives a view-only
server until the user edits the icon's Information.

Run: python tools/make_icon.py
"""

from __future__ import annotations

import struct
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "amiga" / "MintRemoteServer.info"

TOOL_TYPES = ("PORT=5909", "DELAY=5", "(INPUT)")
STACK_SIZE = 16384

WB_DISKMAGIC = 0xE310
WB_DISKVERSION = 1
WB_DISKREVISION = 1
WBTOOL = 3
NO_ICON_POSITION = 0x80000000

WIDTH, HEIGHT = 48, 26
GREY, BLACK, WHITE, BLUE = 0, 1, 2, 3


def _fill(canvas: list[list[int]], x0: int, y0: int, x1: int, y1: int,
          pen: int) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            canvas[y][x] = pen


def _image_rows() -> list[list[int]]:
    """A monitor showing a Workbench window, sending waves to the PC."""
    canvas = [[GREY] * WIDTH for _ in range(HEIGHT)]
    _fill(canvas, 1, 4, 30, 20, BLACK)       # monitor case
    _fill(canvas, 2, 5, 29, 19, WHITE)
    _fill(canvas, 4, 7, 27, 17, BLUE)        # Workbench screen
    _fill(canvas, 7, 9, 21, 15, BLACK)       # a window on it
    _fill(canvas, 8, 10, 20, 14, WHITE)
    _fill(canvas, 8, 10, 20, 10, BLUE)       # its title bar
    _fill(canvas, 12, 21, 19, 21, BLACK)     # stand
    _fill(canvas, 8, 22, 23, 24, BLACK)
    _fill(canvas, 9, 23, 22, 23, WHITE)
    cx, cy = 31.0, 11.5                      # waves leave the right edge
    for radius in (5, 9, 13):
        for y in range(HEIGHT):
            for x in range(32, WIDTH):
                dx, dy = x - cx, y - cy
                if abs(dy) <= dx * 0.85 and \
                        abs((dx * dx + dy * dy) ** 0.5 - radius) < 0.75:
                    canvas[y][x] = BLUE
    return canvas


def _image_planes(rows: list[list[int]]) -> bytes:
    width = len(rows[0])
    words = (width + 15) // 16
    data = bytearray()
    for plane in range(2):
        for row in rows:
            bits = 0
            for x in range(words * 16):
                pen = row[x] if x < width else GREY
                bits = (bits << 1) | ((pen >> plane) & 1)
            data += bits.to_bytes(words * 2, "big")
    return bytes(data)


def _string(text: str) -> bytes:
    raw = text.encode("latin-1") + b"\0"
    return struct.pack(">L", len(raw)) + raw


def build_icon() -> bytes:
    rows = _image_rows()
    width, height = len(rows[0]), len(rows)

    gadget = struct.pack(
        ">LhhhhHHHLLLlLHL",
        0,                 # NextGadget
        0, 0,              # LeftEdge, TopEdge
        width, height + 1,  # Width, Height (+1 is the Workbench convention)
        0x0005,            # GFLG_GADGIMAGE | GFLG_GADGBACKFILL
        0x0003,            # GACT_RELVERIFY | GACT_IMMEDIATE
        0x0001,            # GTYP_BOOLGADGET
        1,                 # GadgetRender: image follows
        0,                 # SelectRender: complement highlight
        0, 0, 0,           # GadgetText, MutualExclude, SpecialInfo
        0,                 # GadgetID
        WB_DISKREVISION,   # UserData holds the icon revision
    )
    disk_object = (
        struct.pack(">HH", WB_DISKMAGIC, WB_DISKVERSION)
        + gadget
        + struct.pack(
            ">BBLLLLLLL",
            WBTOOL, 0,
            0,             # DefaultTool
            1,             # ToolTypes follow
            NO_ICON_POSITION, NO_ICON_POSITION,
            0,             # DrawerData
            0,             # ToolWindow
            STACK_SIZE,
        )
    )
    assert len(disk_object) == 78

    image = struct.pack(">hhhhhLBBL", 0, 0, width, height, 2, 1, 3, 0, 0)
    assert len(image) == 20

    tool_types = struct.pack(">L", 4 * (len(TOOL_TYPES) + 1))
    for entry in TOOL_TYPES:
        tool_types += _string(entry)

    return disk_object + image + _image_planes(rows) + tool_types


def main() -> None:
    OUTPUT.write_bytes(build_icon())
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
