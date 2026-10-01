# MintREMOTE

Remote viewing and control for classic Amigas, designed around the formats the
Amiga can produce cheaply rather than making a 68k machine behave like a
modern video encoder.

## PR1 prototype

The first prototype proves one path end-to-end:

1. `MintRemoteServer` locks the public Workbench screen.
2. It reads a native ECS/AGA planar bitmap in 32x16 pixel tiles.
3. Only tiles that differ from the last transmitted copy are sent over TCP.
4. The Python viewer reconstructs the bitplanes and palette on Windows.

The PC does the planar-to-RGB conversion. The Amiga only compares and copies
the bitplane bytes it already owns.

### Current limits

- Native planar Workbench screens only, from 1 to 8 bitplanes.
- One viewer at a time.
- View-only: keyboard and mouse return traffic is deliberately deferred.
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

Copy `MintRemoteServer` to the Amiga and run:

```text
MintRemoteServer [port] [delay_ticks]
MintRemoteServer 5909 5
```

`delay_ticks` is the pause between scans in Amiga ticks (normally 50 ticks per
second). Five ticks targets roughly ten scans per second without busy-looping.

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

The client accepts both protocol v1 (current `main` server, view only) and
protocol v2 from [PR #2](https://github.com/boingball/MintREMOTE/pull/2).
Mouse/keyboard control is available only when that server advertises input
support, started with `MintRemoteServer 5909 5 INPUT`. The Amiga source is
unchanged by the desktop client work.

The viewer can be tested before using an Amiga:

```powershell
py tools/mock_server.py
py viewer/mintremote_viewer.py 127.0.0.1
```

## Tests

```sh
make check
```

The host-side tests verify protocol framing, planar tile packing and decoding.
The Amiga executable still needs a Bebbo cross-toolchain and real-hardware or
emulator testing.

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the PR1 wire format and
[docs/PR1_TEST_PLAN.md](docs/PR1_TEST_PLAN.md) for the first hardware tests.

## License

MIT - Copyright (c) 2026 Darren Banfi.

