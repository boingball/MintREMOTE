#ifndef MINTREMOTE_GUI_H
#define MINTREMOTE_GUI_H

#include <exec/types.h>
#include <intuition/screens.h>

#define MR_MAX_ADDRESSES 4
#define MR_ADDRESS_TEXT_BYTES 32

/* Address storage must outlive the window's GadTools text gadgets. */
int mr_gui_open(struct Screen *screen,
                char addresses[MR_MAX_ADDRESSES][MR_ADDRESS_TEXT_BYTES],
                UWORD count, int input_enabled);
void mr_gui_connected(int connected);
int mr_gui_poll(void);
ULONG mr_gui_signal(void);
void mr_gui_close(void);

#endif
