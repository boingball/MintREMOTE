"""Animated MintREMOTE protocol source for testing the Python viewer."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "viewer"))

from protocol import (  # noqa: E402
    encode_indexed_tile,
    pack_frame_end,
    pack_handshake,
    pack_palette,
    pack_tile,
)

WIDTH = 320
HEIGHT = 200
TILE_WIDTH = 32
TILE_HEIGHT = 16
DEPTH = 4

PALETTE = [
    (0x00, 0x00, 0x00),
    (0xFF, 0xFF, 0xFF),
    (0x00, 0x55, 0xAA),
    (0x66, 0xAA, 0xFF),
    (0xFF, 0x88, 0x00),
    (0xFF, 0xCC, 0x66),
    (0x44, 0x44, 0x44),
    (0x88, 0x88, 0x88),
] + [(0, 0, 0)] * 8


def make_frame(frame_id: int) -> list[int]:
    pixels = [2] * (WIDTH * HEIGHT)
    for y in range(12, HEIGHT - 12):
        for x in range(12, WIDTH - 12):
            pixels[y * WIDTH + x] = 3 if ((x // 16 + y // 16) & 1) else 1
    box_x = 18 + (frame_id * 4) % (WIDTH - 68)
    for y in range(75, 125):
        for x in range(box_x, box_x + 50):
            pixels[y * WIDTH + x] = 4 if (x + y) & 1 else 5
    return pixels


def serve(client: socket.socket, fps: float) -> None:
    client.sendall(pack_handshake(WIDTH, HEIGHT, TILE_WIDTH, TILE_HEIGHT, DEPTH))
    client.sendall(pack_palette(PALETTE))
    previous: dict[tuple[int, int], bytes] = {}
    frame_id = 1
    while True:
        indices = make_frame(frame_id)
        changed = 0
        for y in range(0, HEIGHT, TILE_HEIGHT):
            for x in range(0, WIDTH, TILE_WIDTH):
                width = min(TILE_WIDTH, WIDTH - x)
                height = min(TILE_HEIGHT, HEIGHT - y)
                tile = encode_indexed_tile(
                    indices, WIDTH, x, y, width, height, DEPTH, frame_id
                )
                if previous.get((x, y)) != tile.data:
                    client.sendall(pack_tile(tile))
                    previous[(x, y)] = tile.data
                    changed += 1
        client.sendall(pack_frame_end(frame_id, changed))
        frame_id += 1
        time.sleep(1.0 / fps)


def main() -> None:
    parser = argparse.ArgumentParser(description="MintREMOTE PR1 mock server")
    parser.add_argument("--port", type=int, default=5909)
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", args.port))
        server.listen(1)
        print(f"Mock server waiting on 127.0.0.1:{args.port}")
        client, address = server.accept()
        with client:
            print(f"Viewer connected from {address[0]}:{address[1]}")
            try:
                serve(client, args.fps)
            except (BrokenPipeError, ConnectionResetError):
                print("Viewer disconnected")


if __name__ == "__main__":
    main()

