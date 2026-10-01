# MintREMOTE

Remote viewing and control for classic Amigas, designed around the formats the
Amiga can produce cheaply rather than making a 68k machine behave like a
modern video encoder.

## Capture and remote input

The server and client use this path:

1. `MintRemoteServer` locks the public Workbench screen.
2. It reads a native ECS/AGA planar bitmap in 32x16 pixel tiles.
3. Only tiles that differ from the last transmitted copy are sent over TCP.
4. The Python viewer reconstructs the bitplanes and palette on Windows.
5. When explicitly enabled, mouse and keyboard messages travel back to the
   Amiga and are injected through `input.device`.

The PC does the planar-to-RGB conversion. The Amiga only compares and copies
the bitplane bytes it already owns.

### Current limits

- Native planar Workbench screens only, from 1 to 8 bitplanes.
- One viewer at a time.
- Standard mouse buttons, pointer movement and the common Amiga keyboard keys
  are supported; mouse wheel and unusual multimedia keys are not mapped yet.
- No compression, encryption or authentication yet.
- Screen-mode changes require reconnecting/restarting the prototype.
- This is for trusted LAN testing only. Do not expose TCP port 5909 to the
  Internet.

## Build the Amiga server

The Makefile follows the same Bebbo cross-toolchain convention as the other
Mint projects:

```sh
make
```

Override the prefix when required:

```sh
make CROSS=/opt/amiga13/m68k-amigaos/bin/m68k-amigaos-
```

Copy `MintRemoteServer` **and** `MintRemoteServer.info` (both are in the
`MintRemoteServer-AmigaOS` CI artifact, and `make` produces both) to the same
Amiga drawer.

### Start from Workbench

Double-click the **MintRemoteServer** icon. The server runs as a normal
Workbench GadTools application: no Shell or console window is opened, and any
start-up problem (no TCP/IP stack, port in use, unsupported screen) is shown in
a requester. Options are the icon's ToolTypes (select the icon, then
**Icons > Information...**):

```text
PORT=5909
DELAY=5
(INPUT)
```

Remove the brackets around `(INPUT)` to allow remote mouse and keyboard
control. `INPUT=NO` also leaves it disabled.

### Start from Shell

```text
MintRemoteServer [port] [delay_ticks] [INPUT]
MintRemoteServer 5909 5 INPUT
```

Arguments use the normal AmigaDOS `ReadArgs` template
`PORT/N,DELAY/N,INPUT/S`. The switch can therefore be used on its own or with
named values:

```text
MintRemoteServer INPUT
MintRemoteServer PORT=5909 DELAY=5 INPUT
```

`delay_ticks` is the pause between scans in Amiga ticks (normally 50 ticks per
second). Five ticks targets roughly ten scans per second without busy-looping.
Input is polled once per tick so it remains responsive independently of the
screen scan rate. Omit `INPUT` for a view-only server.

Either way the server opens a GadTools window titled **MintREMOTE** in the
centre of the Workbench screen. It shows a green running dot, the status
(**Listening for a PC viewer** or **PC connected: <address>**), the local IPv4
address and TCP port, the input mode and the captured screen size. Up to four
active non-loopback addresses are shown when the Amiga has multiple
interfaces. Enter one of these addresses in the PC client. If the stack cannot
report an address, the window says so explicitly.

- **Quit** (or the close gadget, Esc, `Q`, or **Project > Quit**) stops the
  server and releases remote input.
- **Disconnect** (or `D`, or **Project > Disconnect viewer**) drops the current
  PC viewer and keeps listening, so it can reconnect.
- **Project > About...** shows a non-blocking about requester.
- Ctrl-C in the Shell also stops a Shell-started server, including while it
  waits for a viewer. (`Break` with the process number works for `Run`.)

After a viewer disconnects, the server keeps listening so you can reconnect.

Requirements:

- AmigaOS 3.1 or later
- A native planar Workbench screen
- TCP/IP stack providing `bsdsocket.library` v4+

## Windows desktop client

Install Python 3 and Pillow:

```powershell
py -m pip install -r viewer/requirements.txt
py viewer/mintremote_viewer.py
```

Enter the Amiga's IP address and click **Connect**. The client remembers the
address, port and display scale. It offers fit-to-window or 1x–4x scaling,
fullscreen (F11), native-resolution PNG screenshots and reconnecting without
restarting the app. F12 releases remote input and returns focus to the PC.

For a standalone **MintREMOTE.exe** with no Python installation required,
download the `MintREMOTE-Windows-x64` artifact from the **Windows client**
GitHub Actions run for this branch. You can also build it locally:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows.ps1
```

The output is `dist/MintREMOTE.exe`. See [Windows client guide](docs/WINDOWS_CLIENT.md).

The client accepts both protocol v1 (the original view-only server) and
protocol v2 from [PR #2](https://github.com/boingball/MintREMOTE/pull/2).
Mouse/keyboard control is available when the v2 server advertises input
support, started with `MintRemoteServer 5909 5 INPUT`.

The viewer can be tested before using an Amiga:

```powershell
py tools/mock_server.py
py viewer/mintremote_viewer.py 127.0.0.1
```

## Tests

```sh
make check
```

The host-side tests verify protocol framing, planar tile packing and decoding,
and nonblocking server-send retries and cancellation (requires a host C compiler).
The Amiga executable still needs a Bebbo cross-toolchain and real-hardware or
emulator testing.

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the wire format,
[docs/PR1_TEST_PLAN.md](docs/PR1_TEST_PLAN.md) for the capture tests and
[docs/PR2_TEST_PLAN.md](docs/PR2_TEST_PLAN.md) for remote-input tests.
See [server GUI test plan](docs/SERVER_GUI_TEST_PLAN.md) for window, IP address
and shutdown checks on the Amiga.

## License

MIT - Copyright (c) 2026 Darren Banfi.
