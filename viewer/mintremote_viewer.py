"""Tk/Pillow MintREMOTE viewer with Amiga mouse and raw-key input."""

from __future__ import annotations

import argparse
import queue
import socket
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from protocol import (
    CAP_INPUT,
    MSG_CAPABILITIES,
    MSG_FRAME_END,
    MSG_GOODBYE,
    MSG_PALETTE,
    MSG_TILE,
    MOUSE_LEFT,
    MOUSE_MIDDLE,
    MOUSE_RIGHT,
    apply_planar_tile_indices,
    pack_mouse_button,
    pack_mouse_move,
    pack_raw_key,
    parse_capabilities,
    parse_frame_end,
    parse_palette,
    parse_tile,
    read_handshake,
    read_message,
)


# Amiga raw key codes describe physical keys. This covers the standard
# Workbench/CLI keys on a US/UK PC keyboard without asking the 68k to translate
# Unicode or maintain a second keymap.
RAW_KEYS = {
    "grave": 0x00,
    "1": 0x01, "2": 0x02, "3": 0x03, "4": 0x04, "5": 0x05,
    "6": 0x06, "7": 0x07, "8": 0x08, "9": 0x09, "0": 0x0A,
    "exclam": 0x01, "at": 0x02, "numbersign": 0x03, "dollar": 0x04,
    "percent": 0x05, "asciicircum": 0x06, "ampersand": 0x07,
    "asterisk": 0x08, "parenleft": 0x09, "parenright": 0x0A,
    "minus": 0x0B, "equal": 0x0C, "backslash": 0x0D,
    "underscore": 0x0B, "plus": 0x0C, "bar": 0x0D,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "bracketleft": 0x1A, "bracketright": 0x1B,
    "braceleft": 0x1A, "braceright": 0x1B,
    "a": 0x20, "s": 0x21, "d": 0x22, "f": 0x23, "g": 0x24,
    "h": 0x25, "j": 0x26, "k": 0x27, "l": 0x28,
    "semicolon": 0x29, "apostrophe": 0x2A,
    "colon": 0x29, "quotedbl": 0x2A,
    "z": 0x31, "x": 0x32, "c": 0x33, "v": 0x34,
    "b": 0x35, "n": 0x36, "m": 0x37, "comma": 0x38,
    "period": 0x39, "slash": 0x3A,
    "less": 0x38, "greater": 0x39, "question": 0x3A,
    "space": 0x40, "backspace": 0x41, "tab": 0x42,
    "return": 0x44, "escape": 0x45, "delete": 0x46,
    "up": 0x4C, "down": 0x4D, "right": 0x4E, "left": 0x4F,
    "f1": 0x50, "f2": 0x51, "f3": 0x52, "f4": 0x53, "f5": 0x54,
    "f6": 0x55, "f7": 0x56, "f8": 0x57, "f9": 0x58, "f10": 0x59,
    "help": 0x5F, "shift_l": 0x60, "shift_r": 0x61,
    "caps_lock": 0x62, "control_l": 0x63, "control_r": 0x63,
    "alt_l": 0x64, "alt_r": 0x65,
    "meta_l": 0x66, "super_l": 0x66, "win_l": 0x66,
    "meta_r": 0x67, "super_r": 0x67, "win_r": 0x67,
}

TK_MOUSE_BUTTONS = {1: MOUSE_LEFT, 2: MOUSE_MIDDLE, 3: MOUSE_RIGHT}


class MintRemoteViewer:
    def __init__(self, host: str, port: int, scale: int) -> None:
        self.host = host
        self.port = port
        self.scale = scale
        self.root = tk.Tk()
        self.root.title("MintREMOTE PR2")
        self.status = tk.StringVar(value=f"Connecting to {host}:{port}...")
        self.image_label = ttk.Label(self.root, takefocus=True)
        self.image_label.pack(padx=8, pady=8)
        ttk.Label(self.root, textvariable=self.status).pack(fill="x", padx=8, pady=(0, 8))
        self.events: queue.Queue[tuple] = queue.Queue(maxsize=4)
        self.stop = threading.Event()
        self.sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.photo: ImageTk.PhotoImage | None = None
        self.remote_width = 0
        self.remote_height = 0
        self.input_enabled = False
        self.pressed_keys: set[int] = set()
        self.pressed_buttons: set[int] = set()
        self.pending_mouse: tuple[int, int] | None = None
        self.mouse_send_after: str | None = None
        self.image_label.bind("<Motion>", self.mouse_move)
        self.image_label.bind("<ButtonPress>", self.mouse_button_down)
        self.image_label.bind("<KeyPress>", self.key_down)
        self.image_label.bind("<KeyRelease>", self.key_up)
        self.image_label.bind("<FocusOut>", self.release_all_input)
        # A local grab keeps a drag routed to the display, while bind_all is a
        # final safety net for a release delivered after the event target moves.
        self.root.bind_all("<ButtonRelease>", self.mouse_button_up, add="+")
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
                    elif msg_type == MSG_CAPABILITIES:
                        self.publish(("capabilities", parse_capabilities(payload)))
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
                    self.remote_width = hello.width
                    self.remote_height = hello.height
                    self.status.set(
                        f"Connected: {hello.width}x{hello.height}, "
                        f"{hello.depth} bitplanes"
                    )
                elif event[0] == "capabilities":
                    self.input_enabled = bool(event[1] & CAP_INPUT)
                    if self.input_enabled:
                        self.status.set("Connected: input enabled; click the Amiga screen")
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
                        + ("; input enabled" if self.input_enabled else "; view-only")
                    )
                elif event[0] == "error":
                    self.status.set(f"Disconnected: {event[1]}")
        except queue.Empty:
            pass
        if not self.stop.is_set():
            self.root.after(15, self.poll_events)

    def send_input(self, packet: bytes) -> None:
        sock = self.sock
        if not self.input_enabled or sock is None:
            return
        try:
            with self.send_lock:
                sock.sendall(packet)
        except OSError as exc:
            if not self.stop.is_set():
                self.status.set(f"Input send failed: {exc}")

    def mouse_move(self, event: tk.Event) -> None:
        if not self.input_enabled or not self.remote_width or not self.remote_height:
            return
        x = max(0, min(self.remote_width - 1, event.x // self.scale))
        y = max(0, min(self.remote_height - 1, event.y // self.scale))
        self.pending_mouse = (x, y)
        if self.mouse_send_after is None:
            self.mouse_send_after = self.root.after(16, self.scheduled_mouse_move)

    def scheduled_mouse_move(self) -> None:
        self.mouse_send_after = None
        self.flush_mouse_move()

    def flush_mouse_move(self) -> None:
        if self.mouse_send_after is not None:
            self.root.after_cancel(self.mouse_send_after)
            self.mouse_send_after = None
        position = self.pending_mouse
        self.pending_mouse = None
        if position is not None:
            self.send_input(pack_mouse_move(*position))

    def mouse_button_down(self, event: tk.Event) -> str | None:
        button = TK_MOUSE_BUTTONS.get(event.num)
        if button is None:
            return None
        self.image_label.focus_set()
        self.flush_mouse_move()
        if button not in self.pressed_buttons:
            self.pressed_buttons.add(button)
            try:
                self.image_label.grab_set()
            except tk.TclError:
                pass
            self.send_input(pack_mouse_button(button, True))
        return "break"

    def mouse_button_up(self, event: tk.Event) -> str | None:
        button = TK_MOUSE_BUTTONS.get(event.num)
        if button is not None and button in self.pressed_buttons:
            self.flush_mouse_move()
            self.pressed_buttons.remove(button)
            self.send_input(pack_mouse_button(button, False))
            if not self.pressed_buttons:
                try:
                    self.image_label.grab_release()
                except tk.TclError:
                    pass
            return "break"
        return None

    @staticmethod
    def raw_key(event: tk.Event) -> int | None:
        return RAW_KEYS.get(event.keysym.lower())

    def key_down(self, event: tk.Event) -> str | None:
        raw_key = self.raw_key(event)
        if raw_key is None:
            return None
        # Repeated Windows key-down events are passed on as Amiga repeats.
        self.pressed_keys.add(raw_key)
        self.send_input(pack_raw_key(raw_key, True))
        return "break"

    def key_up(self, event: tk.Event) -> str | None:
        raw_key = self.raw_key(event)
        if raw_key is None:
            return None
        self.pressed_keys.discard(raw_key)
        self.send_input(pack_raw_key(raw_key, False))
        return "break"

    def release_all_input(self, _event: tk.Event | None = None) -> None:
        if self.mouse_send_after is not None:
            self.root.after_cancel(self.mouse_send_after)
            self.mouse_send_after = None
        self.pending_mouse = None
        for raw_key in tuple(self.pressed_keys):
            self.send_input(pack_raw_key(raw_key, False))
        for button in tuple(self.pressed_buttons):
            self.send_input(pack_mouse_button(button, False))
        self.pressed_keys.clear()
        self.pressed_buttons.clear()
        try:
            self.image_label.grab_release()
        except tk.TclError:
            pass

    def close(self) -> None:
        self.release_all_input()
        self.stop.set()
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="View and control a MintREMOTE stream")
    parser.add_argument("host", help="Amiga IP address")
    parser.add_argument("--port", type=int, default=5909)
    parser.add_argument("--scale", type=int, choices=(1, 2, 3, 4), default=1)
    args = parser.parse_args()
    MintRemoteViewer(args.host, args.port, args.scale).run()


if __name__ == "__main__":
    main()
