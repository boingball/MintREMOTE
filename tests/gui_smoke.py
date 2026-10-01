"""Actual Tk smoke/input tests. Run explicitly with a display; Windows CI runs these."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from mintremote_viewer import MintRemoteViewer
from protocol import CAP_INPUT, pack_mouse_button, pack_mouse_move, pack_raw_key
from session import Frame


class FakeSession:
    def __init__(self):
        self.sent = []
        self.closed = []
    def send(self, packet):
        self.sent.append(packet)
        return True
    def close(self, packet=b''):
        self.closed.append(packet)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        with patch('mintremote_viewer.load_settings', return_value={}):
            self.app = MintRemoteViewer()
        self.addCleanup(self.app.close)
        self.app.root.update()
        self.app.session = FakeSession()
        self.app.connected = True
        self.app.capabilities = CAP_INPUT
        self.app.remote_width, self.app.remote_height = 320, 200
        self.app.show_frame(Frame(320, 200, bytes([1]*64000), ((0,0,0),(255,255,255)), 1, 1, 0))
        self.app.root.update()
        self.app.render()

    def click(self):
        x, y, dw, dh = self.app.geometry
        return SimpleNamespace(num=1, x=x+dw//2, y=y+dh//2)

    def test_renders_and_click_sends_position_before_button(self):
        self.assertEqual(self.app.image.size, (320,200))
        self.assertIsNotNone(self.app.photo)
        self.app.mouse_button_down(self.click())
        from protocol import parse_mouse_move
        x, y = parse_mouse_move(self.app.session.sent[0][4:])
        self.assertIn(x, (159, 160))
        self.assertIn(y, (99, 100))
        self.assertEqual(self.app.session.sent[1], pack_mouse_button(1, True))
        self.app.release_all_input()
        self.assertEqual(self.app.session.sent[-1], pack_mouse_button(1,False))
        self.assertIsNone(self.app.canvas.grab_current())

    def test_release_uses_original_physical_key_and_no_duplicate_repeat(self):
        self.app.key_down(SimpleNamespace(keysym='A', keycode=65))
        self.app.key_down(SimpleNamespace(keysym='A', keycode=65))
        self.app.key_up(SimpleNamespace(keysym='a', keycode=65))
        self.assertEqual(self.app.session.sent, [pack_raw_key(0x20,True), pack_raw_key(0x20,False)])

    def test_pausing_releases_held_input(self):
        self.app.key_down(SimpleNamespace(keysym='Shift_L', keycode=16))
        self.app.mouse_button_down(self.click())
        self.app.control.set(False)
        self.app.control_changed()
        self.assertEqual(self.app.session.sent[-1], pack_raw_key(0x60,False)+pack_mouse_button(1,False))
        self.assertFalse(self.app.pressed_keys)
        self.assertFalse(self.app.pressed_buttons)
        self.assertFalse(self.app.input_enabled)

    def test_disconnect_drains_releases_and_resets_controls(self):
        self.app.key_down(SimpleNamespace(keysym='a', keycode=65))
        session = self.app.session
        self.app.disconnect()
        self.assertEqual(session.closed, [pack_raw_key(0x20,False)])
        self.assertIsNone(self.app.session)
        self.assertEqual(str(self.app.connect_button['state']), 'normal')
        self.assertFalse(self.app.input_enabled)

    def test_view_only_sends_nothing(self):
        self.app.capabilities = 0
        self.app.mouse_button_down(self.click())
        self.app.key_down(SimpleNamespace(keysym='a',keycode=65))
        self.assertEqual(self.app.session.sent, [])
        self.assertFalse(self.app.pressed_buttons)

    def test_letterbox_click_ignored_and_fullscreen_toggles(self):
        self.app.scale.set('1x')
        self.app.root.update()
        self.app.render()
        self.assertTrue(self.app.geometry[0] > 0 or self.app.geometry[1] > 0)
        self.app.mouse_button_down(SimpleNamespace(num=1,x=0,y=0))
        self.assertEqual(self.app.session.sent, [])
        self.app.toggle_fullscreen()
        self.app.root.update()
        self.assertTrue(self.app.fullscreen)
        if sys.platform == 'win32':
            self.assertTrue(self.app.root.attributes('-fullscreen'))
        self.app.toggle_fullscreen()

    def test_actual_focus_loss_releases_key(self):
        self.app.root.focus_force()
        self.app.canvas.focus_set()
        self.app.root.update()
        self.app.key_down(SimpleNamespace(keysym='a', keycode=65))
        self.app.host_entry.focus_set()
        self.app.root.update()
        self.assertFalse(self.app.pressed_keys)
        self.assertEqual(self.app.session.sent[-1], pack_raw_key(0x20, False))

    def test_f12_releases_focus_while_connect_button_is_disabled(self):
        self.app.connect_button.configure(state="disabled")
        self.app.root.focus_force()
        self.app.canvas.focus_set()
        self.app.root.update()
        self.app.key_down(SimpleNamespace(keysym="a", keycode=65))
        self.app.release_focus()
        self.app.root.update()
        self.assertNotEqual(self.app.root.focus_get(), self.app.canvas)
        self.assertFalse(self.app.pressed_keys)
        self.assertEqual(self.app.session.sent[-1], pack_raw_key(0x20, False))

    def test_png_is_native_resolution(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'shot.png')
            with patch('mintremote_viewer.filedialog.asksaveasfilename', return_value=path):
                self.app.screenshot()
            with Image.open(path) as image:
                self.assertEqual(image.size, (320,200))
                self.assertEqual(image.getpixel((0,0)), (255,255,255))


class DesktopConnectionTests(unittest.TestCase):
    def test_real_stream_disconnect_and_reconnect_both_versions(self):
        import socket
        import threading
        import time
        from protocol import pack_handshake, pack_palette, pack_frame_end, pack_capabilities, pack_tile, encode_indexed_tile, read_message
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        server.settimeout(5)
        self.addCleanup(server.close)
        received = []
        errors = []
        def serve():
            try:
                for version in (1, 2):
                    client, _ = server.accept()
                    with client:
                        client.settimeout(5)
                        data = pack_handshake(320,200,32,16,1,version=version)
                        if version == 2:
                            data += pack_capabilities(CAP_INPUT)
                        data += pack_palette([(0,0,0),(255,255,255)])
                        data += pack_tile(encode_indexed_tile([1]*64000,320,0,0,32,16,1,1))
                        client.sendall(data + pack_frame_end(1,1))
                        try:
                            while True:
                                received.append(read_message(client))
                        except EOFError:
                            pass
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=serve,daemon=True)
        with patch('mintremote_viewer.load_settings',return_value={}):
            app=MintRemoteViewer()
        self.addCleanup(app.close)
        # First-time Tk setup on Windows may take longer than the mock server
        # accept timeout. Start accepting only after the window exists.
        thread.start()
        app.host.set('127.0.0.1')
        app.port.set(str(server.getsockname()[1]))
        app.poll_after=app.root.after(15,app.poll_events)
        def pump(predicate):
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                app.root.update()
                if predicate():
                    return
                time.sleep(.005)
            self.fail(f'desktop session did not reach expected state: {app.status.get()}; server errors: {errors}')
        with patch('mintremote_viewer.save_settings'):
            app.connect()
            pump(lambda: app.image is not None)
            self.assertFalse(app.input_enabled)
            self.assertEqual(app.image.getpixel((0,0)),1)
            app.disconnect()
            app.connect()
            pump(lambda: app.image is not None and app.input_enabled)
            app.key_down(SimpleNamespace(keysym='a',keycode=65))
            app.disconnect()
        thread.join(3)
        self.assertEqual(errors,[])
        self.assertEqual([payload for kind,payload in received], [b'\x20\x01',b'\x20\x00'])


if __name__ == '__main__':
    unittest.main()
