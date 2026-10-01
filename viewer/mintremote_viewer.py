"""MintREMOTE desktop client. Run without arguments for the connection window."""
from __future__ import annotations

import argparse
from datetime import datetime
import queue
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from input_mapping import display_geometry, pointer_position, raw_key
from protocol import CAP_INPUT, pack_mouse_button, pack_mouse_move, pack_raw_key
from session import Frame, Session
from settings import SCALES, load_settings, save_settings


class MintRemoteViewer:
    def __init__(self, host: str | None = None, port: int | None = None,
                 scale: str | int | None = None) -> None:
        preferences = load_settings()
        self.root = tk.Tk()
        self.root.title("MintREMOTE - Amiga desktop")
        self.root.geometry("1000x700")
        self.root.minsize(640, 420)
        self.host = tk.StringVar(value=host or preferences.get("host", ""))
        self.port = tk.StringVar(value=str(port or preferences.get("port", 5909)))
        self.scale = tk.StringVar(value=(f"{scale}x" if isinstance(scale, int) else scale)
                                 or preferences.get("scale", "Fit"))
        self.control = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Enter your Amiga's address and click Connect.")
        self.mode = tk.StringVar(value="Not connected")
        self.stats = tk.StringVar(value="")
        self.session: Session | None = None
        self.connected = False
        self.capabilities = 0
        self.remote_width = self.remote_height = 0
        self.geometry = (0, 0, 1, 1)
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.pressed_keys: dict[int, int] = {}
        self.pressed_buttons: set[int] = set()
        self.pending_mouse: tuple[int, int] | None = None
        self.mouse_after: str | None = None
        self.resize_after: str | None = None
        self.frame_count = 0
        self.fps_start = time.monotonic()
        self.fps = 0.0
        self.closed = False
        self.fullscreen = False
        self.poll_after: str | None = None
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<F12>", self.release_focus)
        self.root.bind_all("<ButtonRelease>", self.mouse_button_up, add="+")
        if host:
            self.root.after(0, self.connect)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="MintREMOTE", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(top, text="Your Amiga, on your PC").pack(side="left", padx=16)
        connection = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        connection.pack(fill="x")
        ttk.Label(connection, text="Amiga address").pack(side="left")
        self.host_entry = ttk.Entry(connection, textvariable=self.host, width=28)
        self.host_entry.pack(side="left", padx=(8, 12))
        self.host_entry.bind("<Return>", lambda _: self.connect())
        ttk.Label(connection, text="Port").pack(side="left")
        self.port_entry = ttk.Entry(connection, textvariable=self.port, width=7)
        self.port_entry.pack(side="left", padx=8)
        self.connect_button = ttk.Button(connection, text="Connect", command=self.connect)
        self.connect_button.pack(side="left", padx=4)
        self.disconnect_button = ttk.Button(connection, text="Disconnect", command=self.disconnect,
                                            state="disabled")
        self.disconnect_button.pack(side="left", padx=4)
        toolbar = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Display").pack(side="left")
        scale_box = ttk.Combobox(toolbar, values=SCALES, textvariable=self.scale,
                                 state="readonly", width=6)
        scale_box.pack(side="left", padx=8)
        scale_box.bind("<<ComboboxSelected>>", self.scale_changed)
        ttk.Button(toolbar, text="Fullscreen (F11)", command=self.toggle_fullscreen).pack(side="left")
        self.screenshot_button = ttk.Button(toolbar, text="Save screenshot", command=self.screenshot,
                                           state="disabled")
        self.screenshot_button.pack(side="left", padx=8)
        self.control_button = ttk.Checkbutton(toolbar, text="Remote control", variable=self.control,
                                              command=self.control_changed, state="disabled")
        self.control_button.pack(side="left")
        ttk.Button(toolbar, text="Amiga keys", command=self.amiga_keys).pack(side="right")
        area = ttk.Frame(self.root)
        area.pack(fill="both", expand=True, padx=10)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(area, bg="#19212b", highlightthickness=0, takefocus=True)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.xscroll = ttk.Scrollbar(area, orient="horizontal", command=self.canvas.xview)
        self.yscroll = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        self.xscroll.grid(row=1, column=0, sticky="ew")
        self.yscroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=self.xscroll.set, yscrollcommand=self.yscroll.set)
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.placeholder = self.canvas.create_text(30, 30, anchor="nw", fill="#e2e8f0",
            font=("Segoe UI", 14), text="Ready to connect\n\nStart MintRemoteServer on your Amiga.")
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<Motion>", self.mouse_move)
        self.canvas.bind("<ButtonPress>", self.mouse_button_down)
        self.canvas.bind("<KeyPress>", self.key_down)
        self.canvas.bind("<KeyRelease>", self.key_up)
        self.canvas.bind("<FocusOut>", self.release_all_input)
        footer = ttk.Frame(self.root, padding=10)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.mode, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(footer, textvariable=self.status, wraplength=930).pack(anchor="w")
        ttk.Label(footer, textvariable=self.stats).pack(anchor="w")
        ttk.Label(footer, text="Click the screen to control | F12 releases focus | Trusted LAN only",
                  foreground="#555555").pack(anchor="w", pady=(4, 0))
        self.host_entry.focus_set()

    def run(self) -> None:
        self.poll_after = self.root.after(15, self.poll_events)
        self.root.mainloop()

    @property
    def input_enabled(self) -> bool:
        return bool(self.connected and self.capabilities & CAP_INPUT and self.control.get())

    def connect(self) -> None:
        if self.session is not None:
            return
        host = self.host.get().strip()
        try:
            port = int(self.port.get())
            if not host or not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Connection", "Enter an Amiga address and a port from 1 to 65535.",
                                 parent=self.root)
            return
        self.host.set(host)
        self.session = Session(host, port)
        self.capabilities = 0
        self.connected = False
        self.image = self.photo = None
        self.remote_width = self.remote_height = 0
        self.frame_count = 0
        self.fps_start = time.monotonic()
        self.fps = 0.0
        self.canvas.itemconfigure(self.image_item, image="")
        self.canvas.itemconfigure(self.placeholder, state="normal", text="Connecting...")
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.canvas.configure(scrollregion=(0, 0, 1, 1))
        self.screenshot_button.configure(state="disabled")
        self.stats.set("")
        self.connect_button.configure(state="disabled")
        self.host_entry.configure(state="disabled")
        self.port_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.status.set(f"Connecting to {host}:{port}...")
        self.mode.set("Connecting")
        save_settings(host, port, self.scale.get())
        self.session.start()

    def _connection_ended(self, reason: str) -> None:
        self.release_all_input(send=False)
        self.session = None
        self.connected = False
        self.capabilities = 0
        self.connect_button.configure(state="normal")
        self.host_entry.configure(state="normal")
        self.port_entry.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.control_button.configure(state="disabled")
        self.mode.set("Disconnected")
        self.status.set(reason)
        if self.image is None:
            self.canvas.itemconfigure(self.placeholder, text="Disconnected\n\n" + reason)

    def disconnect(self) -> None:
        if self.session:
            packet = self.release_packet()
            self.release_all_input(send=False)
            self.session.close(packet)
        self._connection_ended("Disconnected. Click Connect to start a new session.")

    def poll_events(self) -> None:
        session = self.session
        if session is not None:
            try:
                while True:
                    event = session.events.get_nowait()
                    if event[0] == "connected":
                        hello = event[1]
                        self.remote_width, self.remote_height = hello.width, hello.height
                        self.connected = True
                        self.status.set(f"{hello.width} x {hello.height} | {hello.depth} bitplanes | "
                                        f"Protocol {hello.version}")
                        self.update_mode()
                    elif event[0] == "capabilities":
                        # Release tracked state if the server withdraws control.
                        self.release_all_input()
                        self.capabilities = event[1]
                        self.control_button.configure(state="normal" if event[1] & CAP_INPUT
                                                      else "disabled")
                        self.update_mode()
                    elif event[0] == "error":
                        self.status.set(event[1])
                    elif event[0] == "disconnected":
                        self._connection_ended(event[1])
                        break
            except queue.Empty:
                pass
            if self.session is session:
                frame = session.take_frame()
                if frame is not None:
                    self.show_frame(frame)
        if not self.closed:
            self.poll_after = self.root.after(15, self.poll_events)

    def update_mode(self) -> None:
        if not self.connected:
            return
        if self.input_enabled:
            self.mode.set("Remote control available - click the Amiga screen")
        elif self.capabilities & CAP_INPUT:
            self.mode.set("View only - remote control paused")
        else:
            self.mode.set("View only - server has no input enabled")

    def show_frame(self, frame: Frame) -> None:
        image = Image.frombytes("P", (frame.width, frame.height), frame.pixels)
        palette = [component for colour in frame.palette for component in colour]
        image.putpalette(palette + [0] * (768 - len(palette)))
        self.image = image
        self.render()
        self.screenshot_button.configure(state="normal")
        self.frame_count += 1
        elapsed = time.monotonic() - self.fps_start
        if elapsed >= 1:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start = time.monotonic()
        self.stats.set(f"Frame {frame.frame_id} | {self.fps:.1f} displayed fps | "
                       f"{frame.changed_tiles} changed tiles | scan {frame.scan_ms} ms")

    def render(self) -> None:
        if self.resize_after is not None:
            self.root.after_cancel(self.resize_after)
            self.resize_after = None
        if self.image is None:
            return
        width, height = self.image.size
        self.geometry = display_geometry(width, height, self.canvas.winfo_width(),
                                         self.canvas.winfo_height(), self.scale.get())
        left, top, dw, dh = self.geometry
        image = self.image.resize((dw, dh), Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(image, master=self.root)
        self.canvas.coords(self.image_item, left, top)
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.canvas.itemconfigure(self.placeholder, state="hidden")
        self.canvas.configure(scrollregion=(0, 0, max(left + dw, self.canvas.winfo_width()),
                                            max(top + dh, self.canvas.winfo_height())))
        if self.scale.get() == "Fit":
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

    def resize(self, _event=None) -> None:
        self.release_all_input()
        if self.resize_after is not None:
            self.root.after_cancel(self.resize_after)
        self.resize_after = self.root.after(80, self.render)

    def scale_changed(self, _event=None) -> None:
        self.release_all_input()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render()
        try:
            save_settings(self.host.get(), int(self.port.get()), self.scale.get())
        except ValueError:
            pass

    def toggle_fullscreen(self, _event=None) -> str:
        self.release_all_input()
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        return "break"

    def release_focus(self, _event=None) -> str:
        self.release_all_input()
        self.connect_button.focus_set()
        return "break"

    def control_changed(self) -> None:
        # The checkbox has already changed, so release bypasses the new state.
        self.release_all_input()
        self.update_mode()

    def screenshot(self) -> None:
        self.release_all_input()
        if self.image is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Save Amiga screenshot",
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
            initialfile=f"MintREMOTE-{datetime.now():%Y%m%d-%H%M%S}.png")
        if path:
            try:
                self.image.convert("RGB").save(path, format="PNG")
                self.status.set(f"Screenshot saved: {path}")
            except OSError as exc:
                messagebox.showerror("Screenshot", str(exc), parent=self.root)

    def send_input(self, packet: bytes) -> bool:
        return bool(self.input_enabled and self.session and self.session.send(packet))

    def position(self, event, clamp: bool = False) -> tuple[int, int] | None:
        if not self.input_enabled or self.image is None:
            return None
        return pointer_position(int(self.canvas.canvasx(event.x)), int(self.canvas.canvasy(event.y)),
                                self.geometry, self.remote_width, self.remote_height, clamp)

    def mouse_move(self, event) -> None:
        if self.canvas.focus_get() != self.canvas and not self.pressed_buttons:
            return
        position = self.position(event, clamp=bool(self.pressed_buttons))
        if position is not None:
            self.pending_mouse = position
            if self.mouse_after is None:
                self.mouse_after = self.root.after(16, self.flush_mouse_move)

    def flush_mouse_move(self) -> None:
        if self.mouse_after is not None:
            self.root.after_cancel(self.mouse_after)
            self.mouse_after = None
        if self.pending_mouse is not None:
            self.send_input(pack_mouse_move(*self.pending_mouse))
            self.pending_mouse = None

    def mouse_button_down(self, event) -> str | None:
        if event.num not in (1, 2, 3):
            return None
        position = self.position(event)
        if position is None:
            return None
        self.canvas.focus_set()
        # Click coordinates must be sent even if there was no preceding motion.
        self.pending_mouse = position
        self.flush_mouse_move()
        if event.num not in self.pressed_buttons and self.send_input(pack_mouse_button(event.num, True)):
            self.pressed_buttons.add(event.num)
            self.canvas.grab_set()
        return "break"

    def mouse_button_up(self, event) -> str | None:
        if event.num not in self.pressed_buttons:
            return None
        # bind_all may deliver a release relative to another widget.
        x = event.x_root - self.canvas.winfo_rootx()
        y = event.y_root - self.canvas.winfo_rooty()
        position = pointer_position(int(self.canvas.canvasx(x)), int(self.canvas.canvasy(y)),
                                    self.geometry, self.remote_width, self.remote_height, True)
        self.pending_mouse = position
        self.flush_mouse_move()
        self.send_input(pack_mouse_button(event.num, False))
        self.pressed_buttons.remove(event.num)
        if not self.pressed_buttons:
            self.canvas.grab_release()
        return "break"

    def key_down(self, event) -> str | None:
        if event.keysym in ("F11", "F12"):
            return None
        code = raw_key(event.keysym, event.keycode, sys.platform == "win32")
        if code is None or not self.input_enabled:
            return None
        # Amiga input.device supplies repeat. Repeated PC key-down events would
        # otherwise create two independent repeat sources.
        if event.keycode not in self.pressed_keys:
            if code not in self.pressed_keys.values() and not self.send_input(pack_raw_key(code, True)):
                return "break"
            self.pressed_keys[event.keycode] = code
        return "break"

    def key_up(self, event) -> str | None:
        code = self.pressed_keys.pop(event.keycode, None)
        if code is None:
            return None
        if code not in self.pressed_keys.values():
            self.send_input(pack_raw_key(code, False))
        return "break"

    def release_packet(self) -> bytes:
        return b"".join(pack_raw_key(code, False) for code in sorted(set(self.pressed_keys.values()))) + \
               b"".join(pack_mouse_button(button, False) for button in sorted(self.pressed_buttons))

    def release_all_input(self, _event=None, send: bool = True) -> None:
        if self.mouse_after is not None:
            self.root.after_cancel(self.mouse_after)
            self.mouse_after = None
        self.pending_mouse = None
        packet = self.release_packet()
        if send and packet and self.session:
            self.session.send(packet)
        self.pressed_keys.clear()
        self.pressed_buttons.clear()
        if self.canvas.grab_current() == self.canvas:
            self.canvas.grab_release()

    def amiga_keys(self) -> None:
        self.release_focus()
        window = tk.Toplevel(self.root)
        window.title("Amiga keys")
        window.resizable(False, False)
        ttk.Label(window, text="Insert = Help | Left/Right Alt = Amiga Alt\n"
                  "Windows/Menu keys = Left/Right Amiga\n"
                  "Symbols follow the keymap configured on your Amiga.\n"
                  "Some Windows shortcuts stay with the PC; use these buttons.",
                  padding=12).pack()
        buttons = ttk.Frame(window, padding=12)
        buttons.pack()
        for label, codes in (("Help", (0x5F,)), ("Amiga + E", (0x66, 0x12)),
                             ("Amiga + M", (0x66, 0x37))):
            ttk.Button(buttons, text=label, command=lambda c=codes: self.key_chord(c)).pack(
                side="left", padx=4)

    def key_chord(self, codes: tuple[int, ...]) -> None:
        self.send_input(b"".join(pack_raw_key(code, True) for code in codes) +
                        b"".join(pack_raw_key(code, False) for code in reversed(codes)))

    def close(self) -> None:
        if self.closed:
            return
        self.disconnect()
        self.closed = True
        if self.resize_after is not None:
            self.root.after_cancel(self.resize_after)
        if self.poll_after is not None:
            self.root.after_cancel(self.poll_after)
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="View and control an Amiga with MintREMOTE")
    parser.add_argument("host", nargs="?", help="Amiga IP/hostname; omit for the connection window")
    parser.add_argument("--port", type=int)
    parser.add_argument("--scale", choices=("fit", "1", "2", "3", "4"))
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("port must be from 1 to 65535")
    scale = "Fit" if args.scale == "fit" else int(args.scale) if args.scale else None
    MintRemoteViewer(args.host, args.port, scale).run()


if __name__ == "__main__":
    main()
