// The tracker's logic: evaluates the compiled logic bytecode (tracker/logic_compiler.py documents
// the format; evaluate_bytecode there is the Python reference) against the player's items, visited
// entrances and checked locations, and caches each location's result and whether the seed's goal is in logic
// (GO MODE) in TrkState.

#ifndef TRACKER_LOGIC_H
#define TRACKER_LOGIC_H

#include "tracker_types.h"

enum TrkLogicStatus {
  TRK_LOGIC_NOT_EVALUATED = 0,
  TRK_LOGIC_OK = 1,
  TRK_LOGIC_NONE = 2, // The tables have no logic
  TRK_LOGIC_ERROR = 3, // Malformed bytecode: results are unknown
};

// tracker/logic_compiler.py opcodes.
enum TrkLogicOp {
  TRK_OP_END = 0x00,
  TRK_OP_TRUE = 0x01,
  TRK_OP_FALSE = 0x02,
  TRK_OP_STORE = 0x03,
  TRK_OP_AND = 0x04,
  TRK_OP_OR = 0x05,
  TRK_OP_HAS = 0x06,
  TRK_OP_CHECKED = 0x07,
  TRK_OP_CALL = 0x08,
  TRK_OP_HAS1 = 0x09,
  TRK_OP_VISITED = 0x40, // | entrance index (0-63)
};

#define TRK_LOGIC_HEADER_SIZE 10
#define TRK_LOGIC_MAX_STACK 64
#define TRK_LOGIC_MAX_SLOTS 1024
#define TRK_LOGIC_MAX_ITEMS 255
// Frames between an item get and the evaluation, so that items the HUD applies gradually (the magic
// meter) are counted.
#define TRK_LOGIC_ITEM_GET_DELAY 30

bool tracker_logic_available(void);
bool tracker_is_in_logic(u16 location_index);
bool tracker_go_mode(void);
void tracker_logic_evaluate(void);
void tracker_logic_request(u8 delay_frames);
void tracker_logic_frame(void);
void tracker_on_item_get(void);

#endif
