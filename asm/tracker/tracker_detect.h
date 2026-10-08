#ifndef TRACKER_DETECT_H
#define TRACKER_DETECT_H

#include "tracker_types.h"

bool tracker_is_auto_checked(u16 location_index);
bool tracker_is_checked(u16 location_index);
bool tracker_toggle_manual(u16 location_index);
void tracker_group_counts(u16 group_index, u16* checked, u16* total);

#endif
