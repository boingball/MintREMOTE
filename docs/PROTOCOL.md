# MintREMOTE PR1 protocol

All multi-byte integers are unsigned and big-endian. This matches the native
680x0 byte order and keeps the Amiga sender simple.

## Handshake

The server sends exactly 20 bytes after accepting a connection:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | 4 bytes | Magic `MRM1` |
| 4 | u16 | Protocol version, currently 1 |
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
| u8 | Flags, zero in PR1 |
| u16 | Payload length |

Unknown types or non-zero flags are protocol errors in PR1.

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

Reserved for a graceful server shutdown. PR1 normally ends the TCP connection.

## Deliberate omissions

PR1 has no client-to-server messages, compression, authentication, encryption,
acknowledgements or screen-mode-change message. Those are not accidentally
missing: the first test is intended to measure native planar capture cost,
changed-tile behaviour and real TCP throughput before the protocol grows.

