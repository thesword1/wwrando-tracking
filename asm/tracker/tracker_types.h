// Basic types for the tracker runtime. The code is freestanding: nothing from libc is used, so the
// same sources build for the game (devkitPPC, through asm/patches/tracker.asm) and for host tests.

#ifndef TRACKER_TYPES_H
#define TRACKER_TYPES_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef signed short s16;
typedef signed int s32;

#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 202311L
typedef _Bool bool;
#define true 1
#define false 0
#endif

#define NULL ((void*)0)

// asm/assemble.py compiles with -fno-inline, which still honours always_inline.
#define TRK_INLINE static inline __attribute__((always_inline))

#ifdef TRACKER_HOST
#define TRK_EXPORT __attribute__((visibility("default")))
#else
#define TRK_EXPORT
#endif

#endif
