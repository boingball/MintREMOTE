/* Workbench GadTools window: status, addresses, menus and Quit/Disconnect. */
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

#define MR_INNER_WIDTH 304
#define MR_ROW_HEIGHT  14
#define MR_FIRST_ROW   22
#define MR_VALUE_X     84
#define MR_VALUE_WIDTH 212

enum { GID_DISCONNECT = 1, GID_QUIT };
enum { MENU_ABOUT = 1, MENU_DISCONNECT, MENU_QUIT };

static struct Window *window, *about_window;
static struct Gadget *gadgets, *status_gadget, *disconnect_gadget;
static struct Menu *menus;
static APTR visual;
static struct Screen *public_screen;
static struct DrawInfo *draw_info;
static LONG green_pen = -1;
static int connected;
static char status_text[48];
static struct TextAttr text_attr = {(STRPTR)"topaz.font", 8, 0, 0};

static struct NewMenu menu_template[] = {
    {NM_TITLE, (STRPTR)"Project", NULL, 0, 0, NULL},
    {NM_ITEM, (STRPTR)"About...", (STRPTR)"?", 0, 0, (APTR)MENU_ABOUT},
    {NM_ITEM, (STRPTR)"Disconnect viewer", (STRPTR)"D", 0, 0,
     (APTR)MENU_DISCONNECT},
    {NM_ITEM, NM_BARLABEL, NULL, 0, 0, NULL},
    {NM_ITEM, (STRPTR)"Quit", (STRPTR)"Q", 0, 0, (APTR)MENU_QUIT},
    {NM_END, NULL, NULL, 0, 0, NULL}
};

static struct EasyStruct about_request = {
    sizeof(struct EasyStruct), 0, (STRPTR)"About MintREMOTE",
    (STRPTR)"MintREMOTE server\n\n"
            "Remote viewing and control of the\n"
            "Workbench screen from a PC.\n\n"
            "Close this window or choose Quit to stop.",
    (STRPTR)"OK"
};

static void draw_dot(void)
{
    /* Filled 11-pixel circle; no temporary area raster or shared palette edits. */
    static const UBYTE half_width[11] = {2, 3, 4, 5, 5, 5, 5, 5, 4, 3, 2};
    WORD row, x = window->BorderLeft + 14, y = window->BorderTop + 4;
    SetAPen(window->RPort, green_pen >= 0 ? (ULONG)green_pen :
            draw_info->dri_Pens[HIGHLIGHTTEXTPEN]);
    for (row = 0; row < 11; ++row)
        RectFill(window->RPort, x - half_width[row], y + row,
                 x + half_width[row], y + row);
}

static struct Gadget *add_gadget(struct Gadget *previous, ULONG kind,
                                 UWORD x, UWORD y, UWORD width, UWORD height,
                                 const char *label, UWORD id, ULONG tag,
                                 ULONG value)
{
    struct NewGadget ng;
    memset(&ng, 0, sizeof(ng));
    ng.ng_LeftEdge = public_screen->WBorLeft + x;
    ng.ng_TopEdge = public_screen->WBorTop +
        public_screen->Font->ta_YSize + 1 + y;
    ng.ng_Width = width;
    ng.ng_Height = height;
    ng.ng_GadgetText = (STRPTR)label;
    ng.ng_TextAttr = &text_attr;
    ng.ng_GadgetID = id;
    ng.ng_Flags = kind == BUTTON_KIND ? PLACETEXT_IN : PLACETEXT_LEFT;
    ng.ng_VisualInfo = visual;
    return CreateGadget(kind, previous, &ng, tag, value,
                        GT_Underscore, '_', TAG_DONE);
}

static struct Gadget *add_text(struct Gadget *previous, UWORD row,
                               const char *label, const char *text)
{
    return add_gadget(previous, TEXT_KIND, MR_VALUE_X,
                      MR_FIRST_ROW + row * MR_ROW_HEIGHT, MR_VALUE_WIDTH, 12,
                      label, 0, GTTX_Text, (ULONG)text);
}

int mr_gui_open(struct Screen *screen,
                char addresses[MR_MAX_ADDRESSES][MR_ADDRESS_TEXT_BYTES],
                UWORD count, int input_enabled, const char *screen_text)
{
    struct Gadget *previous;
    UWORD i, buttons_y, inner_height, outer_width, outer_height;
    const char *mode = input_enabled ? "Remote input enabled" : "View only";
    public_screen = screen;
    connected = 0;
    GadToolsBase = OpenLibrary((CONST_STRPTR)"gadtools.library", 39);
    if (!GadToolsBase) goto failed;
    visual = GetVisualInfoA(screen, NULL);
    draw_info = GetScreenDrawInfo(screen);
    if (!visual || !draw_info) goto failed;
    green_pen = ObtainBestPenA(screen->ViewPort.ColorMap,
                               0, 0xffffffffUL, 0, NULL);

    previous = CreateContext(&gadgets);
    if (!previous) goto failed;
    status_gadget = previous = add_gadget(previous, TEXT_KIND, 28, 4,
        MR_INNER_WIDTH - 36, 12, NULL, 0, GTTX_Text,
        (ULONG)"Listening for a PC viewer");
    if (!previous) goto failed;
    for (i = 0; i < count; ++i) {
        previous = add_text(previous, i, i == 0 ? "Address" : NULL,
                            addresses[i]);
        if (!previous) goto failed;
    }
    previous = add_text(previous, count, "Mode", mode);
    if (!previous) goto failed;
    previous = add_text(previous, count + 1, "Screen", screen_text);
    if (!previous) goto failed;
    buttons_y = MR_FIRST_ROW + (count + 2) * MR_ROW_HEIGHT + 6;
    disconnect_gadget = previous = add_gadget(previous, BUTTON_KIND, 8,
        buttons_y, 128, 14, "_Disconnect", GID_DISCONNECT, GA_Disabled, TRUE);
    if (!previous) goto failed;
    previous = add_gadget(previous, BUTTON_KIND, MR_INNER_WIDTH - 136,
        buttons_y, 128, 14, "_Quit", GID_QUIT, TAG_IGNORE, 0);
    if (!previous) goto failed;

    menus = CreateMenusA(menu_template, NULL);
    if (!menus || !LayoutMenus(menus, visual,
                               GTMN_NewLookMenus, TRUE, TAG_DONE))
        goto failed;

    inner_height = buttons_y + 14 + 6;
    outer_width = MR_INNER_WIDTH + screen->WBorLeft + screen->WBorRight;
    outer_height = inner_height + screen->WBorTop + screen->Font->ta_YSize +
        1 + screen->WBorBottom;
    window = OpenWindowTags(NULL,
        WA_PubScreen, (ULONG)screen,
        WA_Title, (ULONG)"MintREMOTE",
        WA_ScreenTitle, (ULONG)"MintREMOTE server",
        WA_Left, screen->Width > outer_width ?
            (screen->Width - outer_width) / 2 : 0,
        WA_Top, screen->Height > outer_height ?
            (screen->Height - outer_height) / 2 : 0,
        WA_InnerWidth, MR_INNER_WIDTH,
        WA_InnerHeight, inner_height,
        WA_AutoAdjust, TRUE,
        WA_Gadgets, (ULONG)gadgets,
        WA_CloseGadget, TRUE,
        WA_DragBar, TRUE,
        WA_DepthGadget, TRUE,
        WA_Activate, TRUE,
        WA_SimpleRefresh, TRUE,
        WA_NewLookMenus, TRUE,
        WA_IDCMP, IDCMP_CLOSEWINDOW | IDCMP_REFRESHWINDOW | IDCMP_MENUPICK |
                  IDCMP_VANILLAKEY | BUTTONIDCMP,
        TAG_DONE);
    if (!window) goto failed;
    SetMenuStrip(window, menus);
    GT_RefreshWindow(window, NULL);
    draw_dot();
    return 1;
failed:
    mr_gui_close();
    return 0;
}

void mr_gui_connected(const char *peer)
{
    connected = peer != NULL;
    if (!window) return;
    if (peer) {
        strcpy(status_text, "PC connected: ");
        strncat(status_text, peer, sizeof(status_text) - 15);
    }
    GT_SetGadgetAttrs(status_gadget, window, NULL,
        GTTX_Text, (ULONG)(peer ? status_text : "Listening for a PC viewer"),
        TAG_DONE);
    GT_SetGadgetAttrs(disconnect_gadget, window, NULL,
        GA_Disabled, !connected, TAG_DONE);
}

static ULONG menu_events(UWORD code)
{
    ULONG events = 0;
    while (code != MENUNULL) {
        struct MenuItem *item = ItemAddress(menus, code);
        ULONG id;
        if (!item) break;
        id = (ULONG)GTMENUITEM_USERDATA(item);
        if (id == MENU_QUIT) events |= MR_GUI_QUIT;
        else if (id == MENU_DISCONNECT && connected)
            events |= MR_GUI_DISCONNECT;
        else if (id == MENU_ABOUT && !about_window) {
            /* Non-blocking, so capture and input keep running. */
            about_window = BuildEasyRequestArgs(window, &about_request, 0,
                                                NULL);
            if ((ULONG)about_window <= 1UL) about_window = NULL;
        }
        code = item->NextSelect;
    }
    return events;
}

ULONG mr_gui_poll(void)
{
    struct IntuiMessage *message;
    ULONG events = 0;
    if (!window) return 0;
    if (about_window && SysReqHandler(about_window, NULL, FALSE) != -2) {
        FreeSysRequest(about_window);
        about_window = NULL;
    }
    while ((message = GT_GetIMsg(window->UserPort)) != NULL) {
        ULONG message_class = message->Class;
        UWORD code = message->Code;
        UWORD id = message_class == IDCMP_GADGETUP ?
            ((struct Gadget *)message->IAddress)->GadgetID : 0;
        GT_ReplyIMsg(message);
        if (message_class == IDCMP_CLOSEWINDOW) events |= MR_GUI_QUIT;
        else if (message_class == IDCMP_GADGETUP) {
            if (id == GID_QUIT) events |= MR_GUI_QUIT;
            else if (id == GID_DISCONNECT && connected)
                events |= MR_GUI_DISCONNECT;
        } else if (message_class == IDCMP_MENUPICK) {
            events |= menu_events(code);
        } else if (message_class == IDCMP_VANILLAKEY) {
            if (code == 27 || code == 'q' || code == 'Q')
                events |= MR_GUI_QUIT;
            else if ((code == 'd' || code == 'D') && connected)
                events |= MR_GUI_DISCONNECT;
        } else if (message_class == IDCMP_REFRESHWINDOW) {
            GT_BeginRefresh(window);
            draw_dot();
            GT_EndRefresh(window, TRUE);
        }
    }
    return events;
}

ULONG mr_gui_signal(void)
{
    ULONG signals = window ? 1UL << window->UserPort->mp_SigBit : 0;
    if (about_window) signals |= 1UL << about_window->UserPort->mp_SigBit;
    return signals;
}

void mr_gui_message(const char *text)
{
    struct EasyStruct request = {
        sizeof(struct EasyStruct), 0, (STRPTR)"MintREMOTE",
        (STRPTR)"%s", (STRPTR)"OK"
    };
    ULONG args[1];
    args[0] = (ULONG)text;
    EasyRequestArgs(window, &request, NULL, args);
}

void mr_gui_close(void)
{
    if (about_window) { FreeSysRequest(about_window); about_window = NULL; }
    if (window) {
        ClearMenuStrip(window);
        CloseWindow(window);
        window = NULL;
    }
    if (menus) { FreeMenus(menus); menus = NULL; }
    if (gadgets) {
        FreeGadgets(gadgets);
        gadgets = status_gadget = disconnect_gadget = NULL;
    }
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
    connected = 0;
}
