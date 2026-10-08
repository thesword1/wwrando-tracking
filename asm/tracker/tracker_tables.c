#include "tracker_tables.h"
#include "tracker_mem.h"

TRK_INLINE const u8* trk_dir_entry(int section) {
  return TRK_DATA + TRK_HEADER_SIZE + section*TRK_DIR_ENTRY_SIZE;
}

TRK_EXPORT bool trk_tables_valid(void) {
  if (trk_be32(TRK_DATA) != TRK_MAGIC) {
    return false;
  }
  if (trk_be16(TRK_DATA + 4) != TRK_FORMAT_VERSION) {
    return false;
  }
  return trk_be16(TRK_DATA + 0x0C) >= TRK_NUM_SECTIONS;
}

TRK_EXPORT u16 trk_seed_tag(void) {
  return trk_be16(TRK_DATA + 6);
}

TRK_EXPORT u16 trk_table_flags(void) {
  return trk_be16(TRK_DATA + 0x0E);
}

TRK_EXPORT u16 trk_count(int section) {
  return trk_be16(trk_dir_entry(section) + 4);
}

TRK_EXPORT const u8* trk_section(int section) {
  return TRK_DATA + trk_be32(trk_dir_entry(section));
}

TRK_INLINE const u8* trk_entry(int section, u16 index) {
  return trk_section(section) + index*trk_be16(trk_dir_entry(section) + 6);
}

TRK_EXPORT const char* trk_string(u16 offset) {
  return (const char*)trk_section(TRK_SEC_STRINGS) + offset;
}

TRK_EXPORT void trk_get_location(u16 index, TrkLocation* out) {
  const u8* p = trk_entry(TRK_SEC_LOCATIONS, index);
  out->group_id = p[0];
  out->type = p[1];
  out->stage_id = p[2];
  out->mask = p[3];
  out->address = trk_be32(p + 4);
  out->name = trk_be16(p + 8);
  out->special = p[10];
  out->flags = p[11];
}

TRK_EXPORT void trk_get_group(u16 index, TrkGroup* out) {
  const u8* p = trk_entry(TRK_SEC_GROUPS, index);
  out->id = p[0];
  out->kind = p[1];
  out->first_location = trk_be16(p + 2);
  out->num_locations = trk_be16(p + 4);
  out->name = trk_be16(p + 6);
}

TRK_EXPORT int trk_find_group(u8 group_id) {
  u16 count = trk_count(TRK_SEC_GROUPS);
  for (u16 i = 0; i < count; i++) {
    if (trk_entry(TRK_SEC_GROUPS, i)[0] == group_id) {
      return i;
    }
  }
  return -1;
}

TRK_EXPORT void trk_get_entrance(u16 index, TrkEntrance* out) {
  const u8* p = trk_entry(TRK_SEC_ENTRANCES, index);
  out->island_number = p[0];
  out->parent_group = p[1];
  out->exit_group = p[2];
  out->category = p[3];
  out->entrance_name = trk_be16(p + 4);
  out->exit_name = trk_be16(p + 6);
}

TRK_EXPORT void trk_get_trigger(u16 index, TrkTrigger* out) {
  const u8* p = trk_entry(TRK_SEC_TRIGGERS, index);
  for (int i = 0; i < 8; i++) {
    out->stage_name[i] = (char)p[i];
  }
  out->room = p[8];
  out->spawn = p[9];
  out->entrance_index = p[10];
}

TRK_EXPORT void trk_get_chart(u16 index, TrkChart* out) {
  const u8* p = trk_entry(TRK_SEC_CHARTS, index);
  out->destination_square = p[0];
  out->vanilla_square = p[1];
  out->chart_number = p[2];
  out->item_id = p[3];
  out->owned_offset = p[4];
  out->owned_mask = p[5];
  out->salvaged_offset = p[6];
  out->salvaged_mask = p[7];
  out->name = trk_be16(p + 8);
}

TRK_EXPORT void trk_get_stage(u16 index, TrkStage* out) {
  const u8* p = trk_entry(TRK_SEC_STAGES, index);
  for (int i = 0; i < 8; i++) {
    out->stage_name[i] = (char)p[i];
  }
  out->group_id = p[8];
}
