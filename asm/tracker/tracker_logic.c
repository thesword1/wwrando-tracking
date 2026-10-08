// Logic evaluation for the in-logic colours (D7: on events, not every frame). The bytecode is
// straight-line postfix code computing one result per slot: shared subexpressions first, then one per
// tracked location, then the goal (GO MODE). A full evaluation is one pass over it.
//
// Evaluations run:
// - when the sea chart opens (tracker_ui.c),
// - TRK_LOGIC_ITEM_GET_DELAY frames after an item get (execItemGet, hooked in tracker.asm; covers
//   pickups, chests, shops, NPCs and Archipelago deliveries),
// - when the checked count, the visited entrances or the save data change, and on the first gameplay
//   frame after loading.

#include "tracker_detect.h"
#include "tracker_items.h"
#include "tracker_logic.h"
#include "tracker_mem.h"
#include "tracker_save.h"
#include "tracker_state.h"
#include "tracker_tables.h"

#define TRK_BIT_GET(bits, i) (((bits)[(i) >> 3] >> ((i) & 7)) & 1)
#define TRK_BIT_SET(bits, i, value) \
  ((bits)[(i) >> 3] = (u8)(((bits)[(i) >> 3] & ~(1 << ((i) & 7))) | ((value) << ((i) & 7))))

TRK_INLINE u32 trk_time_base(void) {
#ifdef TRACKER_HOST
  return 0;
#else
  u32 tb;
  __asm__ volatile("mftb %0" : "=r"(tb));
  return tb;
#endif
}

TRK_EXPORT bool tracker_logic_available(void) {
  return TRK_STATE->logic_status == TRK_LOGIC_OK;
}

TRK_EXPORT bool tracker_is_in_logic(u16 location_index) {
  if (!tracker_logic_available() || location_index >= TRK_STATE_MAX_LOCATIONS) {
    return false;
  }
  return TRK_BIT_GET(TRK_STATE->in_logic, location_index);
}

// Whether the seed's goal (Can Reach and Defeat Ganondorf, with the required bosses) is in logic.
TRK_EXPORT bool tracker_go_mode(void) {
  return tracker_logic_available() && TRK_STATE->goal_in_logic;
}

// Runs the bytecode. Returns false if it's malformed (the results are then incomplete).
static bool trk_logic_run(const u8* logic, u16 logic_size, u8* slot_results) {
  TrkState* state = TRK_STATE;
  u16 num_slots = trk_be16(logic);
  u16 num_locations = trk_be16(logic + 2);
  u8 num_items = logic[5];
  u16 code_size = trk_be16(logic + 6);
  u8 num_goals = logic[8];
  if (num_slots > TRK_LOGIC_MAX_SLOTS || num_locations > TRK_STATE_MAX_LOCATIONS
      || num_locations != trk_count(TRK_SEC_LOCATIONS) || num_items > trk_count(TRK_SEC_ITEMS)
      || num_goals > 1 || TRK_LOGIC_HEADER_SIZE + code_size > logic_size) {
    return false;
  }
  const u8* code = logic + TRK_LOGIC_HEADER_SIZE;

  // Item counts don't change during an evaluation; read each once.
  u8 counts[TRK_LOGIC_MAX_ITEMS];
  for (u16 i = 0; i < num_items; i++) {
    counts[i] = tracker_item_count(i);
  }

  u8 stack[TRK_LOGIC_MAX_STACK];
  u16 sp = 0;
  u16 slot = 0;
  u16 pc = 0;
  while (pc < code_size) {
    u8 op = code[pc++];
    u8 value;
    if (op == TRK_OP_END) {
      return sp == 0 && slot == num_slots + num_locations + num_goals;
    } else if (op == TRK_OP_STORE || op == TRK_OP_AND || op == TRK_OP_OR) {
      u16 n = 1;
      if (op != TRK_OP_STORE) {
        if (pc >= code_size) {
          return false;
        }
        n = code[pc++];
      }
      if (n == 0 || n > sp) {
        return false;
      }
      if (op == TRK_OP_STORE) {
        sp--;
        if (slot < num_slots) {
          TRK_BIT_SET(slot_results, slot, stack[sp]);
        } else if (slot < num_slots + num_locations) {
          TRK_BIT_SET(state->in_logic, slot - num_slots, stack[sp]);
        } else if (slot < num_slots + num_locations + num_goals) {
          state->goal_in_logic = stack[sp];
        } else {
          return false;
        }
        slot++;
        continue;
      }
      value = op == TRK_OP_AND;
      for (u16 i = 0; i < n; i++) {
        u8 operand = stack[--sp];
        value = op == TRK_OP_AND ? (value & operand) : (value | operand);
      }
    } else if (op == TRK_OP_TRUE || op == TRK_OP_FALSE) {
      value = op == TRK_OP_TRUE;
    } else if (op == TRK_OP_HAS || op == TRK_OP_HAS1) {
      u16 operand_size = op == TRK_OP_HAS ? 2 : 1;
      if (pc + operand_size > code_size || code[pc] >= num_items) {
        return false;
      }
      u8 needed = op == TRK_OP_HAS ? code[pc + 1] : 1;
      value = counts[code[pc]] >= needed;
      pc += operand_size;
    } else if (op == TRK_OP_CHECKED || op == TRK_OP_CALL) {
      if (pc + 2 > code_size) {
        return false;
      }
      u16 index = trk_be16(code + pc);
      pc += 2;
      if (op == TRK_OP_CHECKED) {
        if (index >= num_locations) {
          return false;
        }
        value = tracker_is_checked(index);
      } else {
        // Only slots already computed can be called.
        if (index >= slot || index >= num_slots) {
          return false;
        }
        value = TRK_BIT_GET(slot_results, index);
      }
    } else if ((op & 0xC0) == TRK_OP_VISITED) {
      value = tracker_is_entrance_visited(op & 0x3F);
    } else {
      return false;
    }
    if (sp >= TRK_LOGIC_MAX_STACK) {
      return false;
    }
    stack[sp++] = value;
  }
  return false;
}

TRK_EXPORT void tracker_logic_evaluate(void) {
  TrkState* state = TRK_STATE;
  u32 start = trk_time_base();
  state->logic_delay = 0;
  state->logic_seen_checked = state->num_checked;
  state->logic_seen_resets = state->save_resets;
  for (u32 i = 0; i < 8; i++) {
    state->logic_seen_visited[i] = trk_mem_u8(TRK_SAVE_ADDR + TRK_SAVE_VISITED_BITS + i);
  }
  for (u32 i = 0; i < sizeof(state->in_logic); i++) {
    state->in_logic[i] = 0;
  }
  state->goal_in_logic = 0;
  u16 logic_size = trk_count(TRK_SEC_LOGIC);
  if (!trk_tables_valid() || logic_size < TRK_LOGIC_HEADER_SIZE) {
    state->logic_status = TRK_LOGIC_NONE;
    return;
  }
  u8 slot_results[TRK_LOGIC_MAX_SLOTS/8];
  if (trk_logic_run(trk_section(TRK_SEC_LOGIC), logic_size, slot_results)) {
    state->logic_status = TRK_LOGIC_OK;
  } else {
    state->logic_status = TRK_LOGIC_ERROR;
    for (u32 i = 0; i < sizeof(state->in_logic); i++) {
      state->in_logic[i] = 0;
    }
    state->goal_in_logic = 0;
  }
  state->logic_evals++;
  state->logic_ticks = trk_time_base() - start;
  if (state->logic_ticks > state->logic_max_ticks) {
    state->logic_max_ticks = state->logic_ticks;
  }
}

// Evaluate after delay_frames frames (1 = on the next tracker_logic_frame). An earlier pending
// request is kept if it's sooner.
TRK_EXPORT void tracker_logic_request(u8 delay_frames) {
  TrkState* state = TRK_STATE;
  if (delay_frames == 0) {
    delay_frames = 1;
  }
  if (state->logic_delay == 0 || delay_frames < state->logic_delay) {
    state->logic_delay = delay_frames;
  }
}

TRK_EXPORT void tracker_on_item_get(void) {
  tracker_logic_request(TRK_LOGIC_ITEM_GET_DELAY);
}

// Per-frame part (from tracker_frame, after the counts are updated): runs requested evaluations and
// notices changes that affect the logic.
TRK_EXPORT void tracker_logic_frame(void) {
  TrkState* state = TRK_STATE;
  bool changed = state->logic_status == TRK_LOGIC_NOT_EVALUATED
    || state->num_checked != state->logic_seen_checked
    || state->save_resets != state->logic_seen_resets;
  for (u32 i = 0; i < 8 && !changed; i++) {
    changed = state->logic_seen_visited[i] != trk_mem_u8(TRK_SAVE_ADDR + TRK_SAVE_VISITED_BITS + i);
  }
  if (changed) {
    tracker_logic_request(1);
  }
  if (state->logic_delay != 0 && --state->logic_delay == 0) {
    tracker_logic_evaluate();
  }
}
