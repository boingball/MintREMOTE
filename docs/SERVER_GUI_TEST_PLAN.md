# MintREMOTE server status window

Build with `make` or use the `MintRemoteServer-AmigaOS` CI artifact. Copy the
executable to an AmigaOS 3.1+ machine with native planar Workbench and an active
AmiTCP-compatible stack (e.g. Roadshow or Miami). Launch from Shell; the existing
`PORT/N,DELAY/N,INPUT/S` arguments still apply.

1. Start `MintRemoteServer`. Check the title is **MintREMOTE**, with a green
   running dot, **Listening**, a local IPv4 address and port, and **View only**.
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
7. Use Ctrl-C while listening and while connected. Check the same cleanup.
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
