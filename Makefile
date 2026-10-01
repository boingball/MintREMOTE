CROSS   ?= m68k-amigaos-
CC       = $(CROSS)gcc
PYTHON  ?= python3
CFLAGS  ?= -Os -m68000 -Wall -Wextra -fomit-frame-pointer -fno-builtin

.PHONY: all check clean

all: MintRemoteServer

MintRemoteServer: amiga/mintremote_server.c amiga/mintremote_gui.c amiga/mintremote_gui.h amiga/mintremote_io.h amiga/mintremote_protocol.h
	$(CC) $(CFLAGS) -Iamiga -o $@ amiga/mintremote_server.c amiga/mintremote_gui.c -lamiga

check:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -f MintRemoteServer
	rm -rf viewer/__pycache__ tests/__pycache__ tools/__pycache__
