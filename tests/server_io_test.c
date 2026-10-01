/* Exercise the server's actual send loop without Amiga libraries. */
#include <assert.h>
#include <string.h>
#include "mintremote_io.h"

struct Fake {
    unsigned char output[40000];
    unsigned long used;
    int calls, waits, stopped, mode;
};

static long write_data(void *context, const unsigned char *data,
                        unsigned long length)
{
    struct Fake *fake = context;
    ++fake->calls;
    assert(length <= 16384UL);
    if (fake->mode && fake->calls == 2) return -1;
    if (fake->mode == 5) return 0;
    if (length > 7) length = 7; /* Many short writes, including after retry. */
    memcpy(fake->output + fake->used, data, length);
    fake->used += length;
    return (long)length;
}

static int error_kind(void *context)
{
    struct Fake *fake = context;
    if (fake->mode == 1 || fake->mode == 2) return MR_IO_WAIT;
    if (fake->mode == 3) return MR_IO_RETRY;
    return MR_IO_FATAL;
}

static int wait_ready(void *context)
{
    struct Fake *fake = context;
    ++fake->waits;
    if (fake->mode == 2) { fake->stopped = 1; return 0; }
    return 1;
}

static int is_stopped(void *context)
{
    return ((struct Fake *)context)->stopped;
}

int main(void)
{
    unsigned char source[35000];
    struct Fake fake;
    struct MRWriteOps ops = {&fake, write_data, error_kind, wait_ready, is_stopped};
    unsigned long i;
    int mode;
    for (i = 0; i < sizeof(source); ++i) source[i] = (unsigned char)i;
    for (mode = 0; mode <= 5; ++mode) {
        int result;
        memset(&fake, 0, sizeof(fake));
        fake.mode = mode;
        result = mr_write_all(&ops, source, sizeof(source));
        if (mode == 0 || mode == 1 || mode == 3) {
            assert(result == 1);
            assert(fake.used == sizeof(source));
            assert(memcmp(fake.output, source, sizeof(source)) == 0);
            assert(fake.waits == (mode == 1 ? 1 : 0));
        } else {
            assert(result == 0);
            assert(fake.calls == (mode == 5 ? 1 : 2));
            assert(fake.used == (mode == 5 ? 0 : 7));
            assert(fake.waits == (mode == 2 ? 1 : 0));
        }
    }
    memset(&fake, 0, sizeof(fake));
    fake.stopped = 1;
    assert(!mr_write_all(&ops, source, sizeof(source)));
    assert(fake.calls == 0);
    return 0;
}
