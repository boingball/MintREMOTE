/*
 * MintREMOTE PR1 native-planar capture prototype.
 *
 * Captures the public Workbench screen as native bitplane tiles and sends
 * only changed tiles to a single TCP client. The PC performs all planar to
 * RGB conversion. This is deliberately a trusted-LAN, view-only prototype.
 */

#include <exec/types.h>
#include <exec/memory.h>
#include <exec/libraries.h>
#include <dos/dos.h>
#include <intuition/intuition.h>
#include <graphics/gfx.h>
#include <graphics/gfxbase.h>
#include <graphics/view.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/intuition.h>
#include <proto/graphics.h>
#include <sys/types.h>
#include <proto/bsdsocket.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mintremote_protocol.h"

struct Library *SocketBase = NULL;
struct IntuitionBase *IntuitionBase = NULL;
struct GfxBase *GfxBase = NULL;

static void mr_put16(UBYTE *p, UWORD value)
{
    p[0] = (UBYTE)(value >> 8);
    p[1] = (UBYTE)value;
}

static void mr_put32(UBYTE *p, ULONG value)
{
    p[0] = (UBYTE)(value >> 24);
    p[1] = (UBYTE)(value >> 16);
    p[2] = (UBYTE)(value >> 8);
    p[3] = (UBYTE)value;
}

static int mr_send_all(LONG sock, const UBYTE *data, ULONG length)
{
    ULONG sent_total = 0;

    while (sent_total < length) {
        ULONG left = length - sent_total;
        LONG chunk = (LONG)(left > 16384UL ? 16384UL : left);
        LONG sent = send(sock, (char *)(data + sent_total), chunk, 0);
        if (sent <= 0) return 0;
        sent_total += (ULONG)sent;
    }
    return 1;
}

static int mr_send_message_header(LONG sock, UBYTE type, UWORD payload_bytes)
{
    UBYTE header[MR_MESSAGE_HEADER_BYTES];

    header[0] = type;
    header[1] = 0;
    mr_put16(header + 2, payload_bytes);
    return mr_send_all(sock, header, sizeof(header));
}

static int mr_send_handshake(LONG sock, UWORD width, UWORD height,
                             UWORD depth, UWORD palette_entries)
{
    UBYTE hello[MR_HANDSHAKE_BYTES];

    hello[0] = 'M';
    hello[1] = 'R';
    hello[2] = 'M';
    hello[3] = '1';
    mr_put16(hello + 4, MR_PROTOCOL_VERSION);
    mr_put16(hello + 6, width);
    mr_put16(hello + 8, height);
    mr_put16(hello + 10, MR_TILE_WIDTH);
    mr_put16(hello + 12, MR_TILE_HEIGHT);
    mr_put16(hello + 14, depth);
    mr_put16(hello + 16, MR_PIXEL_PLANAR_INDEXED);
    mr_put16(hello + 18, palette_entries);
    return mr_send_all(sock, hello, sizeof(hello));
}

static void mr_capture_palette(struct Screen *screen, UBYTE *rgb,
                               UWORD entries, ULONG *rgb32)
{
    UWORD i;

    if (((struct Library *)GfxBase)->lib_Version >= 39) {
        GetRGB32(screen->ViewPort.ColorMap, 0, (ULONG)entries, rgb32);
        for (i = 0; i < entries; ++i) {
            rgb[i * 3U + 0U] = (UBYTE)(rgb32[i * 3U + 0U] >> 24);
            rgb[i * 3U + 1U] = (UBYTE)(rgb32[i * 3U + 1U] >> 24);
            rgb[i * 3U + 2U] = (UBYTE)(rgb32[i * 3U + 2U] >> 24);
        }
    } else {
        for (i = 0; i < entries; ++i) {
            ULONG value = GetRGB4(screen->ViewPort.ColorMap, (LONG)i);
            rgb[i * 3U + 0U] = (UBYTE)(((value >> 8) & 15U) * 17U);
            rgb[i * 3U + 1U] = (UBYTE)(((value >> 4) & 15U) * 17U);
            rgb[i * 3U + 2U] = (UBYTE)((value & 15U) * 17U);
        }
    }
}

static int mr_send_palette(LONG sock, const UBYTE *rgb, UWORD entries)
{
    UBYTE packet[2 + 256 * 3];
    UWORD bytes = (UWORD)(2U + entries * 3U);

    mr_put16(packet, entries);
    memcpy(packet + 2, rgb, (ULONG)entries * 3UL);
    return mr_send_message_header(sock, MR_MSG_PALETTE, bytes) &&
           mr_send_all(sock, packet, bytes);
}

static ULONG mr_capture_tile(const struct BitMap *bitmap,
                             UWORD x, UWORD y, UWORD width, UWORD height,
                             UWORD depth, UBYTE *output)
{
    UWORD row_bytes = (UWORD)((width + 7U) >> 3);
    UWORD plane;
    UWORD row;
    ULONG pos = 0;

    for (plane = 0; plane < depth; ++plane) {
        PLANEPTR source_plane = bitmap->Planes[plane];
        for (row = 0; row < height; ++row) {
            if (source_plane == NULL) {
                memset(output + pos, 0, row_bytes);
            } else if ((ULONG)source_plane == 0xffffffffUL) {
                memset(output + pos, 0xff, row_bytes);
            } else {
                const UBYTE *source = (const UBYTE *)source_plane +
                    (ULONG)(y + row) * (ULONG)bitmap->BytesPerRow +
                    (ULONG)(x >> 3);
                memcpy(output + pos, source, row_bytes);
            }
            pos += row_bytes;
        }
    }
    return pos;
}

static int mr_send_tile(LONG sock, ULONG frame_id,
                        UWORD x, UWORD y, UWORD width, UWORD height,
                        UWORD row_bytes, UBYTE depth,
                        const UBYTE *data, UWORD data_bytes)
{
    UBYTE header[MR_MESSAGE_HEADER_BYTES + MR_TILE_HEADER_BYTES];
    UWORD payload_bytes = (UWORD)(MR_TILE_HEADER_BYTES + data_bytes);

    header[0] = MR_MSG_TILE;
    header[1] = 0;
    mr_put16(header + 2, payload_bytes);
    mr_put32(header + 4, frame_id);
    mr_put16(header + 8, x);
    mr_put16(header + 10, y);
    mr_put16(header + 12, width);
    mr_put16(header + 14, height);
    mr_put16(header + 16, row_bytes);
    header[18] = depth;
    header[19] = 0;

    return mr_send_all(sock, header, sizeof(header)) &&
           mr_send_all(sock, data, data_bytes);
}

static int mr_send_frame_end(LONG sock, ULONG frame_id, UWORD changed_tiles)
{
    UBYTE payload[8];

    mr_put32(payload, frame_id);
    mr_put16(payload + 4, changed_tiles);
    mr_put16(payload + 6, 0);
    return mr_send_message_header(sock, MR_MSG_FRAME_END, sizeof(payload)) &&
           mr_send_all(sock, payload, sizeof(payload));
}

static int mr_ctrl_c_pressed(void)
{
    return (SetSignal(0L, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C) != 0;
}

static int mr_serve_client(LONG sock, struct Screen *screen, ULONG delay_ticks)
{
    struct BitMap *bitmap = screen->RastPort.BitMap;
    UWORD width = (UWORD)screen->Width;
    UWORD height = (UWORD)screen->Height;
    UWORD depth = (UWORD)bitmap->Depth;
    UWORD palette_entries = (UWORD)(1U << depth);
    UWORD tiles_x = (UWORD)((width + MR_TILE_WIDTH - 1U) / MR_TILE_WIDTH);
    UWORD tiles_y = (UWORD)((height + MR_TILE_HEIGHT - 1U) / MR_TILE_HEIGHT);
    ULONG tile_count = (ULONG)tiles_x * (ULONG)tiles_y;
    ULONG max_tile_bytes =
        (ULONG)(MR_TILE_WIDTH / 8) * MR_TILE_HEIGHT * depth;
    UBYTE *previous = NULL;
    UBYTE *valid = NULL;
    UBYTE *tile = NULL;
    UBYTE *palette = NULL;
    UBYTE *old_palette = NULL;
    ULONG *rgb32 = NULL;
    ULONG frame_id = 1;
    int connected = 0;

    previous = (UBYTE *)AllocVec(tile_count * max_tile_bytes,
                                 MEMF_PUBLIC | MEMF_CLEAR);
    valid = (UBYTE *)AllocVec(tile_count, MEMF_PUBLIC | MEMF_CLEAR);
    tile = (UBYTE *)AllocVec(max_tile_bytes, MEMF_PUBLIC);
    palette = (UBYTE *)AllocVec((ULONG)palette_entries * 3UL, MEMF_PUBLIC);
    old_palette = (UBYTE *)AllocVec((ULONG)palette_entries * 3UL,
                                    MEMF_PUBLIC | MEMF_CLEAR);
    rgb32 = (ULONG *)AllocVec((ULONG)palette_entries * 3UL * sizeof(ULONG),
                              MEMF_PUBLIC);

    if (!previous || !valid || !tile || !palette || !old_palette || !rgb32) {
        printf("Not enough memory for capture buffers.\n");
        goto done;
    }

    if (!mr_send_handshake(sock, width, height, depth, palette_entries))
        goto done;

    printf("Viewer connected: %ux%u, %u bitplanes, %u tiles.\n",
           (unsigned int)width, (unsigned int)height,
           (unsigned int)depth, (unsigned int)tile_count);
    connected = 1;

    while (!mr_ctrl_c_pressed()) {
        UWORD ty;
        UWORD changed = 0;

        mr_capture_palette(screen, palette, palette_entries, rgb32);
        if (frame_id == 1 ||
            memcmp(palette, old_palette, (ULONG)palette_entries * 3UL) != 0) {
            if (!mr_send_palette(sock, palette, palette_entries)) break;
            memcpy(old_palette, palette, (ULONG)palette_entries * 3UL);
        }

        for (ty = 0; ty < tiles_y; ++ty) {
            UWORD tx;
            for (tx = 0; tx < tiles_x; ++tx) {
                UWORD x = (UWORD)(tx * MR_TILE_WIDTH);
                UWORD y = (UWORD)(ty * MR_TILE_HEIGHT);
                UWORD tw = (UWORD)((x + MR_TILE_WIDTH > width)
                    ? width - x : MR_TILE_WIDTH);
                UWORD th = (UWORD)((y + MR_TILE_HEIGHT > height)
                    ? height - y : MR_TILE_HEIGHT);
                UWORD row_bytes = (UWORD)((tw + 7U) >> 3);
                ULONG tile_bytes = mr_capture_tile(bitmap, x, y, tw, th,
                                                   depth, tile);
                ULONG tile_index = (ULONG)ty * tiles_x + tx;
                UBYTE *old_tile = previous + tile_index * max_tile_bytes;

                if (!valid[tile_index] ||
                    memcmp(old_tile, tile, tile_bytes) != 0) {
                    if (!mr_send_tile(sock, frame_id, x, y, tw, th,
                                      row_bytes, (UBYTE)depth, tile,
                                      (UWORD)tile_bytes))
                        goto done;
                    memcpy(old_tile, tile, tile_bytes);
                    valid[tile_index] = 1;
                    ++changed;
                }
            }
        }

        if (!mr_send_frame_end(sock, frame_id, changed)) break;

        if ((frame_id % 50UL) == 0)
            printf("Frame %u: %u changed tiles.\n",
                   (unsigned int)frame_id, (unsigned int)changed);
        ++frame_id;
        Delay(delay_ticks);
    }

done:
    if (rgb32) FreeVec(rgb32);
    if (old_palette) FreeVec(old_palette);
    if (palette) FreeVec(palette);
    if (tile) FreeVec(tile);
    if (valid) FreeVec(valid);
    if (previous) FreeVec(previous);
    if (connected) printf("Viewer disconnected.\n");
    return connected;
}

int main(int argc, char **argv)
{
    LONG listen_sock = -1;
    LONG client_sock = -1;
    struct sockaddr_in address;
    struct Screen *screen = NULL;
    ULONG port = MR_DEFAULT_PORT;
    ULONG delay_ticks = 5;
    LONG reuse = 1;
    int result = 20;

    if (argc > 1) port = (ULONG)atol(argv[1]);
    if (argc > 2) delay_ticks = (ULONG)atol(argv[2]);
    if (port == 0 || port > 65535UL || delay_ticks == 0 || delay_ticks > 250UL) {
        printf("Usage: MintRemoteServer [port 1-65535] [delay_ticks 1-250]\n");
        return 10;
    }

    IntuitionBase = (struct IntuitionBase *)OpenLibrary(
        (CONST_STRPTR)"intuition.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary(
        (CONST_STRPTR)"graphics.library", 37);
    SocketBase = OpenLibrary((CONST_STRPTR)"bsdsocket.library", 4);
    if (!IntuitionBase || !GfxBase || !SocketBase) {
        printf("MintREMOTE requires intuition/graphics v37 and bsdsocket v4.\n");
        goto done;
    }

    screen = LockPubScreen((UBYTE *)"Workbench");
    if (!screen || !screen->RastPort.BitMap) {
        printf("Could not lock the public Workbench screen.\n");
        goto done;
    }
    if (screen->Width <= 0 || screen->Height <= 0 ||
        screen->RastPort.BitMap->Depth == 0 ||
        screen->RastPort.BitMap->Depth > 8) {
        printf("PR1 supports native planar Workbench screens up to 8 bitplanes.\n");
        goto done;
    }
    if (((struct Library *)GfxBase)->lib_Version >= 39 &&
        !(GetBitMapAttr(screen->RastPort.BitMap, BMA_FLAGS) & BMF_STANDARD)) {
        printf("PR1 cannot directly read this RTG/non-standard bitmap.\n");
        goto done;
    }
#ifdef BMF_INTERLEAVED
    if (screen->RastPort.BitMap->Flags & BMF_INTERLEAVED) {
        printf("PR1 does not yet support interleaved bitmaps.\n");
        goto done;
    }
#endif

    listen_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_sock < 0) {
        printf("Could not create TCP socket.\n");
        goto done;
    }
    setsockopt(listen_sock, SOL_SOCKET, SO_REUSEADDR,
               (char *)&reuse, sizeof(reuse));
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons((UWORD)port);
    address.sin_addr.s_addr = INADDR_ANY;

    if (bind(listen_sock, (struct sockaddr *)&address, sizeof(address)) < 0 ||
        listen(listen_sock, 1) < 0) {
        printf("Could not listen on TCP port %u.\n", (unsigned int)port);
        goto done;
    }

    printf("MintREMOTE PR1 waiting on TCP port %u. Ctrl-C stops it.\n",
           (unsigned int)port);
    client_sock = accept(listen_sock, NULL, NULL);
    if (client_sock < 0) {
        printf("Accept failed or was interrupted.\n");
        goto done;
    }

    mr_serve_client(client_sock, screen, delay_ticks);
    result = 0;

done:
    if (client_sock >= 0) CloseSocket(client_sock);
    if (listen_sock >= 0) CloseSocket(listen_sock);
    if (screen) UnlockPubScreen((UBYTE *)"Workbench", screen);
    if (SocketBase) CloseLibrary(SocketBase);
    if (GfxBase) CloseLibrary((struct Library *)GfxBase);
    if (IntuitionBase) CloseLibrary((struct Library *)IntuitionBase);
    return result;
}
