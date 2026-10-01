# MintREMOTE server status window

Build with `make` or use the `MintRemoteServer-AmigaOS` CI artifact. Copy
`MintRemoteServer` and `MintRemoteServer.info` to the same drawer on an
AmigaOS 3.1+ machine with native planar Workbench and an active
AmiTCP-compatible stack (e.g. Roadshow or Miami).

## Workbench start

W1. Double-click the **MintRemoteServer** icon. Check that only the
    **MintREMOTE** GadTools window opens, centred on the screen, and that no
    console/Shell window appears at any point (including on connect and
    disconnect).
W2. Check the window shows **Listening for a PC viewer**, the address and port,
    **View only** and the screen size/colours. **Disconnect** is ghosted.
W3. Click **Quit**. The window closes and the task exits (check with a task
    monitor such as Scout or `Status`). Repeat with the close gadget, Esc, `Q`
    and **Project > Quit**.
W4. Edit the icon's ToolTypes to `PORT=5910` and `INPUT` (no brackets). Start
    it and check the displayed port and **Remote input enabled**. Set
    `PORT=abc` and check a requester reports the invalid ToolType and the
    program exits.
W5. Stop the TCP/IP stack and start the server. A requester must explain that
    bsdsocket.library is missing; no console window opens. Start two servers
    on the same port and check the second reports the port is in use.
W6. Connect the PC viewer. Check **PC connected: <PC address>** and that
    **Disconnect** becomes available. Click **Disconnect** (and later try `D`
    and the menu item): the viewer sees the connection close, the window
    returns to **Listening**, and the viewer can reconnect.
W7. Open **Project > About...** while a viewer is connected. The viewer must
    keep updating while the requester is open. Close it with **OK**, and also
    quit with the About requester still open.

## Shell start

The existing `PORT/N,DELAY/N,INPUT/S` arguments still apply.

1. Start `MintRemoteServer`. Check the title is **MintREMOTE**, with a green
   running dot, **Listening for a PC viewer**, a local IPv4 address and port,
   and **View only**.
   Compare the address with the stack's interface configuration. The server
   listens on all IPv4 interfaces; up to four distinct non-loopback addresses
   are shown. A limited Workbench palette may approximate the green colour.
2. Cover/uncover and drag the window. Check the text and dot redraw correctly.
   Use the depth gadget. Test both a four-colour screen and an AGA screen.
3. Close the window before connecting a viewer. Check the task exits, the window
   disappears and port 5909 can immediately be used by a newly started server.
4. Connect the PC viewer to the displayed address. Check **PC connected**, live
   display updates and unchanged protocol behaviour. Disconnect; check
   **Listening**, then reconnect without restarting the server.
5. Close during capture. Check the viewer detects the closed connection and
   the server exits. Repeat with a client that connects but never reads data:
   the close gadget must still stop the blocked send promptly.
6. Run `MintRemoteServer PORT=5910 DELAY=250 INPUT`. Check the displayed port
   and **Remote input enabled**. Hold a remote key/button and close the window,
   then verify Amiga input is released. Also test disconnect/reconnect with a
   held key/button and verify no input remains held or buffered between clients.
7. Use Ctrl-C in the Shell while listening (nobody connected) and while
   connected. Each must stop the server promptly with the same cleanup.
   Previously the TCP stack consumed Ctrl-C while waiting for a viewer.
8. Test with multiple active interfaces and a loopback interface. Only distinct
   active non-loopback IPv4 addresses should appear. If the stack cannot supply
   interface addresses, the window should explicitly say **IP unavailable**;
   it must not present 0.0.0.0 as an address to connect to.

Host tests exercise the same send loop used by the server: partial writes,
would-block retry, interrupted writes, peer closure, fatal errors, and quitting
during a writable-socket wait. GadTools drawing and socket-stack integration
still need the above Amiga hardware/emulator checks.
The tests also decode old and BSD IPv4 interface records, skip extended
non-IPv4 records, and reject truncated, unspecified and loopback addresses.
