import random
import re

from wwrando import make_argparser # Must be imported first, it adds gclib to the path.
from aptww import read_ap_plando_file
from logic.logic import Logic
from options.wwrando_options import Options
from tracker.charts import GET_MAP_ADDR, get_chart_number, get_chart_table_bit
from tracker.items import ITEM_READS, ItemReadKind, get_item_read, read_item_count
from tracker.locations import ENTRANCE_CATEGORIES
from tracker.logic_compiler import CompiledLogic, TrackerLogicInput, _LogicRandoStub
from tracker.serialize import Section, TrackerTables, build_tracker_tables, parse_tracker_tables, serialize_tracker_tables
from tracker_c_host import TrackerHost
from test_aptww_fixtures import FIXTURE_PATHS

CURRENT_STAGE_ID_ADDR = 0x803C53A4

def logic_item_names() -> set[str]:
  """Every item any requirement in the logic files can refer to, with any options."""
  options = Options(enable_tuner_logic=True)
  logic = Logic(_LogicRandoStub(options))
  leaves = set()
  def walk(expression):
    for token in expression:
      if isinstance(token, list):
        walk(token)
      elif token not in "&|()":
        leaves.add(token)
  for expression in logic.macros.values():
    walk(expression)
  for location in logic.item_locations.values():
    walk(location["Need"])
  items = set()
  for leaf in leaves:
    match = re.fullmatch(r"(Progressive .+|.+ Capacity Upgrade|.+ Small Key) x\d+", leaf)
    if match:
      items.add(match.group(1))
    elif leaf in logic.all_cleaned_item_names:
      items.add(leaf)
  return items

def test_every_logic_item_can_be_read():
  items = logic_item_names()
  assert len(items) > 100
  for item_name in items:
    get_item_read(item_name)
  # Every chart, including the ones only randomized charts can point to.
  for i in range(1, 42):
    get_item_read(f"Treasure Chart {i}")
  for i in range(1, 9):
    get_item_read(f"Triforce Chart {i}")

def test_chart_reads_match_chart_table():
  for chart_name in [f"Treasure Chart {i}" for i in range(1, 42)] + [f"Triforce Chart {i}" for i in range(1, 9)]:
    read = ITEM_READS[chart_name]
    assert (read.address, read.a) == get_chart_table_bit(GET_MAP_ADDR, get_chart_number(chart_name))
  # Ghost Ship Chart is item 0xDB, collectmap36.
  assert (ITEM_READS["Ghost Ship Chart"].address, ITEM_READS["Ghost Ship Chart"].a) == get_chart_table_bit(GET_MAP_ADDR, 36)


def fixture_blobs() -> list[tuple[list[str], bytes]]:
  blobs = []
  for path in FIXTURE_PATHS:
    options = Options()
    plando = read_ap_plando_file(str(path), options)
    required_bosses = plando.required_bosses if options.required_bosses else None
    logic_input = TrackerLogicInput(options, plando.entrances, plando.charts, required_bosses)
    tables = build_tracker_tables(
      plando.locations, plando.charts, plando.entrances, {name: options[name] for name in ENTRANCE_CATEGORIES},
      required_bosses, logic_input,
    )
    blobs.append((tables.logic.items, serialize_tracker_tables(tables, 1)))
  return blobs

def test_items_section():
  for items, blob in fixture_blobs():
    parsed = parse_tracker_tables(blob)
    offset, count, entry_size = parsed["directory"][Section.ITEMS]
    assert count == len(items) == blob[parsed["directory"][Section.LOGIC][0] + 5]
    assert entry_size == 8
    for i, item_name in enumerate(items):
      assert blob[offset + 8*i:offset + 8*(i+1)] == get_item_read(item_name).pack()

def test_c_item_counts_match_python(tracker: TrackerHost):
  # Random memory at every address the descriptors read: the C reader must agree with the Python reference.
  rng = random.Random(5)
  for items, blob in fixture_blobs():
    tracker.reset_ram()
    tracker.set_tables(blob)
    reads = [get_item_read(item_name) for item_name in items]
    addresses = {CURRENT_STAGE_ID_ADDR, 0x803C5380 + 0x21}
    for read in reads:
      addresses.update(range(read.address, read.address + max(1, read.a if read.kind == ItemReadKind.SLOTS else 1)))
    for _ in range(30):
      for address in addresses:
        tracker.write_u8(address, rng.choice([0, 0xFF, rng.randrange(256), 30, 60, 99, 16, 32]))
      tracker.write_u8(CURRENT_STAGE_ID_ADDR, rng.choice([0, 3, 4, 5, 6, 7, 0xB]))
      for i, read in enumerate(reads):
        assert tracker.lib.tracker_item_count(i) == read_item_count(read, tracker.read_u8), items[i]
    assert tracker.lib.tracker_item_count(len(items)) == 0

def load_items(tracker: TrackerHost, item_names: list[str]) -> dict[str, int]:
  tables = build_tracker_tables([], None, {}, None, None)
  logic = CompiledLogic(b"\0", 0, 0, 0, list(item_names), [])
  tracker.set_tables(serialize_tracker_tables(TrackerTables(tables.location_set, tables.entrance_set, tables.charts, logic), 1))
  return {item_name: i for i, item_name in enumerate(item_names)}

def test_item_counts_from_game_state(tracker: TrackerHost):
  # Memory as the item get functions leave it (vanilla d_item.cpp and the randomizer's custom_funcs.asm).
  names = [
    "Progressive Sword", "Progressive Bow", "Progressive Shield", "Progressive Picto Box", "Wallet Capacity Upgrade",
    "Bomb Bag Capacity Upgrade", "Quiver Capacity Upgrade", "Progressive Magic Meter", "Grappling Hook",
    "Empty Bottle", "Triforce Shard 3", "Din's Pearl", "Song of Passing", "Hurricane Spin", "Earth Tingle Statue",
    "Moblin's Letter", "Cabana Deed", "Power Bracelets", "DRC Big Key", "DRC Small Key", "WT Small Key",
    "Treasure Chart 3", "Magic Armor",
  ]
  index = load_items(tracker, names)
  count = lambda name: tracker.lib.tracker_item_count(index[name])
  # New game: max bombs and arrows are 30, no magic, every slot empty.
  for address in range(0x803C4C44, 0x803C4C44 + 21):
    tracker.write_u8(address, 0xFF)
  tracker.write_u8(0x803C4C77, 30)
  tracker.write_u8(0x803C4C78, 30)
  tracker.write_u8(CURRENT_STAGE_ID_ADDR, 0)
  assert all(count(name) == 0 for name in names)
  
  tracker.write_u8(0x803C4CBC, 0x07) # Hero's Sword, Master Sword, half power
  tracker.write_u8(0x803C4C65, 0x03) # Bow, Fire & Ice Arrows
  tracker.write_u8(0x803C4CBD, 0x01)
  tracker.write_u8(0x803C4C61, 0x03)
  tracker.write_u8(0x803C4C1A, 2) # 5000 rupee wallet
  tracker.write_u8(0x803C4C78, 60)
  tracker.write_u8(0x803C4C77, 99)
  tracker.write_u8(0x803C4C1B, 16)
  tracker.write_u8(0x803C4C5C, 0x01) # Grappling Hook slot ever-owned bit
  tracker.write_u8(0x803C4C53, 0x50) # A bottle in the second bottle slot
  tracker.write_u8(0x803C4CC6, 0x04)
  tracker.write_u8(0x803C4CC7, 0x02)
  tracker.write_u8(0x803C4CC5, 0x20)
  tracker.write_u8(0x803C5295, 0x01) # Event 0x6901
  tracker.write_u8(0x803C5296, 0x20) # Event 0x6A20
  tracker.write_u32(0x803C4C98, (1 << 15) | (1 << 0x10)) # Moblin's Letter and Cabana Deed owned
  tracker.write_u8(0x803C4CBE, 0x01)
  tracker.write_u8(0x803C4C63, 0x01) # Magic Armor slot
  chart_address, chart_mask = get_chart_table_bit(GET_MAP_ADDR, get_chart_number("Treasure Chart 3"))
  tracker.write_u8(chart_address, chart_mask)
  expected = {
    "Progressive Sword": 3, "Progressive Bow": 2, "Progressive Shield": 1, "Progressive Picto Box": 2,
    "Wallet Capacity Upgrade": 2, "Bomb Bag Capacity Upgrade": 1, "Quiver Capacity Upgrade": 2,
    "Progressive Magic Meter": 1, "Grappling Hook": 1, "Empty Bottle": 1, "Triforce Shard 3": 1, "Din's Pearl": 1,
    "Song of Passing": 1, "Hurricane Spin": 1, "Earth Tingle Statue": 1, "Moblin's Letter": 1, "Cabana Deed": 1,
    "Power Bracelets": 1, "Magic Armor": 1, "DRC Big Key": 0, "DRC Small Key": 0, "WT Small Key": 0,
    "Treasure Chart 3": 1,
  }
  assert {name: count(name) for name in names} == expected
  
  # Big key: the saved DRC stage info, or the live copy while in DRC.
  tracker.write_u8(0x803C4FF4 + 0x21, 0x04)
  assert count("DRC Big Key") == 1
  tracker.write_u8(CURRENT_STAGE_ID_ADDR, 3)
  assert count("DRC Big Key") == 0
  tracker.write_u8(0x803C5380 + 0x21, 0x04)
  assert count("DRC Big Key") == 1
  
  # Small keys: the tracker's obtained counters, not the current key count.
  tracker.lib.tracker_count_small_key(0)
  tracker.lib.tracker_count_small_key(0)
  tracker.lib.tracker_count_small_key(4)
  assert (count("DRC Small Key"), count("WT Small Key")) == (2, 1)
