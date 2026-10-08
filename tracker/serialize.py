# Binary table format for the in-game tracker.
#
# serialize_tracker_tables() packs one seed's location, group, entrance and chart tables into the
# blob that tweaks.add_in_game_tracker writes into the tracker_data reserve (asm/patches/tracker.asm).
# The C runtime reads it with asm/tracker/tracker_tables.c, whose constants must match this file.
#
# Everything is big-endian. Offsets are from the start of the blob.
#
# Header (0x20 bytes):
#   0x00  char[4]  magic "WWTK"
#   0x04  u16      format version (FORMAT_VERSION)
#   0x06  u16      seed tag (nonzero; the runtime resets its save data when a save has another tag)
#   0x08  u32      total size in bytes
#   0x0C  u16      number of sections (NUM_SECTIONS)
#   0x0E  u16      flags (reserved, 0)
#   0x10  -        reserved, 0
# Section directory at 0x20, one 8-byte entry per Section:
#   +0 u32 offset, +4 u16 entry count, +6 u16 entry size (1 for byte streams)
# Sections (each 4-byte aligned):
#   LOCATIONS (12 bytes each, ordered by group so every group's locations are contiguous):
#     +0 u8 group ID, +1 u8 LocationType, +2 u8 stage ID (0xFF unless CHEST/SWTCH/PCKUP), +3 u8 mask,
#     +4 u32 address (saved copy for stage flags; 0 for NONE), +8 u16 display name,
#     +10 u8 SpecialCheck (0xFF unless SPECL), +11 u8 flags (reserved, 0)
#   GROUPS (8 bytes each, ordered by ID): every sea square 1-49, then each list-page group that has
#     locations or is behind a tracked entrance.
#     +0 u8 ID, +1 u8 GroupKind, +2 u16 first location, +4 u16 location count, +6 u16 name
#   ENTRANCES (8 bytes each; the index is the entrance's visited bit):
#     +0 u8 island square (0 when nested), +1 u8 group of the exit it's nested in (0xFF if not
#     nested), +2 u8 group behind its exit in this seed, +3 u8 category (ENTRANCE_CATEGORY_ORDER),
#     +4 u16 entrance name, +6 u16 exit name
#   TRIGGERS (12 bytes each): stages whose visit sets an entrance's visited bit.
#     +0 char[8] stage name (NUL-padded), +8 u8 room (0xFF = any), +9 u8 spawn (0xFF = any),
#     +10 u8 entrance index, +11 pad
#   CHARTS (12 bytes each, one per destination square 1-49 in order):
#     +0 u8 destination square, +1 u8 vanilla square, +2 u8 chart number, +3 u8 item ID,
#     +4 u8 owned byte offset from 0x803C4CDC, +5 u8 owned mask,
#     +6 u8 salvaged byte offset from 0x803C4CFC, +7 u8 salvaged mask, +8 u16 name, +10 pad
#   STRINGS: NUL-terminated ASCII strings; the "name" fields above are offsets into this section.
#   LOGIC: compiled logic bytecode (byte stream), described in tracker/logic_compiler.py. Empty when the
#     tables were built without logic.
#   ITEMS (8 bytes each): how to read the count of each item the logic uses, indexed by the bytecode's item
#     operands (tracker/items.py documents the entries). Empty when the tables were built without logic.
#   STAGES (10 bytes each, sorted by stage name): the group whose list the dungeon map and Quest Status screens open
#     in a stage (tracker/stages.py). Only groups in GROUPS.
#     +0 char[8] stage name (NUL-padded), +8 u8 group ID, +9 pad

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
import struct
import zlib

from typing import Any

from tracker.charts import COMPLETE_MAP_ADDR, GET_MAP_ADDR, TrackerChart, build_tracker_chart_table
from tracker.entrances import EXITS, TrackerEntranceSet, build_tracker_entrance_set
from tracker.items import serialize_item_reads
from tracker.logic_compiler import CompiledLogic, TrackerLogicInput, compile_tracker_logic
from tracker.locations import (
  ENTRANCE_CATEGORIES, SQUARE_GROUPS, TrackerGroup, TrackerLocationSet, build_tracker_location_set,
  get_randomized_exits,
)
from tracker.stages import build_stage_groups, stage_group_entries

MAGIC = b"WWTK"
FORMAT_VERSION = 2
HEADER_SIZE = 0x20
DIR_ENTRY_SIZE = 8

# Size of the tracker_data reserve in asm/patches/tracker.asm.
TRACKER_DATA_RESERVE_SIZE = 0x6000

# Limits of the save data layout (docs/dev/memory-map.md): 384 manual-mark bits, 64 visited bits.
MAX_LOCATIONS = 384
MAX_ENTRANCES = 64
# Size of the per-group counts in the runtime state (asm/tracker/tracker_state.h).
MAX_GROUPS = 128

NO_VALUE = 0xFF

ENTRANCE_CATEGORY_ORDER = list(ENTRANCE_CATEGORIES)


class Section(IntEnum):
  LOCATIONS = 0
  GROUPS = 1
  ENTRANCES = 2
  TRIGGERS = 3
  CHARTS = 4
  STRINGS = 5
  LOGIC = 6
  ITEMS = 7
  STAGES = 8

NUM_SECTIONS = len(Section)

LOCATION_FORMAT = ">BBBBIHBB"
GROUP_FORMAT = ">BBHHH"
ENTRANCE_FORMAT = ">BBBBHH"
TRIGGER_FORMAT = ">8sBBBx"
CHART_FORMAT = ">BBBBBBBBHxx"
STAGE_FORMAT = ">8sBx"
ENTRY_SIZES = {
  Section.LOCATIONS: struct.calcsize(LOCATION_FORMAT),
  Section.GROUPS: struct.calcsize(GROUP_FORMAT),
  Section.ENTRANCES: struct.calcsize(ENTRANCE_FORMAT),
  Section.TRIGGERS: struct.calcsize(TRIGGER_FORMAT),
  Section.CHARTS: struct.calcsize(CHART_FORMAT),
  Section.STRINGS: 1,
  Section.LOGIC: 1,
  Section.ITEMS: 8,
  Section.STAGES: struct.calcsize(STAGE_FORMAT),
}


def compute_seed_tag(text: str) -> int:
  """A nonzero 16-bit tag identifying a seed, stored in the tables and in the save file."""
  return (zlib.crc32(text.encode("utf-8")) % 0xFFFF) + 1


class _StringPool:
  def __init__(self):
    self.data = bytearray()
    self.offsets: dict[str, int] = {}

  def add(self, string: str) -> int:
    if string not in self.offsets:
      assert string.isascii() and "\0" not in string, f"Tracker strings must be ASCII: {string!r}"
      self.offsets[string] = len(self.data)
      self.data += string.encode("ascii") + b"\0"
      assert len(self.data) <= 0x10000, "Tracker string pool is too large"
    return self.offsets[string]


@dataclass(frozen=True)
class TrackerTables:
  location_set: TrackerLocationSet
  entrance_set: TrackerEntranceSet
  charts: Sequence[TrackerChart]
  logic: CompiledLogic | None = None
  # Stage name -> group (tracker/stages.py).
  stage_groups: Mapping[str, TrackerGroup] = field(default_factory=dict)

  def groups(self) -> list[TrackerGroup]:
    """Every sea square, plus the list-page groups that have locations or tracked entrances."""
    groups = {group.id: group for group in SQUARE_GROUPS}
    for group in self.location_set.groups():
      groups[group.id] = group
    for seed_entrance in self.entrance_set.entrances:
      exit_group = seed_entrance.exit.group
      groups[exit_group.id] = exit_group
    return [groups[group_id] for group_id in sorted(groups)]


def build_tracker_tables(
  active_location_names: Iterable[str],
  chart_mapping: Sequence[int] | None,
  entrance_pairings: Mapping[str, str],
  entrance_options: Mapping[str, Any] | None,
  required_bosses: Iterable[str] | None,
  logic_input: TrackerLogicInput | None = None,
) -> TrackerTables:
  """All of one seed's tables. The arguments are as for the build_tracker_*() functions. The logic is only compiled
  when logic_input is given."""
  location_set = build_tracker_location_set(active_location_names, chart_mapping, entrance_options, required_bosses)
  entrance_set = build_tracker_entrance_set(entrance_pairings, entrance_options)
  logic = None
  if logic_input is not None:
    logic = compile_tracker_logic(
      logic_input,
      [loc.name for loc in location_set.locations],
      {seed_entrance.entrance.name: seed_entrance.index for seed_entrance in entrance_set.entrances},
    )
  stage_groups = build_stage_groups(get_randomized_exits(entrance_options))
  return TrackerTables(location_set, entrance_set, build_tracker_chart_table(chart_mapping), logic, stage_groups)


def serialize_tracker_tables(tables: TrackerTables, seed_tag: int) -> bytes:
  assert 0 < seed_tag <= 0xFFFF
  locations = tables.location_set.locations
  entrances = tables.entrance_set.entrances
  assert len(locations) <= MAX_LOCATIONS, f"Too many tracked locations: {len(locations)}"
  assert len(entrances) <= MAX_ENTRANCES, f"Too many tracked entrances: {len(entrances)}"
  assert [loc.index for loc in locations] == list(range(len(locations)))
  assert [e.index for e in entrances] == list(range(len(entrances)))

  strings = _StringPool()
  sections: dict[Section, tuple[bytes, int]] = {}

  location_data = bytearray()
  for loc in locations:
    check = loc.check
    location_data += struct.pack(
      LOCATION_FORMAT,
      loc.group.id,
      check.type.value,
      NO_VALUE if check.stage_id is None else check.stage_id,
      check.mask,
      check.address or 0,
      strings.add(loc.display_name),
      NO_VALUE if check.special is None else check.special.value,
      0,
    )
  sections[Section.LOCATIONS] = (location_data, len(locations))

  group_data = bytearray()
  groups = tables.groups()
  for group in groups:
    group_locations = tables.location_set.locations_in_group(group)
    first = group_locations[0].index if group_locations else 0
    if group_locations:
      assert [loc.index for loc in group_locations] == list(range(first, first + len(group_locations))), \
        f"Locations of group {group.name!r} aren't contiguous"
    group_data += struct.pack(GROUP_FORMAT, group.id, group.kind.value, first, len(group_locations), strings.add(group.name))
  assert len(groups) <= MAX_GROUPS, f"Too many tracker groups: {len(groups)}"
  sections[Section.GROUPS] = (group_data, len(groups))

  entrance_data = bytearray()
  for seed_entrance in entrances:
    entrance = seed_entrance.entrance
    parent_group = EXITS[entrance.nested_in].group.id if entrance.nested_in else NO_VALUE
    entrance_data += struct.pack(
      ENTRANCE_FORMAT,
      entrance.island_number or 0,
      parent_group,
      seed_entrance.exit.group.id,
      ENTRANCE_CATEGORY_ORDER.index(entrance.option_name),
      strings.add(entrance.display_name),
      strings.add(seed_entrance.exit.display_name),
    )
  sections[Section.ENTRANCES] = (entrance_data, len(entrances))

  trigger_data = bytearray()
  triggers = tables.entrance_set.stage_triggers()
  for trigger, entrance_index in triggers:
    stage_name = trigger.stage_name.encode("ascii")
    assert len(stage_name) <= 8
    trigger_data += struct.pack(
      TRIGGER_FORMAT,
      stage_name,
      NO_VALUE if trigger.room_num is None else trigger.room_num,
      NO_VALUE if trigger.spawn_id is None else trigger.spawn_id,
      entrance_index,
    )
  sections[Section.TRIGGERS] = (trigger_data, len(triggers))

  chart_data = bytearray()
  for chart in tables.charts:
    chart_data += struct.pack(
      CHART_FORMAT,
      chart.destination_island_number,
      chart.vanilla_island_number,
      chart.chart_number,
      chart.item_id,
      chart.owned_address - GET_MAP_ADDR,
      chart.owned_mask,
      chart.salvaged_address - COMPLETE_MAP_ADDR,
      chart.salvaged_mask,
      strings.add(chart.name),
    )
  sections[Section.CHARTS] = (chart_data, len(tables.charts))

  sections[Section.STRINGS] = (bytes(strings.data), len(strings.data))
  logic_data = tables.logic.serialize() if tables.logic is not None else b""
  sections[Section.LOGIC] = (logic_data, len(logic_data))
  items = tables.logic.items if tables.logic is not None else []
  sections[Section.ITEMS] = (serialize_item_reads(items), len(items))

  stage_data = bytearray()
  stage_entries = stage_group_entries(tables.stage_groups, {group.id for group in groups})
  for stage_name, group_id in stage_entries:
    encoded = stage_name.encode("ascii")
    assert len(encoded) <= 8
    stage_data += struct.pack(STAGE_FORMAT, encoded, group_id)
  sections[Section.STAGES] = (stage_data, len(stage_entries))

  directory = bytearray()
  body = bytearray()
  offset = HEADER_SIZE + DIR_ENTRY_SIZE*NUM_SECTIONS
  for section in Section:
    data, count = sections[section]
    directory += struct.pack(">IHH", offset + len(body), count, ENTRY_SIZES[section])
    body += data
    body += b"\0" * (-len(body) % 4)

  total_size = offset + len(body)
  header = struct.pack(">4sHHIHH", MAGIC, FORMAT_VERSION, seed_tag, total_size, NUM_SECTIONS, 0)
  header += b"\0" * (HEADER_SIZE - len(header))
  blob = header + directory + body
  assert len(blob) == total_size
  return bytes(blob)


def parse_tracker_tables(blob: bytes) -> dict[str, object]:
  """Python reader for the format above, for tests and debugging."""
  magic, version, seed_tag, total_size, num_sections, flags = struct.unpack_from(">4sHHIHH", blob, 0)
  assert magic == MAGIC and version == FORMAT_VERSION
  directory = [struct.unpack_from(">IHH", blob, HEADER_SIZE + DIR_ENTRY_SIZE*i) for i in range(num_sections)]

  def entries(section: Section, fmt: str) -> list[tuple]:
    offset, count, size = directory[section]
    assert size == struct.calcsize(fmt)
    return [struct.unpack_from(fmt, blob, offset + i*size) for i in range(count)]

  strings_offset, strings_size, _ = directory[Section.STRINGS]
  string_data = blob[strings_offset:strings_offset+strings_size]
  def string(offset: int) -> str:
    return string_data[offset:string_data.index(b"\0", offset)].decode("ascii")

  return {
    "seed_tag": seed_tag,
    "total_size": total_size,
    "flags": flags,
    "directory": directory,
    "locations": [(*entry[:5], string(entry[5]), *entry[6:]) for entry in entries(Section.LOCATIONS, LOCATION_FORMAT)],
    "groups": [(*entry[:4], string(entry[4])) for entry in entries(Section.GROUPS, GROUP_FORMAT)],
    "entrances": [(*entry[:4], string(entry[4]), string(entry[5])) for entry in entries(Section.ENTRANCES, ENTRANCE_FORMAT)],
    "triggers": [(entry[0].rstrip(b"\0").decode("ascii"), *entry[1:]) for entry in entries(Section.TRIGGERS, TRIGGER_FORMAT)],
    "charts": [(*entry[:8], string(entry[8])) for entry in entries(Section.CHARTS, CHART_FORMAT)],
    "logic": blob[directory[Section.LOGIC][0]:directory[Section.LOGIC][0]+directory[Section.LOGIC][1]],
    "stages": [(entry[0].rstrip(b"\0").decode("ascii"), entry[1]) for entry in entries(Section.STAGES, STAGE_FORMAT)],
  }
