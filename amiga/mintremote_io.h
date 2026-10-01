#ifndef MINTREMOTE_IO_H
#define MINTREMOTE_IO_H

/* Portable retry loop: socket and GUI operations are supplied by the caller. */
#define MR_IO_FATAL 0
#define MR_IO_RETRY 1
#define MR_IO_WAIT  2

struct MRWriteOps {
    void *context;
    long (*write)(void *, const unsigned char *, unsigned long);
    int (*error)(void *);
    int (*wait)(void *);
    int (*stopped)(void *);
};

static int mr_write_all(const struct MRWriteOps *ops,
                        const unsigned char *data, unsigned long length)
{
    unsigned long offset = 0;
    while (offset < length) {
        unsigned long left = length - offset;
        long written;
        int error;
        if (ops->stopped(ops->context)) return 0;
        written = ops->write(ops->context, data + offset,
                             left > 16384UL ? 16384UL : left);
        if (written > 0) {
            offset += (unsigned long)written;
            continue;
        }
        if (written == 0) return 0;
        error = ops->error(ops->context);
        if (error == MR_IO_RETRY) continue;
        if (error != MR_IO_WAIT || !ops->wait(ops->context)) return 0;
    }
    return 1;
}

#endif
