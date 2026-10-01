# MintREMOTE Windows client

## Connect

1. Start `MintRemoteServer 5909 5` on your Amiga.
2. Open `MintREMOTE.exe`, enter the Amiga IP address or hostname, and click **Connect**.
3. Use **Disconnect**, then **Connect** to reconnect or change the target.

The original protocol v1 Amiga server is view-only. For mouse and keyboard control,
use the protocol v2 server from PR #2 and start it with:

```text
MintRemoteServer 5909 5 INPUT
```

The client detects input capability automatically. It does not need an Amiga
server rebuild for view-only use. Screens remain native ECS/AGA planar
Workbench screens; RTG, HAM and screen-mode changes are outside the current
server protocol.

## Display and input

- **Fit** preserves the screen's pixel aspect ratio and centres it in the window.
- **1x–4x** uses nearest-neighbour scaling; scrollbars reach the edges of larger screens.
- **F11** toggles fullscreen. **F12** releases all held input and returns focus to the PC.
- **Save screenshot** writes an unscaled RGB PNG of the last complete frame.
- Click inside the displayed Amiga screen to focus it. Clicks in the surrounding border are ignored.
- All three mouse buttons work; drags keep the pointer at the screen edge when you move outside it.
- Disabling **Remote control**, losing screen focus, resizing or disconnecting releases held keys/buttons.
- Shift, Ctrl, Alt, cursor keys, F1–F10 and the numeric keypad map to Amiga raw keys.
- Insert maps to Help; Windows/Menu keys map to the Amiga keys where Windows allows delivery.
- The **Amiga keys** window provides Help, Amiga+E and Amiga+M buttons because Windows can intercept shortcuts.
- Symbols follow the keymap selected on the Amiga. This is raw-key control, not Unicode paste.

F11 and F12 are local shortcuts. Some OS shortcuts (for example Alt+Tab) stay
with Windows. Test modifiers, keypad Enter and Caps Lock with your Amiga's
keymap before relying on long remote typing sessions.

## Get or build the EXE

The **Windows client** GitHub Actions workflow builds and checks a Windows x64
executable and uploads `MintREMOTE-Windows-x64`. Download and extract that
artifact, then run `MintREMOTE.exe`. Python and Pillow are bundled inside it.

To build on Windows with Python 3.12 installed:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows.ps1
```

This creates a local virtual environment, runs the tests and builds
`dist/MintREMOTE.exe` with PyInstaller. The EXE is unsigned. No installer or
administrator rights are required to run it.

To run from source:

```powershell
py -m pip install -r viewer/requirements.txt
py viewer/mintremote_viewer.py
py viewer/mintremote_viewer.py 192.168.1.50 --port 5909 --scale 2
```

Preferences are saved under `%APPDATA%\MintREMOTE\settings.json`. Unreadable or
invalid preferences fall back to defaults. Source execution also works on
Linux/macOS with Tk and Pillow; executable packaging here targets Windows.

## Test without an Amiga

```powershell
py tools/mock_server.py
py viewer/mintremote_viewer.py 127.0.0.1
```

The mock server logs mouse positions, buttons and raw-key transitions. It
accepts reconnects. Use `--version 1` to test the original view-only server or
`--view-only` to test v2 without input support.

Automated tests:

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p gui_smoke.py -v
```

The second command needs a desktop display (or `xvfb-run` on Linux). It checks
that the actual Tk window renders a frame and that clicking/typing/focus loss
produce the expected packets.

## Real Amiga acceptance checks

Connect to your existing server, confirm palette colours and partial updates,
resize/fullscreen/scroll to every corner, and save a screenshot. Disconnect
while updates arrive, reconnect twice, and close during a failed connection.
With a v2 INPUT server, test Workbench icon double-clicks, dragging windows,
right-button menus, Shell typing, Shift/Ctrl/Alt, Help and keypad Enter. Hold a
key or mouse button, switch to another PC window, then verify nothing remains
held on the Amiga. Repeat while disabling Remote control and disconnecting.

The existing protocol has no authentication or encryption. Use a trusted LAN;
do not forward port 5909 to the Internet.
