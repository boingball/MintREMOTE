from __future__ import annotations

from pathlib import Path
import socket
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "viewer"))

from protocol import (  # noqa: E402
    CAP_INPUT,
    MSG_CAPABILITIES,
    MSG_FRAME_END,
    MSG_MOUSE_BUTTON,
    MSG_MOUSE_MOVE,
    MSG_PALETTE,
    MSG_TILE,
    MSG_RAW_KEY,
    MOUSE_LEFT,
    Tile,
    apply_planar_tile,
    apply_planar_tile_indices,
    encode_indexed_tile,
    pack_frame_end,
    pack_capabilities,
    pack_handshake,
    pack_palette,
    pack_mouse_button,
    pack_mouse_move,
    pack_raw_key,
    pack_tile,
    parse_frame_end,
    parse_button_or_key,
    parse_capabilities,
    parse_mouse_move,
    parse_palette,
    parse_tile,
    read_handshake,
    read_message,
)


class ProtocolTests(unittest.TestCase):
    def test_handshake_round_trip(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.sendall(pack_handshake(640, 256, 32, 16, 4))
        hello = read_handshake(right)
        self.assertEqual((hello.width, hello.height), (640, 256))
        self.assertEqual((hello.tile_width, hello.tile_height), (32, 16))
        self.assertEqual((hello.depth, hello.palette_entries), (4, 16))

    def test_message_round_trip(self) -> None:
        palette = [(0, 0, 0), (255, 255, 255)]
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.sendall(pack_palette(palette))
        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_PALETTE)
        self.assertEqual(parse_palette(payload), palette)

    def test_planar_encode_decode(self) -> None:
        width = 10
        height = 3
        depth = 2
        palette = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
        indices = [
            0, 1, 2, 3, 0, 1, 2, 3, 0, 1,
            3, 2, 1, 0, 3, 2, 1, 0, 3, 2,
            1, 1, 2, 2, 3, 3, 0, 0, 1, 2,
        ]
        tile = encode_indexed_tile(indices, width, 0, 0, width, height, depth, 7)
        framebuffer = bytearray(width * height * 3)
        apply_planar_tile(framebuffer, width, height, palette, tile)
        expected = b"".join(bytes(palette[index]) for index in indices)
        self.assertEqual(bytes(framebuffer), expected)

        index_buffer = bytearray(width * height)
        apply_planar_tile_indices(index_buffer, width, height, tile)
        self.assertEqual(list(index_buffer), indices)

    def test_tile_and_frame_messages(self) -> None:
        tile = Tile(9, 32, 16, 8, 1, 1, 1, b"\xaa")
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.sendall(pack_tile(tile) + pack_frame_end(9, 1, 12))

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_TILE)
        self.assertEqual(parse_tile(payload), tile)

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_FRAME_END)
        self.assertEqual(parse_frame_end(payload), (9, 1, 12))

    def test_capabilities_and_input_messages(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.sendall(
            pack_capabilities(CAP_INPUT)
            + pack_mouse_move(319, 199)
            + pack_mouse_button(MOUSE_LEFT, True)
            + pack_raw_key(0x20, True)
        )

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_CAPABILITIES)
        self.assertEqual(parse_capabilities(payload), CAP_INPUT)

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_MOUSE_MOVE)
        self.assertEqual(parse_mouse_move(payload), (319, 199))

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_MOUSE_BUTTON)
        self.assertEqual(parse_button_or_key(payload), (MOUSE_LEFT, True))

        msg_type, payload = read_message(right)
        self.assertEqual(msg_type, MSG_RAW_KEY)
        self.assertEqual(parse_button_or_key(payload), (0x20, True))


if __name__ == "__main__":
    unittest.main()
