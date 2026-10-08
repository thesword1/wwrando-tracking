// Automatic check detection. Mirrors Archipelago's TWWClient.py (check_regular_location,
// check_special_location and check_locations); tracker/locations.py resolves each location to the
// byte and mask tested here.

#include "tracker_detect.h"
#include "tracker_mem.h"
#include "tracker_save.h"
#include "tracker_tables.h"

#define TRK_SAVED_STAGE_INFO_ADDR 0x803C4F88
#define TRK_LIVE_STAGE_INFO_ADDR 0x803C5380
#define TRK_STAGE_INFO_SIZE 0x24
#define TRK_CURRENT_STAGE_ID_ADDR 0x803C53A4

#define TRK_DELIVERY_BAG_ADDR 0x803C4C8E
#define TRK_DELIVERY_BAG_OWNED_ADDR 0x803C4C98
#define TRK_MOBLINS_LETTER 0x9B
#define TRK_TINGLE_STATUE_1_ADDR 0x803C523E
#define TRK_TINGLE_STATUE_2_ADDR 0x803C5249

TRK_INLINE bool trk_bits_set(u32 addr, u8 mask) {
  return mask != 0 && (trk_mem_u8(addr) & mask) == mask;
}

static bool trk_is_special_checked(const TrkLocation* loc) {
  switch (loc->special) {
    case TRK_SPECIAL_MAGGIE_DELIVERY: {
      // The reward's flag is unknown: checked once Moblin's Letter was owned and is no longer in the
      // delivery bag.
      if (((trk_mem_u32(TRK_DELIVERY_BAG_OWNED_ADDR) >> 15) & 1) == 0) {
        return false;
      }
      for (u32 i = 0; i < 8; i++) {
        if (trk_mem_u8(TRK_DELIVERY_BAG_ADDR + i) == TRK_MOBLINS_LETTER) {
          return false;
        }
      }
      return true;
    }
    case TRK_SPECIAL_ANKLE_ALL_STATUES:
      return trk_bits_set(TRK_TINGLE_STATUE_1_ADDR, 0x40) && trk_bits_set(TRK_TINGLE_STATUE_2_ADDR, 0x0F);
    case TRK_SPECIAL_LENZO_ASSISTANT:
    case TRK_SPECIAL_LETTER_HOSKITS_GIRLFRIEND:
    case TRK_SPECIAL_LETTER_BAITOS_MOTHER:
    case TRK_SPECIAL_LETTER_GRANDMA:
      // All bits of the mask (0x06 for Lenzo, 0x03 for the letters).
      return trk_bits_set(loc->address, loc->mask);
    default:
      return false;
  }
}

TRK_EXPORT bool tracker_is_auto_checked(u16 location_index) {
  if (!trk_tables_valid() || location_index >= trk_count(TRK_SEC_LOCATIONS)) {
    return false;
  }
  TrkLocation loc;
  trk_get_location(location_index, &loc);
  switch (loc.type) {
    case TRK_TYPE_CHART:
    case TRK_TYPE_BOCTO:
    case TRK_TYPE_EVENT:
      return trk_bits_set(loc.address, loc.mask);
    case TRK_TYPE_CHEST:
    case TRK_TYPE_SWTCH:
    case TRK_TYPE_PCKUP:
      if (trk_bits_set(loc.address, loc.mask)) {
        return true;
      }
      // While the player is in the location's stage, its flags are in the live copy and only reach
      // the saved copy when the stage is left.
      if (trk_mem_u8(TRK_CURRENT_STAGE_ID_ADDR) == loc.stage_id) {
        u32 offset = loc.address - (TRK_SAVED_STAGE_INFO_ADDR + TRK_STAGE_INFO_SIZE*loc.stage_id);
        return trk_bits_set(TRK_LIVE_STAGE_INFO_ADDR + offset, loc.mask);
      }
      return false;
    case TRK_TYPE_SPECL:
      return trk_is_special_checked(&loc);
    default:
      return false;
  }
}

TRK_EXPORT bool tracker_is_checked(u16 location_index) {
  return tracker_is_auto_checked(location_index) || tracker_is_manual(location_index);
}

// Manual marks only apply to locations that aren't auto-detected; an auto-detected check stays
// checked. Returns whether the mark changed.
TRK_EXPORT bool tracker_toggle_manual(u16 location_index) {
  if (!trk_tables_valid() || location_index >= trk_count(TRK_SEC_LOCATIONS)) {
    return false;
  }
  if (tracker_is_auto_checked(location_index)) {
    return false;
  }
  trk_save_toggle_manual(location_index);
  return true;
}

TRK_EXPORT void tracker_group_counts(u16 group_index, u16* checked, u16* total) {
  TrkGroup group;
  trk_get_group(group_index, &group);
  u16 count = 0;
  for (u16 i = 0; i < group.num_locations; i++) {
    if (tracker_is_checked(group.first_location + i)) {
      count++;
    }
  }
  *checked = count;
  *total = group.num_locations;
}
