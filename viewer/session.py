"""Background connection and decoding; no Tk calls or socket writes on the UI thread."""
from __future__ import annotations

from dataclasses import dataclass
import queue
import socket
import threading

from protocol import (
    CAP_INPUT, MSG_CAPABILITIES, MSG_FRAME_END, MSG_GOODBYE, MSG_PALETTE,
    MSG_TILE, apply_planar_tile_indices, parse_capabilities, parse_frame_end,
    parse_palette, parse_tile, read_handshake, read_message,
)


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    pixels: bytes
    palette: tuple
    frame_id: int
    changed_tiles: int
    scan_ms: int


class Session:
    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port
        # Lifecycle events must never be discarded when rendering falls behind.
        self.events: queue.SimpleQueue = queue.SimpleQueue()
        self.outgoing: queue.Queue = queue.Queue(maxsize=256)
        self.lock = threading.Lock()
        self.closing = threading.Event()
        self.finished = threading.Event()
        self.sock: socket.socket | None = None
        self.latest_frame: Frame | None = None
        self.input_allowed = False

    def start(self) -> None:
        threading.Thread(target=self._receive, daemon=True).start()

    def take_frame(self) -> Frame | None:
        with self.lock:
            frame, self.latest_frame = self.latest_frame, None
            return frame

    def send(self, packet: bytes) -> bool:
        with self.lock:
            if self.closing.is_set() or not self.input_allowed or self.sock is None:
                return False
            try:
                self.outgoing.put_nowait(packet)
                return True
            except queue.Full:
                # Never silently drop a key/button release: close the session so
                # the input server releases its tracked state.
                self.events.put(("error", "Input queue full; connection closed"))
                self.closing.set()
                self._shutdown()
                return False

    def close(self, release_packet: bytes = b"") -> None:
        with self.lock:
            if self.closing.is_set():
                return
            self.closing.set()
            if self.sock is not None:
                try:
                    if release_packet and self.input_allowed:
                        self.outgoing.put_nowait(release_packet)
                    self.outgoing.put_nowait(None)
                except queue.Full:
                    self._shutdown()

    def _shutdown(self) -> None:
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _send(self, sock: socket.socket) -> None:
        try:
            while not self.finished.is_set():
                try:
                    packet = self.outgoing.get(timeout=0.2)
                except queue.Empty:
                    continue
                if packet is None:
                    break
                sock.sendall(packet)
        except OSError as exc:
            if not self.closing.is_set():
                self.events.put(("error", f"Input send failed: {exc}"))
        finally:
            # Also wakes a receive blocked on a partial message.
            with self.lock:
                self._shutdown()

    def _receive(self) -> None:
        reason = "Server closed the connection"
        try:
            with socket.create_connection((self.host, self.port), timeout=10) as sock:
                with self.lock:
                    if self.closing.is_set():
                        return
                    self.sock = sock
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    threading.Thread(target=self._send, args=(sock,), daemon=True).start()
                hello = read_handshake(sock)
                # Bound stalled/partial streams, but permit slow Amiga captures.
                sock.settimeout(30)
                self.events.put(("connected", hello))
                palette = [(0, 0, 0)] * hello.palette_entries
                framebuffer = bytearray(hello.width * hello.height)
                while True:
                    msg_type, payload = read_message(sock)
                    if msg_type == MSG_PALETTE:
                        palette = parse_palette(payload)
                        if len(palette) != hello.palette_entries:
                            raise ValueError("server changed palette size")
                    elif msg_type == MSG_TILE:
                        tile = parse_tile(payload)
                        if (tile.depth != hello.depth or tile.width > hello.tile_width
                                or tile.height > hello.tile_height):
                            raise ValueError("tile does not match the screen declaration")
                        apply_planar_tile_indices(framebuffer, hello.width, hello.height, tile)
                    elif msg_type == MSG_FRAME_END:
                        frame_id, changed, scan_ms = parse_frame_end(payload)
                        frame = Frame(hello.width, hello.height, bytes(framebuffer),
                                      tuple(palette), frame_id, changed, scan_ms)
                        with self.lock:
                            self.latest_frame = frame
                    elif msg_type == MSG_CAPABILITIES and hello.version >= 2:
                        capabilities = parse_capabilities(payload)
                        with self.lock:
                            self.input_allowed = bool(capabilities & CAP_INPUT)
                        self.events.put(("capabilities", capabilities))
                    elif msg_type == MSG_GOODBYE:
                        reason = "Server ended the session"
                        break
                    else:
                        raise ValueError(f"unknown message type {msg_type}")
        except EOFError:
            pass
        except Exception as exc:
            reason = str(exc)
            if not self.closing.is_set():
                self.events.put(("error", reason))
        finally:
            with self.lock:
                self.sock = None
                self.input_allowed = False
            self.finished.set()
            self.events.put(("disconnected", reason))
