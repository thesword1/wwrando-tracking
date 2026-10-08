// Host-only glue for the unit tests (test/test_tracker_c.py): a mock RAM buffer standing in for
// 0x80000000-0x817FFFFF, and a settable pointer to the tables.

#include "tracker_mem.h"

static u8 trk_host_ram_buffer[TRK_RAM_SIZE];
u8* trk_host_ram = trk_host_ram_buffer;
const u8* trk_host_data;

TRK_EXPORT u8* trk_host_ram_base(void) {
  return trk_host_ram_buffer;
}

TRK_EXPORT void trk_host_set_data(const u8* data) {
  trk_host_data = data;
}

TRK_EXPORT void trk_host_reset_ram(void) {
  for (u32 i = 0; i < TRK_RAM_SIZE; i++) {
    trk_host_ram_buffer[i] = 0;
  }
}
