// Access to game memory and to the patch-time tables.
//
// In the game, addresses are plain pointers and the tables are the tracker_data reserve in
// asm/patches/tracker.asm. In the host build (TRACKER_HOST), game memory is a mock RAM buffer and
// the tables are whatever buffer the test passes in (tracker_host.c), so all game memory access must
// go through these helpers.
//
// Both the game and the tables are big-endian; the helpers read byte by byte so the host build
// doesn't need to byte-swap.

#ifndef TRACKER_MEM_H
#define TRACKER_MEM_H

#include "tracker_types.h"

#define TRK_RAM_BASE 0x80000000
#define TRK_RAM_SIZE 0x01800000

#ifdef TRACKER_HOST
extern u8* trk_host_ram;
extern const u8* trk_host_data;
#define TRK_MEM(addr) (&trk_host_ram[(u32)(addr) - TRK_RAM_BASE])
#define TRK_DATA trk_host_data
#else
extern const u8 tracker_data[];
#define TRK_MEM(addr) ((volatile u8*)(addr))
#define TRK_DATA tracker_data
#endif

TRK_INLINE u8 trk_mem_u8(u32 addr) {
  return *TRK_MEM(addr);
}

TRK_INLINE u16 trk_mem_u16(u32 addr) {
  return (u16)((trk_mem_u8(addr) << 8) | trk_mem_u8(addr + 1));
}

TRK_INLINE u32 trk_mem_u32(u32 addr) {
  return ((u32)trk_mem_u16(addr) << 16) | trk_mem_u16(addr + 2);
}

TRK_INLINE void trk_mem_write_u8(u32 addr, u8 value) {
  *TRK_MEM(addr) = value;
}

TRK_INLINE u16 trk_be16(const u8* p) {
  return (u16)((p[0] << 8) | p[1]);
}

TRK_INLINE u32 trk_be32(const u8* p) {
  return ((u32)trk_be16(p) << 16) | trk_be16(p + 2);
}

#endif
