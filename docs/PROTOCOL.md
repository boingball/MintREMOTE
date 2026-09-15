# MintREMOTE protocol version 2

All multi-byte integers are unsigned and big-endian. This matches the native
680x0 byte order and keeps the Amiga sender simple.

## Handshake

The server sends exactly 20 bytes after accepting a connection:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | 4 bytes | Magic `MRM1` |
| 4 | u16 | Protocol version, currently 2 |
| 6 | u16 | Screen width |
| 8 | u16 | Screen height |
| 10 | u16 | Nominal tile width |
| 12 | u16 | Nominal tile height |
| 14 | u16 | Bitplane depth, 1-8 |
| 16 | u16 | Pixel format, 1 = planar indexed |
| 18 | u16 | Palette entry count, `1 << depth` |

## Message framing

Every subsequent message starts with:

| Type | Meaning |
|---|---|
| u8 | Message type |
| u8 | Flags, currently zero |
| u16 | Payload length |

Non-zero message flags are currently a protocol error.

## Capabilities message: type 5

The server sends this immediately after the handshake. Its payload is a u16
bit field. Bit 0 (`MR_CAP_INPUT`) means the server was launched with remote
input enabled. A viewer must not transmit input when that bit is clear.

## Palette message: type 1

The payload is a u16 entry count followed by three bytes per entry in RGB
order. A palette message is sent before the first tile and whenever the
Workbench colour map changes.

## Tile message: type 2

The payload begins with:

| Type | Meaning |
|---|---|
| u32 | Frame number |
| u16 | X position |
| u16 | Y position |
| u16 | Actual tile width |
| u16 | Actual tile height |
| u16 | Bytes per row per plane |
| u8 | Bitplane depth |
| u8 | Reserved, zero |

Planar bytes immediately follow the 16-byte tile header. They are plane-major,
then row-major within each plane. Bit 7 is the leftmost pixel of each byte.
Plane 0 contributes the least significant bit of the palette index.

The data length is `row_bytes * height * depth`.

## Frame-end message: type 3

| Type | Meaning |
|---|---|
| u32 | Frame number |
| u16 | Number of changed tiles sent |
| u16 | Scan time in milliseconds; zero until timing is implemented |

The viewer presents its updated framebuffer when this message arrives.

## Goodbye message: type 4

Reserved for a graceful server shutdown. The prototype normally ends the TCP
connection.

## Client-to-server input

Input uses the same four-byte message header. The server accepts these only
when its capabilities include `MR_CAP_INPUT`.

### Pointer position: type 128

The four-byte payload is an absolute u16 X coordinate followed by an absolute
u16 Y coordinate. The server clamps both to the captured screen and writes an
`IECLASS_POINTERPOS` event to `input.device`.

### Mouse button: type 129

The two-byte payload contains a button number (1 left, 2 middle, 3 right) and a
state (0 released, 1 pressed).

### Raw key: type 130

The two-byte payload contains an Amiga raw key code from 0 through 127 and a
state (0 released, 1 pressed). The Python viewer maps ordinary PC keys to their
physical Amiga equivalents. Text/Unicode is deliberately not sent because
applications on the Amiga expect raw key events and the Amiga's configured
keymap remains authoritative.

## Deliberate omissions

The protocol still has no compression, authentication, encryption,
acknowledgements, clipboard transfer or screen-mode-change message. It must be
used only on a trusted LAN. Remote input is an explicit server-side option.
