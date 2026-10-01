"""Host regression test for nonblocking server sends and cancellation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ServerIOTests(unittest.TestCase):
    def test_partial_writes_retries_disconnect_and_close(self):
        compiler = shutil.which("cc") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("A host C compiler is required")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "server_io_test"
            subprocess.run(
                [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
                 "-I" + str(root / "amiga"), str(root / "tests/server_io_test.c"),
                 "-o", str(executable)], check=True,
            )
            subprocess.run([str(executable)], check=True, timeout=10)
