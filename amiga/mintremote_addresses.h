#ifndef MINTREMOTE_ADDRESSES_H
#define MINTREMOTE_ADDRESSES_H

/* AmiTCP interface records have a 16-byte name followed by a sockaddr.
 * Handle both the old big-endian 16-bit family and BSD length/family layout.
 * Return 1 for a usable IPv4 address, 0 to skip, -1 for a truncated record.
 */
static int mr_read_interface_ipv4(const unsigned char *record,
    unsigned long available, unsigned long *step, unsigned long *address)
{
    const unsigned char *sockaddr;
    unsigned long length;
    if (available < 32) return -1;
    sockaddr = record + 16;
    length = sockaddr[0] > 16 ? sockaddr[0] : 16;
    *step = 16 + length;
    if (*step > available) return -1;
    if (sockaddr[1] != 2) return 0; /* AF_INET on Amiga TCP stacks. */
    *address = ((unsigned long)sockaddr[4] << 24) |
               ((unsigned long)sockaddr[5] << 16) |
               ((unsigned long)sockaddr[6] << 8) | sockaddr[7];
    return *address != 0 && (*address >> 24) != 127;
}

#endif
