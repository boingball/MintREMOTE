#ifndef MINTREMOTE_GUI_H
#define MINTREMOTE_GUI_H

#include <exec/types.h>
#include <intuition/screens.h>

#define MR_MAX_ADDRESSES 4
#define MR_ADDRESS_TEXT_BYTES 32

/* Events returned by mr_gui_poll(). */
#define MR_GUI_QUIT       1UL
#define MR_GUI_DISCONNECT 2UL

/* Address and screen text must outlive the window's GadTools text gadgets. */
int mr_gui_open(struct Screen *screen,
                char addresses[MR_MAX_ADDRESSES][MR_ADDRESS_TEXT_BYTES],
                UWORD count, int input_enabled, const char *screen_text);
/* NULL peer means listening; otherwise the viewer's address text. */
void mr_gui_connected(const char *peer);
ULONG mr_gui_poll(void);
ULONG mr_gui_signal(void);
/* Requester on the window (or Workbench if no window is open). */
void mr_gui_message(const char *text);
void mr_gui_close(void);

#endif
