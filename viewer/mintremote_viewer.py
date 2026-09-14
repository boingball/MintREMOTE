"""Simple Tk/Pillow viewer for the MintREMOTE PR1 prototype."""

from __future__ import annotations

import argparse
import queue
import socket
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from protocol import (
    MSG_FRAME_END,
    MSG_GOODBYE,
    MSG_PALETTE,
    MSG_TILE,
    apply_planar_tile_indices,
    parse_frame_end,
    parse_palette,
    parse_tile,
    read_handshake,
    read_message,
)


class MintRemoteViewer:
    def __init__(self, host: str, port: int, scale: int) -> None:
        self.host = host
        self.port = port
        self.scale = scale
        self.root = tk.Tk()
        self.root.title("MintREMOTE PR1")
        self.status = tk.StringVar(value=f"Connecting to {host}:{port}...")
        self.image_label = ttk.Label(self.root)
        self.image_label.pack(padx=8, pady=8)
        ttk.Label(self.root, textvariable=self.status).pack(fill="x", padx=8, pady=(0, 8))
        self.events: queue.Queue[tuple] = queue.Queue(maxsize=2)
        self.stop = threading.Event()
        self.sock: socket.socket | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        threading.Thread(target=self.network_worker, daemon=True).start()
        self.root.after(15, self.poll_events)
        self.root.mainloop()

    def publish(self, event: tuple) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait(event)

    def network_worker(self) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=10) as sock:
                self.sock = sock
                sock.settimeout(None)
                hello = read_handshake(sock)
                palette = [(0, 0, 0)] * hello.palette_entries
                framebuffer = bytearray(hello.width * hello.height)
                self.publish(("connected", hello))

                while not self.stop.is_set():
                    msg_type, payload = read_message(sock)
                    if msg_type == MSG_PALETTE:
                        new_palette = parse_palette(payload)
                        if len(new_palette) != hello.palette_entries:
                            raise ValueError("server changed palette size")
                        palette = new_palette
                    elif msg_type == MSG_TILE:
                        tile = parse_tile(payload)
                        apply_planar_tile_indices(
                            framebuffer, hello.width, hello.height, tile
                        )
                    elif msg_type == MSG_FRAME_END:
                        frame_id, changed_tiles, scan_ms = parse_frame_end(payload)
                        self.publish(
                            (
                                "frame",
                                hello.width,
                                hello.height,
                                bytes(framebuffer),
                                tuple(palette),
                                frame_id,
                                changed_tiles,
                                scan_ms,
                            )
                        )
                    elif msg_type == MSG_GOODBYE:
                        break
                    else:
                        raise ValueError(f"unknown message type {msg_type}")
        except Exception as exc:  # displayed in the UI, including disconnects
            if not self.stop.is_set():
                self.publish(("error", str(exc)))
        finally:
            self.sock = None

    def poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "connected":
                    hello = event[1]
                    self.status.set(
                        f"Connected: {hello.width}x{hello.height}, "
                        f"{hello.depth} bitplanes"
                    )
                elif event[0] == "frame":
                    _, width, height, pixels, palette, frame_id, changed, scan_ms = event
                    image = Image.frombytes("P", (width, height), pixels)
                    flat_palette = [component for colour in palette for component in colour]
                    flat_palette.extend([0] * (768 - len(flat_palette)))
                    image.putpalette(flat_palette)
                    if self.scale != 1:
                        image = image.resize(
                            (width * self.scale, height * self.scale),
                            Image.Resampling.NEAREST,
                        )
                    self.photo = ImageTk.PhotoImage(image)
                    self.image_label.configure(image=self.photo)
                    timing = f", scan {scan_ms} ms" if scan_ms else ""
                    self.status.set(
                        f"Frame {frame_id}: {changed} changed tiles{timing}"
                    )
                elif event[0] == "error":
                    self.status.set(f"Disconnected: {event[1]}")
        except queue.Empty:
            pass
        if not self.stop.is_set():
            self.root.after(15, self.poll_events)

    def close(self) -> None:
        self.stop.set()
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="View a MintREMOTE PR1 stream")
    parser.add_argument("host", help="Amiga IP address")
    parser.add_argument("--port", type=int, default=5909)
    parser.add_argument("--scale", type=int, choices=(1, 2, 3, 4), default=1)
    args = parser.parse_args()
    MintRemoteViewer(args.host, args.port, args.scale).run()


if __name__ == "__main__":
    main()
