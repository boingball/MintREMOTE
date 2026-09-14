# PR1 test plan

## Before using the Amiga

1. Run `make check`.
2. Start `python tools/mock_server.py`.
3. Connect with `python viewer/mintremote_viewer.py 127.0.0.1`.
4. Confirm the blue/checkerboard test screen and moving orange square render.

## WinUAE

1. Use an AmigaOS 3.1 native planar Workbench mode, initially 640x256x4.
2. Ensure the emulated TCP stack exposes `bsdsocket.library` v4 or later.
3. Start `MintRemoteServer 5909 5`.
4. Connect the viewer to the emulated Amiga IP.
5. Drag windows, type in a Shell and change Workbench palette colours.
6. Confirm that unchanged frames report zero tiles and local Workbench input
   remains responsive.

## Real hardware matrix

| Machine | First mode | What to record |
|---|---|---|
| A1200 68060/50 | 640x256x4 or current AGA Workbench | First-frame time, changed tiles, mouse responsiveness |
| A600 PiStorm | Current native ECS Workbench | First-frame time, update smoothness, CPU feel |

Also try delay values 2, 5 and 10. Lower is a faster scan rate and higher CPU
load.

## Expected PR1 behaviour

- The first frame sends every tile.
- An idle Workbench normally sends zero changed tiles.
- Moving one small window updates only tiles intersecting the old and new
  positions.
- Palette changes are visible without requiring a full-frame retransmission.
- Closing the viewer causes the Amiga sender to leave its capture loop.

## Known failure cases to capture

- Picasso96/RTG Workbench: rejected in PR1 if depth is over 8; 8-bit RTG is
  not yet guaranteed safe.
- Interleaved bitmap: rejected.
- Screen-mode change while connected: restart the server and viewer.
- Copper effects, hardware sprites, dual playfields and HAM are not represented
  by this simple Workbench bitmap capture.

