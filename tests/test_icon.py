"""The committed Workbench icon is a valid tool DiskObject with ToolTypes."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_icon  # noqa: E402


class IconTests(unittest.TestCase):
    def setUp(self):
        self.data = (ROOT / "amiga" / "MintRemoteServer.info").read_bytes()

    def test_committed_icon_matches_generator(self):
        self.assertEqual(self.data, make_icon.build_icon())

    def test_tool_disk_object_layout(self):
        data = self.data
        magic, version = struct.unpack_from(">HH", data, 0)
        self.assertEqual((magic, version), (0xE310, 1))
        # struct Gadget starts at 4: NextGadget, Left, Top, Width, Height...
        width, height, flags = struct.unpack_from(">hhH", data, 12)
        gadget_render, select_render = struct.unpack_from(">LL", data, 22)
        self.assertNotEqual(gadget_render, 0)
        self.assertEqual(select_render, 0)
        self.assertEqual(flags & 0x0004, 0x0004)  # GFLG_GADGIMAGE
        do_type = data[48]
        default_tool, tool_types, x, y, drawer, window, stack = \
            struct.unpack_from(">LLLLLLL", data, 50)
        self.assertEqual(do_type, 3)  # WBTOOL
        self.assertEqual((default_tool, drawer, window), (0, 0, 0))
        self.assertEqual((x, y), (0x80000000, 0x80000000))
        self.assertGreaterEqual(stack, 8192)
        self.assertNotEqual(tool_types, 0)

        offset = 78
        _, _, image_width, image_height, depth = \
            struct.unpack_from(">hhhhh", data, offset)
        image_data, plane_pick, _, next_image = \
            struct.unpack_from(">LBBL", data, offset + 10)
        self.assertEqual((image_width, image_height + 1), (width, height))
        self.assertEqual((depth, plane_pick, next_image), (2, 3, 0))
        self.assertNotEqual(image_data, 0)
        offset += 20 + ((image_width + 15) // 16) * 2 * image_height * depth

        table_bytes, = struct.unpack_from(">L", data, offset)
        offset += 4
        entries = []
        for _ in range(table_bytes // 4 - 1):
            length, = struct.unpack_from(">L", data, offset)
            raw = data[offset + 4:offset + 4 + length]
            self.assertEqual(raw[-1:], b"\0")
            entries.append(raw[:-1].decode("latin-1"))
            offset += 4 + length
        self.assertEqual(offset, len(data))
        self.assertEqual(entries, ["PORT=5909", "DELAY=5", "(INPUT)"])


if __name__ == "__main__":
    unittest.main()
