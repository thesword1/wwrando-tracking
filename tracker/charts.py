# Patch-time treasure/Triforce chart table for the in-game tracker.
#
# For each chart: where it leads in this seed, and how the runtime can tell the player owns it, so
# the destination is only revealed once the chart is owned.
#
# Chart number N (the game's 1-based collectMapNo) is item ID 0xFF - N. It owns bit N-1 of the
# u32[4] big-endian "GetMap" table at 0x803C4CDC (docs/dev/memory-map.md, section 3.5). The
# "CompleteMap" (salvaged) table at 0x803C4CFC uses the same numbering. Archipelago reads its
# first 8 bytes as one big-endian integer, so its salvage bit b is chart number ((b + 32) % 64) + 1.

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
import re

from tracker.locations import (
  ISLAND_NUMBER_TO_NAME, VANILLA_ISLAND_NUMBER_TO_CHART_NAME, get_chart_destinations,
)
from wwrando_paths import DATA_PATH

GET_MAP_ADDR = 0x803C4CDC
COMPLETE_MAP_ADDR = 0x803C4CFC


def _load_chart_item_ids() -> dict[str, int]:
  with open(os.path.join(DATA_PATH, "item_names.txt"), "r") as f:
    matches = re.findall(r"^([0-9a-f]{2}) - (.+)$", f.read(), re.IGNORECASE | re.MULTILINE)
  chart_names = set(VANILLA_ISLAND_NUMBER_TO_CHART_NAME.values())
  return {item_name: int(item_id, 16) for item_id, item_name in matches if item_name in chart_names}

CHART_NAME_TO_ITEM_ID = _load_chart_item_ids()


def get_chart_number(chart_name: str) -> int:
  return 0xFF - CHART_NAME_TO_ITEM_ID[chart_name]

def get_chart_table_bit(table_address: int, chart_number: int) -> tuple[int, int]:
  """The byte address and mask of a chart's bit in one of the u32[4] chart tables."""
  index = chart_number - 1
  word, bit = index >> 5, index & 31
  return table_address + 4*word + 3 - (bit >> 3), 1 << (bit & 7)


@dataclass(frozen=True)
class TrackerChart:
  name: str
  item_id: int
  chart_number: int
  # The island whose sunken treasure this chart leads to in vanilla, and in this seed. Both are
  # sea square numbers.
  vanilla_island_number: int
  destination_island_number: int
  owned_address: int
  owned_mask: int
  salvaged_address: int
  salvaged_mask: int

  @property
  def destination_island_name(self) -> str:
    return ISLAND_NUMBER_TO_NAME[self.destination_island_number]


def chart_mapping_from_island_chart_names(island_number_to_chart_name: Mapping[int, str]) -> list[int]:
  """
  Converts ChartRandomizer.island_number_to_chart_name (destination island -> chart) to the
  .aptww plando's Charts form (entry i-1 is where island i's vanilla chart leads).
  """
  chart_name_to_destination = {chart_name: island_number for island_number, chart_name in island_number_to_chart_name.items()}
  return [chart_name_to_destination[VANILLA_ISLAND_NUMBER_TO_CHART_NAME[i]] for i in range(1, 49+1)]


def build_tracker_chart_table(chart_mapping: Sequence[int] | None) -> list[TrackerChart]:
  """One chart per sea square, ordered by destination square (1-49)."""
  chart_destinations = get_chart_destinations(chart_mapping)
  charts = []
  for destination in range(1, 49+1):
    vanilla_island_number = chart_destinations[destination]
    chart_name = VANILLA_ISLAND_NUMBER_TO_CHART_NAME[vanilla_island_number]
    chart_number = get_chart_number(chart_name)
    owned_address, owned_mask = get_chart_table_bit(GET_MAP_ADDR, chart_number)
    salvaged_address, salvaged_mask = get_chart_table_bit(COMPLETE_MAP_ADDR, chart_number)
    charts.append(TrackerChart(
      chart_name, CHART_NAME_TO_ITEM_ID[chart_name], chart_number, vanilla_island_number, destination,
      owned_address, owned_mask, salvaged_address, salvaged_mask,
    ))
  return charts
