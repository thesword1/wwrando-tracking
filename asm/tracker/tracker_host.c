// Host-only glue for the unit tests (test/test_tracker_c*.py): a mock RAM buffer standing in for
// 0x80000000-0x817FFFFF, a settable pointer to the tables, and the runtime state.

#include "tracker_mem.h"
#include "tracker_state.h"
#include "tracker_ui.h"

static u8 trk_host_ram_buffer[TRK_RAM_SIZE];
u8* trk_host_ram = trk_host_ram_buffer;
const u8* trk_host_data;
TrkState trk_host_state;
TrkUiState trk_host_ui_state;

TRK_EXPORT u8* trk_host_ram_base(void) {
  return trk_host_ram_buffer;
}

TRK_EXPORT TrkState* trk_host_state_ptr(void) {
  return &trk_host_state;
}

TRK_EXPORT TrkUiState* trk_host_ui_state_ptr(void) {
  return &trk_host_ui_state;
}

TRK_EXPORT void trk_host_set_data(const u8* data) {
  trk_host_data = data;
}

// Clears the mock RAM and the runtime state (which is zeroed in main.dol).
TRK_EXPORT void trk_host_reset_ram(void) {
  for (u32 i = 0; i < TRK_RAM_SIZE; i++) {
    trk_host_ram_buffer[i] = 0;
  }
  u8* state = (u8*)&trk_host_state;
  for (u32 i = 0; i < sizeof(trk_host_state); i++) {
    state[i] = 0;
  }
  u8* ui_state = (u8*)&trk_host_ui_state;
  for (u32 i = 0; i < sizeof(trk_host_ui_state); i++) {
    ui_state[i] = 0;
  }
}
