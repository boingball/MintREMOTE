from __future__ import annotations
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from input_mapping import display_geometry, pointer_position, raw_key
from protocol import (
    CAP_INPUT, HANDSHAKE, MAGIC, MSG_GOODBYE, MSG_RAW_KEY, PIXEL_PLANAR_INDEXED,
    Tile, apply_planar_tile_indices, encode_indexed_tile, pack_capabilities,
    pack_frame_end, pack_handshake, pack_message, pack_palette, pack_raw_key,
    pack_tile, parse_tile, read_handshake, read_message,
)
from session import Session
from settings import load_settings, save_settings


class ClientTests(unittest.TestCase):
    def test_v1_and_v2_handshakes(self):
        for version in (1, 2):
            left, right = socket.socketpair()
            with left, right:
                left.sendall(pack_handshake(320, 200, 32, 16, 4, version=version))
                self.assertEqual(read_handshake(right).version, version)

    def test_invalid_handshake_rejected_before_allocation(self):
        for width, height, tw, th in ((0, 200, 32, 16), (65535, 65535, 32, 16),
                                      (320, 200, 0, 16), (320, 200, 321, 16)):
            left, right = socket.socketpair()
            with left, right:
                left.sendall(HANDSHAKE.pack(MAGIC, 1, width, height, tw, th,
                                           4, PIXEL_PLANAR_INDEXED, 16))
                with self.assertRaises(ValueError):
                    read_handshake(right)

    def test_bad_tile_layout_and_bounds(self):
        for tile in (Tile(1, 0, 0, 9, 1, 1, 1, b'\xff'),
                     Tile(1, 0, 0, 8, 1, 1, 1, b''),
                     Tile(1, 319, 0, 8, 1, 1, 1, b'\xff'),
                     Tile(1, -1, 0, 8, 1, 1, 1, b'\xff')):
            with self.assertRaises(ValueError):
                apply_planar_tile_indices(bytearray(320 * 200), 320, 200, tile)
        with self.assertRaises(ValueError):
            parse_tile(pack_tile(Tile(1, 0, 0, 9, 1, 1, 1, b'\xff'))[4:])

    def test_fragmented_stream(self):
        packet = pack_handshake(8, 1, 8, 1, 1)
        class Fragmented:
            def recv(self, count):
                nonlocal packet
                result, packet = packet[:1], packet[1:]
                return result
        self.assertEqual(read_handshake(Fragmented()).width, 8)

    def test_fit_coordinates_and_letterbox(self):
        geometry = display_geometry(320, 200, 1000, 700, 'Fit')
        self.assertEqual(geometry, (0, 37, 1000, 625))
        self.assertIsNone(pointer_position(0, 0, geometry, 320, 200))
        self.assertEqual(pointer_position(999, 661, geometry, 320, 200), (319, 199))
        self.assertEqual(pointer_position(-20, 800, geometry, 320, 200, True), (0, 199))
        self.assertEqual(display_geometry(320, 200, 200, 100, '2x'), (0, 0, 640, 400))

    def test_windows_keys_are_stable_with_shift(self):
        self.assertEqual(raw_key('A', 65, True), 0x20)
        self.assertEqual(raw_key('a', 65, True), 0x20)
        self.assertEqual(raw_key('quotedbl', 0xDE, True), 0x2A)
        self.assertEqual(raw_key('apostrophe', 0xDE, True), 0x2A)
        self.assertEqual(raw_key('Shift_R', 16, True), 0x61)
        self.assertEqual(raw_key('KP_Enter', 13, True), 0x43)
        self.assertIsNone(raw_key('Print', 44, True))

    def test_settings_corruption_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            self.assertEqual(load_settings(path), {})
            path.write_text('{broken')
            self.assertEqual(load_settings(path), {})
            path.write_text('{"port":-1,"scale":"invalid","host":5}')
            self.assertEqual(load_settings(path), {})
            save_settings('amiga.local', 5909, 'Fit', path)
            self.assertEqual(load_settings(path), {'host':'amiga.local','port':5909,'scale':'Fit'})


class SessionTests(unittest.TestCase):
    def start_server(self, handler):
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        server.settimeout(5)
        self.addCleanup(server.close)
        errors = []
        def run():
            try:
                client, _ = server.accept()
                with client:
                    client.settimeout(5)
                    handler(client)
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        session = Session('127.0.0.1', server.getsockname()[1])
        self.addCleanup(session.close)
        session.start()
        return session, thread, errors

    @staticmethod
    def wait_for(predicate, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = predicate()
            if result:
                return result
            time.sleep(0.005)
        raise AssertionError('timed out waiting for background session')

    def test_v1_view_only_and_clean_goodbye(self):
        def server(client):
            client.sendall(pack_handshake(8, 1, 8, 1, 1, version=1) +
                           pack_palette([(0,0,0),(255,255,255)]) +
                           pack_tile(encode_indexed_tile([1]*8, 8, 0, 0, 8, 1, 1, 1)) +
                           pack_frame_end(1, 1) + pack_message(MSG_GOODBYE, b''))
        session, thread, errors = self.start_server(server)
        self.assertTrue(session.finished.wait(3))
        self.assertFalse(session.send(pack_raw_key(0x20, True)))
        self.assertEqual(session.take_frame().pixels, bytes([1]*8))
        events = []
        while not session.events.empty():
            events.append(session.events.get())
        self.assertIn(('disconnected','Server ended the session'), events)
        thread.join(3)
        self.assertEqual(errors, [])

    def test_capabilities_survive_frame_flood_and_releases_drain(self):
        received = []
        ready = threading.Event()
        def server(client):
            client.sendall(pack_handshake(8, 1, 8, 1, 1) + pack_capabilities(CAP_INPUT))
            for number in range(100):
                client.sendall(pack_frame_end(number, 0))
            ready.set()
            try:
                while True:
                    received.append(read_message(client))
            except EOFError:
                pass
        session, thread, errors = self.start_server(server)
        self.assertTrue(ready.wait(3))
        self.wait_for(lambda: session.latest_frame and session.latest_frame.frame_id == 99)
        self.assertTrue(session.send(pack_raw_key(0x20, True)))
        session.close(pack_raw_key(0x20, False))
        self.assertTrue(session.finished.wait(3))
        thread.join(3)
        self.assertEqual(received, [(MSG_RAW_KEY, b'\x20\x01'), (MSG_RAW_KEY, b'\x20\x00')])
        self.assertEqual(session.events.get()[0], 'connected')
        self.assertEqual(session.events.get(), ('capabilities', CAP_INPUT))
        self.assertEqual(errors, [])

    def test_disconnect_interrupts_partial_message(self):
        sent = threading.Event()
        def server(client):
            client.sendall(pack_handshake(8, 1, 8, 1, 1) + b'\x01')
            sent.set()
            self.assertEqual(client.recv(1), b'')
        session, thread, errors = self.start_server(server)
        self.assertTrue(sent.wait(3))
        session.close()
        self.assertTrue(session.finished.wait(3))
        thread.join(3)
        self.assertEqual(errors, [])

    def test_cancel_before_connect(self):
        session = Session('127.0.0.1', 1)
        session.close()
        session.start()
        self.assertTrue(session.finished.wait(3))
        self.assertFalse(session.send(pack_raw_key(0x20, True)))


if __name__ == '__main__':
    unittest.main()
