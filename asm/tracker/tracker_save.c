#include "tracker_save.h"
#include "tracker_mem.h"
#include "tracker_state.h"
#include "tracker_tables.h"

TRK_INLINE u32 trk_save_bit_addr(u32 offset, u16 index) {
  return TRK_SAVE_ADDR + offset + (index >> 3);
}

TRK_INLINE u8 trk_save_bit_mask(u16 index) {
  return (u8)(1 << (index & 7));
}

// Clears the save region and stamps it with this seed. Runs when a new game is started, and when a
// save from another seed (or from before the tracker existed) is loaded.
TRK_EXPORT void trk_save_reset(void) {
  for (u32 i = 0; i < TRK_SAVE_SIZE; i++) {
    trk_mem_write_u8(TRK_SAVE_ADDR + i, 0);
  }
  u16 seed_tag = trk_seed_tag();
  trk_mem_write_u8(TRK_SAVE_ADDR + TRK_SAVE_VERSION, TRK_SAVE_LAYOUT_VERSION);
  trk_mem_write_u8(TRK_SAVE_ADDR + TRK_SAVE_SEED_TAG, (u8)(seed_tag >> 8));
  trk_mem_write_u8(TRK_SAVE_ADDR + TRK_SAVE_SEED_TAG + 1, (u8)seed_tag);
  TRK_STATE->save_resets++;
}

TRK_EXPORT void trk_save_validate(void) {
  if (trk_mem_u8(TRK_SAVE_ADDR + TRK_SAVE_VERSION) != TRK_SAVE_LAYOUT_VERSION
      || trk_mem_u16(TRK_SAVE_ADDR + TRK_SAVE_SEED_TAG) != trk_seed_tag()) {
    trk_save_reset();
  }
}

TRK_EXPORT u8 tracker_small_keys_obtained(int dungeon) {
  return trk_mem_u8(TRK_SAVE_ADDR + TRK_SAVE_KEYS + dungeon);
}

TRK_EXPORT void tracker_count_small_key(int dungeon) {
  if (!trk_tables_valid()) {
    return;
  }
  trk_save_validate();
  u32 addr = TRK_SAVE_ADDR + TRK_SAVE_KEYS + dungeon;
  u8 count = trk_mem_u8(addr);
  if (count < 0xFF) {
    trk_mem_write_u8(addr, count + 1);
  }
}

TRK_EXPORT bool tracker_is_manual(u16 location_index) {
  if (location_index >= TRK_MAX_LOCATIONS) {
    return false;
  }
  return (trk_mem_u8(trk_save_bit_addr(TRK_SAVE_MANUAL_BITS, location_index)) & trk_save_bit_mask(location_index)) != 0;
}

// Returns the new state.
bool trk_save_toggle_manual(u16 location_index) {
  u32 addr = trk_save_bit_addr(TRK_SAVE_MANUAL_BITS, location_index);
  u8 value = trk_mem_u8(addr) ^ trk_save_bit_mask(location_index);
  trk_mem_write_u8(addr, value);
  return (value & trk_save_bit_mask(location_index)) != 0;
}

TRK_EXPORT bool tracker_is_entrance_visited(u16 entrance_index) {
  if (entrance_index >= TRK_MAX_ENTRANCES) {
    return false;
  }
  return (trk_mem_u8(trk_save_bit_addr(TRK_SAVE_VISITED_BITS, entrance_index)) & trk_save_bit_mask(entrance_index)) != 0;
}

void trk_save_set_entrance_visited(u16 entrance_index) {
  u32 addr = trk_save_bit_addr(TRK_SAVE_VISITED_BITS, entrance_index);
  trk_mem_write_u8(addr, trk_mem_u8(addr) | trk_save_bit_mask(entrance_index));
}
