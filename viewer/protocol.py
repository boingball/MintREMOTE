"""MintREMOTE wire protocol, input packets and planar conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import socket
import struct
from typing import Sequence

MAGIC = b"MRM1"
VERSION = 2
PIXEL_PLANAR_INDEXED = 1

MSG_PALETTE = 1
MSG_TILE = 2
MSG_FRAME_END = 3
MSG_GOODBYE = 4
MSG_CAPABILITIES = 5

MSG_MOUSE_MOVE = 128
MSG_MOUSE_BUTTON = 129
MSG_RAW_KEY = 130

CAP_INPUT = 1

MOUSE_LEFT = 1
MOUSE_MIDDLE = 2
MOUSE_RIGHT = 3

HANDSHAKE = struct.Struct(">4s8H")
MESSAGE_HEADER = struct.Struct(">BBH")
TILE_HEADER = struct.Struct(">I5H2B")
FRAME_END = struct.Struct(">IHH")
CAPABILITIES = struct.Struct(">H")
MOUSE_MOVE = struct.Struct(">HH")
BUTTON_OR_KEY = struct.Struct(">BB")


@dataclass(frozen=True)
class Handshake:
    width: int
    height: int
    tile_width: int
    tile_height: int
    depth: int
    pixel_format: int
    palette_entries: int


@dataclass(frozen=True)
class Tile:
    frame_id: int
    x: int
    y: int
    width: int
    height: int
    row_bytes: int
    depth: int
    data: bytes


def recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_handshake(sock: socket.socket) -> Handshake:
    magic, version, width, height, tw, th, depth, pixel_format, entries = (
        HANDSHAKE.unpack(recv_exact(sock, HANDSHAKE.size))
    )
    if magic != MAGIC:
        raise ValueError(f"not a MintREMOTE stream: {magic!r}")
    if version != VERSION:
        raise ValueError(f"unsupported protocol version {version}")
    if pixel_format != PIXEL_PLANAR_INDEXED:
        raise ValueError(f"unsupported pixel format {pixel_format}")
    if not (1 <= depth <= 8 and entries == 1 << depth):
        raise ValueError("invalid planar depth/palette declaration")
    return Handshake(width, height, tw, th, depth, pixel_format, entries)


def read_message(sock: socket.socket) -> tuple[int, bytes]:
    msg_type, flags, payload_length = MESSAGE_HEADER.unpack(
        recv_exact(sock, MESSAGE_HEADER.size)
    )
    if flags != 0:
        raise ValueError(f"unsupported message flags 0x{flags:02x}")
    return msg_type, recv_exact(sock, payload_length)


def parse_palette(payload: bytes) -> list[tuple[int, int, int]]:
    if len(payload) < 2:
        raise ValueError("short palette message")
    count = struct.unpack_from(">H", payload)[0]
    if len(payload) != 2 + count * 3:
        raise ValueError("palette message length mismatch")
    return [tuple(payload[2 + i * 3 : 5 + i * 3]) for i in range(count)]


def parse_tile(payload: bytes) -> Tile:
    if len(payload) < TILE_HEADER.size:
        raise ValueError("short tile message")
    values = TILE_HEADER.unpack_from(payload)
    frame_id, x, y, width, height, row_bytes, depth, reserved = values
    if reserved != 0:
        raise ValueError("unsupported tile flags")
    data = payload[TILE_HEADER.size :]
    if len(data) != row_bytes * height * depth:
        raise ValueError("tile planar data length mismatch")
    return Tile(frame_id, x, y, width, height, row_bytes, depth, data)


def parse_frame_end(payload: bytes) -> tuple[int, int, int]:
    if len(payload) != FRAME_END.size:
        raise ValueError("invalid frame-end message")
    return FRAME_END.unpack(payload)


def parse_capabilities(payload: bytes) -> int:
    if len(payload) != CAPABILITIES.size:
        raise ValueError("invalid capabilities message")
    return CAPABILITIES.unpack(payload)[0]


def parse_mouse_move(payload: bytes) -> tuple[int, int]:
    if len(payload) != MOUSE_MOVE.size:
        raise ValueError("invalid mouse-move message")
    return MOUSE_MOVE.unpack(payload)


def parse_button_or_key(payload: bytes) -> tuple[int, bool]:
    if len(payload) != BUTTON_OR_KEY.size:
        raise ValueError("invalid button/key message")
    code, down = BUTTON_OR_KEY.unpack(payload)
    if down not in (0, 1):
        raise ValueError("invalid button/key state")
    return code, bool(down)


def apply_planar_tile(
    framebuffer: bytearray,
    screen_width: int,
    screen_height: int,
    palette: Sequence[tuple[int, int, int]],
    tile: Tile,
) -> None:
    if tile.x + tile.width > screen_width or tile.y + tile.height > screen_height:
        raise ValueError("tile lies outside framebuffer")
    if tile.depth < 1 or tile.depth > 8:
        raise ValueError("unsupported tile depth")

    plane_stride = tile.row_bytes * tile.height
    for row in range(tile.height):
        for column in range(tile.width):
            byte_number = row * tile.row_bytes + (column >> 3)
            mask = 0x80 >> (column & 7)
            colour = 0
            for plane in range(tile.depth):
                if tile.data[plane * plane_stride + byte_number] & mask:
                    colour |= 1 << plane
            if colour >= len(palette):
                raise ValueError("tile references missing palette entry")
            target = ((tile.y + row) * screen_width + tile.x + column) * 3
            framebuffer[target : target + 3] = bytes(palette[colour])


def apply_planar_tile_indices(
    framebuffer: bytearray,
    screen_width: int,
    screen_height: int,
    tile: Tile,
) -> None:
    """Apply a tile to an 8-bit palette-index framebuffer.

    Keeping indices rather than resolved RGB values means a later palette
    message immediately recolours unchanged pixels, as real Amiga hardware
    does, without forcing the server to resend every tile.
    """
    if tile.x + tile.width > screen_width or tile.y + tile.height > screen_height:
        raise ValueError("tile lies outside framebuffer")
    if tile.depth < 1 or tile.depth > 8:
        raise ValueError("unsupported tile depth")

    plane_stride = tile.row_bytes * tile.height
    for row in range(tile.height):
        for column in range(tile.width):
            byte_number = row * tile.row_bytes + (column >> 3)
            mask = 0x80 >> (column & 7)
            colour = 0
            for plane in range(tile.depth):
                if tile.data[plane * plane_stride + byte_number] & mask:
                    colour |= 1 << plane
            framebuffer[(tile.y + row) * screen_width + tile.x + column] = colour


def pack_message(msg_type: int, payload: bytes) -> bytes:
    if len(payload) > 65535:
        raise ValueError("message is too large")
    return MESSAGE_HEADER.pack(msg_type, 0, len(payload)) + payload


def pack_handshake(
    width: int, height: int, tile_width: int, tile_height: int, depth: int
) -> bytes:
    return HANDSHAKE.pack(
        MAGIC,
        VERSION,
        width,
        height,
        tile_width,
        tile_height,
        depth,
        PIXEL_PLANAR_INDEXED,
        1 << depth,
    )


def pack_palette(palette: Sequence[tuple[int, int, int]]) -> bytes:
    raw = b"".join(bytes(colour) for colour in palette)
    return pack_message(MSG_PALETTE, struct.pack(">H", len(palette)) + raw)


def pack_tile(tile: Tile) -> bytes:
    payload = TILE_HEADER.pack(
        tile.frame_id,
        tile.x,
        tile.y,
        tile.width,
        tile.height,
        tile.row_bytes,
        tile.depth,
        0,
    ) + tile.data
    return pack_message(MSG_TILE, payload)


def pack_frame_end(frame_id: int, changed_tiles: int, scan_ms: int = 0) -> bytes:
    return pack_message(MSG_FRAME_END, FRAME_END.pack(frame_id, changed_tiles, scan_ms))


def pack_capabilities(capabilities: int) -> bytes:
    return pack_message(MSG_CAPABILITIES, CAPABILITIES.pack(capabilities))


def pack_mouse_move(x: int, y: int) -> bytes:
    if not (0 <= x <= 65535 and 0 <= y <= 65535):
        raise ValueError("mouse position is outside the protocol range")
    return pack_message(MSG_MOUSE_MOVE, MOUSE_MOVE.pack(x, y))


def pack_mouse_button(button: int, down: bool) -> bytes:
    if button not in (MOUSE_LEFT, MOUSE_MIDDLE, MOUSE_RIGHT):
        raise ValueError("unknown mouse button")
    return pack_message(MSG_MOUSE_BUTTON, BUTTON_OR_KEY.pack(button, int(down)))


def pack_raw_key(raw_key: int, down: bool) -> bytes:
    if not 0 <= raw_key < 128:
        raise ValueError("raw key must be in the range 0-127")
    return pack_message(MSG_RAW_KEY, BUTTON_OR_KEY.pack(raw_key, int(down)))


def encode_indexed_tile(
    indices: Sequence[int],
    screen_width: int,
    x: int,
    y: int,
    width: int,
    height: int,
    depth: int,
    frame_id: int,
) -> Tile:
    row_bytes = (width + 7) // 8
    plane_stride = row_bytes * height
    data = bytearray(plane_stride * depth)
    for row in range(height):
        for column in range(width):
            colour = indices[(y + row) * screen_width + x + column]
            mask = 0x80 >> (column & 7)
            byte_number = row * row_bytes + (column >> 3)
            for plane in range(depth):
                if colour & (1 << plane):
                    data[plane * plane_stride + byte_number] |= mask
    return Tile(frame_id, x, y, width, height, row_bytes, depth, bytes(data))
