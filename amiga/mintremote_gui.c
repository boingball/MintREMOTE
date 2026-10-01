/* Small Workbench status window, using the MintVID GadTools conventions. */
#include <exec/libraries.h>
#include <intuition/intuition.h>
#include <libraries/gadtools.h>
#include <graphics/gfxbase.h>
#include <graphics/text.h>
#include <graphics/view.h>
#include <proto/exec.h>
#include <proto/intuition.h>
#include <proto/graphics.h>
#include <proto/gadtools.h>
#include <string.h>

#include "mintremote_gui.h"

struct Library *GadToolsBase = NULL;
extern struct IntuitionBase *IntuitionBase;
extern struct GfxBase *GfxBase;

static struct Window *window;
static struct Gadget *gadgets, *status_gadget;
static APTR visual;
static struct Screen *public_screen;
static struct DrawInfo *draw_info;
static LONG green_pen = -1;
static int quit;
static struct TextAttr text_attr = {(STRPTR)"topaz.font", 8, 0, 0};

static void draw_dot(void)
{
    /* Filled 11-pixel circle; no temporary area raster or shared palette edits. */
    static const UBYTE half_width[11] = {2, 3, 4, 5, 5, 5, 5, 5, 4, 3, 2};
    WORD row, x = window->BorderLeft + 13, y = window->BorderTop + 8;
    SetAPen(window->RPort, green_pen >= 0 ? (ULONG)green_pen :
            draw_info->dri_Pens[HIGHLIGHTTEXTPEN]);
    for (row = 0; row < 11; ++row)
        RectFill(window->RPort, x - half_width[row], y + row,
                 x + half_width[row], y + row);
}

static struct Gadget *add_text(struct Gadget *previous, UWORD x, UWORD y,
                               UWORD width, const char *text)
{
    struct NewGadget ng;
    memset(&ng, 0, sizeof(ng));
    ng.ng_LeftEdge = public_screen->WBorLeft + x;
    ng.ng_TopEdge = public_screen->WBorTop +
        public_screen->Font->ta_YSize + 1 + y;
    ng.ng_Width = width;
    ng.ng_Height = 12;
    ng.ng_TextAttr = &text_attr;
    ng.ng_VisualInfo = visual;
    return CreateGadget(TEXT_KIND, previous, &ng,
                         GTTX_Text, (ULONG)text, TAG_DONE);
}

int mr_gui_open(struct Screen *screen,
                char addresses[MR_MAX_ADDRESSES][MR_ADDRESS_TEXT_BYTES],
                UWORD count, int input_enabled)
{
    struct Gadget *previous;
    UWORD i;
    const char *mode = input_enabled ? "Remote input enabled" : "View only";
    public_screen = screen;
    quit = 0;
    GadToolsBase = OpenLibrary((CONST_STRPTR)"gadtools.library", 39);
    if (!GadToolsBase) goto failed;
    visual = GetVisualInfoA(screen, NULL);
    draw_info = GetScreenDrawInfo(screen);
    if (!visual || !draw_info) goto failed;
    green_pen = ObtainBestPenA(screen->ViewPort.ColorMap,
                               0, 0xffffffffUL, 0, NULL);
    previous = CreateContext(&gadgets);
    if (!previous) goto failed;
    status_gadget = previous = add_text(previous, 28, 8, 260, "Listening");
    if (!previous) goto failed;
    for (i = 0; i < count; ++i) {
        previous = add_text(previous, 8, 28 + i * 16, 280, addresses[i]);
        if (!previous) goto failed;
    }
    previous = add_text(previous, 8, 34 + count * 16, 280, mode);
    if (!previous) goto failed;
    window = OpenWindowTags(NULL,
        WA_PubScreen, (ULONG)screen,
        WA_Title, (ULONG)"MintREMOTE",
        WA_InnerWidth, 296,
        WA_InnerHeight, 54 + count * 16,
        WA_Gadgets, (ULONG)gadgets,
        WA_CloseGadget, TRUE,
        WA_DragBar, TRUE,
        WA_DepthGadget, TRUE,
        WA_Activate, TRUE,
        WA_SimpleRefresh, TRUE,
        WA_IDCMP, IDCMP_CLOSEWINDOW | IDCMP_REFRESHWINDOW,
        TAG_DONE);
    if (!window) goto failed;
    GT_RefreshWindow(window, NULL);
    draw_dot();
    return 1;
failed:
    mr_gui_close();
    return 0;
}

void mr_gui_connected(int connected)
{
    if (window)
        GT_SetGadgetAttrs(status_gadget, window, NULL,
            GTTX_Text, (ULONG)(connected ? "PC connected" : "Listening"),
            TAG_DONE);
}

int mr_gui_poll(void)
{
    struct IntuiMessage *message;
    if (!window) return quit;
    while ((message = GT_GetIMsg(window->UserPort)) != NULL) {
        ULONG message_class = message->Class;
        GT_ReplyIMsg(message);
        if (message_class == IDCMP_CLOSEWINDOW) quit = 1;
        else if (message_class == IDCMP_REFRESHWINDOW) {
            GT_BeginRefresh(window);
            draw_dot();
            GT_EndRefresh(window, TRUE);
        }
    }
    return quit;
}

ULONG mr_gui_signal(void)
{
    return window ? 1UL << window->UserPort->mp_SigBit : 0;
}

void mr_gui_close(void)
{
    if (window) { CloseWindow(window); window = NULL; }
    if (gadgets) { FreeGadgets(gadgets); gadgets = status_gadget = NULL; }
    if (visual) { FreeVisualInfo(visual); visual = NULL; }
    if (green_pen >= 0) {
        ReleasePen(public_screen->ViewPort.ColorMap, (ULONG)green_pen);
        green_pen = -1;
    }
    if (draw_info) {
        FreeScreenDrawInfo(public_screen, draw_info);
        draw_info = NULL;
    }
    if (GadToolsBase) { CloseLibrary(GadToolsBase); GadToolsBase = NULL; }
    public_screen = NULL;
}
