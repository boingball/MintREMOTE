# PR2 remote-input test plan

## Start the input-enabled server

On a native planar Workbench, run:

```text
MintRemoteServer 5909 5 INPUT
```

The equivalent AmigaDOS forms `MintRemoteServer INPUT` and
`MintRemoteServer PORT=5909 DELAY=5 INPUT` must also enable input.

Connect the Python viewer and click inside its Amiga display to give it
keyboard focus.

## Mouse checks

1. Move to all four edges and confirm the Amiga pointer reaches them.
2. Single-click and double-click Workbench icons.
3. Drag a window continuously across the display and release it.
4. Open a menu with the right button and choose an item with the left.
5. Move the pointer quickly while a window is updating; input should remain
   responsive and screen streaming should not regress.
6. Alt-tab away from the viewer while holding a button and confirm it is not
   left stuck down on the Amiga.
7. Rapidly double-click a window, drag it, and release both inside and outside
   the viewer. Repeat this several times; the drag must never remain latched,
   and later mouse movement must not replay as a delayed burst.

## Keyboard checks

1. Open a Shell and type lower-case letters, capitals, digits and punctuation.
2. Test Return, Backspace, Delete, Tab, Escape and all four arrow keys.
3. Test Ctrl-C, Left-Amiga combinations and F1 through F10.
4. Hold a key to check repeat behaviour, then release it.
5. Alt-tab away while holding Shift and confirm Shift is released remotely.

The first key mapping targets standard UK/US Workbench use. Record any key
whose printed character does not match; that will identify differences between
the Windows/Tk key name and the active Amiga keymap.

## Safety and failure checks

- Running without `INPUT` must advertise view-only mode and ignore local PC
  interaction.
- Closing the viewer must release all tracked keys and buttons.
- A malformed input packet must close the client connection rather than feed
  unchecked data to `input.device`.
- Do not expose TCP port 5909 outside a trusted LAN; there is no authentication
  or encryption yet.
