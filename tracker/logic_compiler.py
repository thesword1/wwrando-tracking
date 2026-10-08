# Compiles the randomizer's logic (logic/item_locations.txt and logic/macros.txt, the same files the offline item
# randomizer uses) into compact bytecode that the in-game tracker evaluates to colour locations that are in logic.
#
# Everything that's fixed for the seed is resolved at patch time: Option terms, Tuner logic, Swords Optional/Swordless,
# starting items, dungeon items in the Start With modes, the chart mapping and the required bosses. What's left reads
# the player's state: items owned, small keys obtained per dungeon (the tracker's own counters, D12), entrances visited
# and locations checked.
#
# Behaviour follows the WWRando-APTracker website (src/services/logic-tweaks.js, logic-calculation.js) so that the
# tracker never spoils anything:
# - A randomized entrance's exit is only reachable once the entrance has been visited ("Entered X" on the website). The
#   compiler knows the seed's real entrance mapping, so "Can Access <exit>" becomes VISITED(entrance) & "Can Access
#   <entrance>". Before the visit everything behind it is out of logic, and the visit itself reveals the mapping.
# - Mail letters and "Can Farm Knight's Crests" use "Has Accessed Other Location": the other location counts once it's
#   checked, or if it's in logic (has-accessed-location-tweaks.json).
# - Required bosses count as defeated once their heart container location is checked, or if it's in logic.
# - The chart for each island is the chart that leads there in this seed. That doesn't spoil anything either: a chart's
#   destination is shown once it's owned, which is exactly when the logic starts using it.
#
# Bytecode
# --------
# The program is straight-line postfix code over a stack of booleans, evaluated once from start to end. It computes a
# result bit per "slot": first the shared subexpressions (macros used more than once, in dependency order), then one
# slot per tracked location in table order, then the goal slots. STORE pops the top of the stack into the next slot; CALL pushes an earlier
# slot's result. So there's no recursion or memo at runtime, and a full evaluation costs one pass over the code.
#
# LOGIC section layout (big-endian):
#   +0 u16 number of shared slots (S)        location i's result is slot S+i
#   +2 u16 number of locations (L)           must equal the LOCATIONS section's count
#   +4 u8  maximum stack depth
#   +5 u8  number of items (the ITEMS section's count)
#   +6 u16 code size in bytes
#   +8 u8  number of goal slots (G, 0 or 1)  goal i's result is slot S+L+i
#   +9 u8  reserved, 0
#   +10    code, ending with END
#
# The goal slot is the seed's goal, "Can Reach and Defeat Ganondorf" (the requirement of Archipelago's "Defeat
# Ganondorf" location, which the tracker doesn't track), including the required bosses. The tracker shows "GO MODE"
# while it's in logic. It isn't a location: it doesn't change any count.
#
# Opcodes:
#   0x00 END
#   0x01 TRUE                    push 1
#   0x02 FALSE                   push 0
#   0x03 STORE                   pop into the next slot
#   0x04 AND n                   pop n (2-255) values, push their AND
#   0x05 OR n                    pop n values, push their OR
#   0x06 HAS item count          push (count of item >= count); count is 2-255
#   0x07 CHECKED loc_hi loc_lo   push whether tracked location loc is checked (auto-detected or marked)
#   0x08 CALL slot_hi slot_lo    push an earlier slot's result
#   0x09 HAS1 item               push (count of item >= 1)
#   0x40 | e                     VISITED e: push whether tracked entrance e (0-63) has been visited
# "item" indexes the compiled item list (ITEMS section, tracker/items.py). Small keys are items too: their count is
# the number of that dungeon's small keys obtained.

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import re
import struct
from typing import Any, Callable, Union

from logic.logic import Logic
from options.wwrando_options import KeyLunacyMode, Options, SwordMode
from randomizers import entrances

OP_END = 0x00
OP_TRUE = 0x01
OP_FALSE = 0x02
OP_STORE = 0x03
OP_AND = 0x04
OP_OR = 0x05
OP_HAS = 0x06
OP_CHECKED = 0x07
OP_CALL = 0x08
OP_HAS1 = 0x09
OP_VISITED = 0x40

LOGIC_HEADER_FORMAT = ">HHBBHBx"
LOGIC_HEADER_SIZE = struct.calcsize(LOGIC_HEADER_FORMAT)

# The C interpreter's stack and item list sizes (asm/tracker/tracker_logic.c).
MAX_STACK_DEPTH = 64
MAX_ITEMS = 255
MAX_VISITED = 64

# The logic's requirement for beating the game, compiled into the goal slot.
GOAL_REQUIREMENT = "Can Reach and Defeat Ganondorf"

# Locations and macros whose "Can Access Item Location" terms are replaced with "Has Accessed Other Location" on the
# website (src/data/has-accessed-location-tweaks.json).
HAS_ACCESSED_LOCATION_TWEAK_LOCATIONS = {
  "Mailbox - Letter from Baito",
  "Mailbox - Letter from Orca",
  "Mailbox - Letter from Aryll",
  "Mailbox - Letter from Tingle",
}
HAS_ACCESSED_LOCATION_TWEAK_MACROS = {
  "Can Farm Knight's Crests",
}

# A shared subexpression is only given its own slot if inlining it would cost more than calling it.
CALL_SIZE = 3


# Expression nodes. They're interned, so equal subexpressions are the same object and can be shared (and compared and
# hashed by identity, which keeps this fast on the deep DAGs the macros make).
class Node:
  __slots__ = ("kind", "args", "children", "__weakref__")
  
  def __init__(self, kind: str, args: tuple = (), children: tuple[Node, ...] = ()):
    self.kind = kind
    self.args = args
    self.children = children
  
  def __repr__(self):
    if self.children:
      return f"{self.kind}({', '.join(map(repr, self.children))})"
    return f"{self.kind}{self.args!r}" if self.args else self.kind.upper()

_interned: dict[tuple, Node] = {}

def _intern(kind: str, args: tuple = (), children: tuple[Node, ...] = ()) -> Node:
  key = (kind, args, tuple(id(child) for child in children))
  node = _interned.get(key)
  if node is None:
    node = Node(kind, args, children)
    _interned[key] = node
  return node

TRUE = _intern("true")
FALSE = _intern("false")

def has(item_name: str, count: int = 1) -> Node:
  if count <= 0:
    return TRUE
  return _intern("has", (item_name, count))

def visited(entrance_index: int) -> Node:
  return _intern("visited", (entrance_index,))

def checked(location_index: int) -> Node:
  return _intern("checked", (location_index,))

def _combine(kind: str, children: Iterable[Node]) -> Node:
  absorbing, neutral = (FALSE, TRUE) if kind == "and" else (TRUE, FALSE)
  flat: list[Node] = []
  seen = set()
  for child in children:
    if child is absorbing:
      return absorbing
    if child is neutral:
      continue
    for grandchild in (child.children if child.kind == kind else (child,)):
      if grandchild not in seen:
        seen.add(grandchild)
        flat.append(grandchild)
  if not flat:
    return neutral
  if len(flat) == 1:
    return flat[0]
  return _intern(kind, (), tuple(flat))

def and_(*children: Node) -> Node:
  return _combine("and", children)

def or_(*children: Node) -> Node:
  return _combine("or", children)


def node_size(node: Node, cache: dict[Node, int] | None = None) -> int:
  """Number of leaves in the fully expanded tree."""
  if cache is None:
    cache = {}
  if node in cache:
    return cache[node]
  if node.children:
    size = sum(node_size(child, cache) for child in node.children)
  else:
    size = 1
  cache[node] = size
  return size


@dataclass(frozen=True)
class TrackerLogicInput:
  """What the compiler needs to know about the seed besides the tracker tables."""
  options: Options
  # Entrance name -> exit name (the plando's Entrances). Entrances that are missing are vanilla.
  entrance_pairings: Mapping[str, str]
  # The plando's Charts list (entry i-1 is where island i's vanilla chart leads), or None for vanilla charts.
  chart_mapping: Sequence[int] | None
  # The required bosses' heart container locations, or None when Required Bosses mode is off.
  required_bosses: Sequence[str] | None
  # Items the logic counts as owned from the start (offline: WWRandomizer.starting_items). In Archipelago mode only
  # the Boat's Sail: the start inventory is given by the client, so the tracker reads it from the game.
  starting_items: Sequence[str] = ("Boat's Sail",)


@dataclass
class CompiledLogic:
  code: bytes
  num_slots: int
  num_locations: int
  max_stack: int
  # Item names, indexed by the HAS operands.
  items: list[str]
  # The expression of each tracked location, in table order (for tests and debugging).
  location_exprs: list[Node] = field(repr=False)
  # The goal's expression (GOAL_REQUIREMENT), or None if the code has no goal slot.
  goal_expr: Node | None = field(default=None, repr=False)

  @property
  def num_goals(self) -> int:
    return 0 if self.goal_expr is None else 1

  def serialize(self) -> bytes:
    header = struct.pack(
      LOGIC_HEADER_FORMAT, self.num_slots, self.num_locations, self.max_stack, len(self.items), len(self.code),
      self.num_goals,
    )
    return header + self.code


class _Compiler:
  def __init__(self, inp: TrackerLogicInput, location_names: Sequence[str], tracked_entrances: Mapping[str, int]):
    self.inp = inp
    self.options = inp.options
    self.logic = Logic(_LogicRandoStub(inp.options))
    self.location_index = {name: i for i, name in enumerate(location_names)}
    self.location_names = list(location_names)
    self.tracked_entrances = tracked_entrances
    self.starting_item_counts: dict[str, int] = {}
    for item_name in inp.starting_items:
      item_name = self.logic.clean_item_name(item_name)
      self.starting_item_counts[item_name] = self.starting_item_counts.get(item_name, 0) + 1

    self.macro_overrides: dict[str, Node | str] = {}
    self._override_entrance_macros()
    self._override_chart_macros()
    self._override_required_bosses_macro()

    # Logic.check_requirement_met's exception for nested entrances that depend on the exit they're nested in.
    self.nested_entrance_macros = {}
    for zone_entrance in entrances.ZoneEntrance.all.values():
      if zone_entrance.is_nested:
        self.nested_entrance_macros["Can Access " + zone_entrance.entrance_name] = "Can Access " + zone_entrance.nested_in.unique_name

    self.memo: dict[str, Node] = {}
    self.stack: list[str] = []

  def _override_entrance_macros(self):
    exit_to_entrance = {}
    for zone_entrance in entrances.ZoneEntrance.all.values():
      exit_name = self.inp.entrance_pairings.get(zone_entrance.entrance_name)
      if exit_name is None:
        exit_name = _vanilla_exit_for_entrance(zone_entrance.entrance_name)
      if exit_name is None:
        continue
      exit_to_entrance[exit_name] = zone_entrance.entrance_name
    for exit_name, entrance_name in exit_to_entrance.items():
      if entrance_name in self.tracked_entrances:
        self.macro_overrides["Can Access " + exit_name] = lambda e=entrance_name: and_(visited(self.tracked_entrances[e]), self.req("Can Access " + e))
      else:
        self.macro_overrides["Can Access " + exit_name] = lambda e=entrance_name: self.req("Can Access " + e)

  def _override_chart_macros(self):
    from tracker.locations import VANILLA_ISLAND_NUMBER_TO_CHART_NAME
    mapping = self.inp.chart_mapping
    for source_island in range(1, 49+1):
      destination = mapping[source_island-1] if mapping is not None else source_island
      chart_name = VANILLA_ISLAND_NUMBER_TO_CHART_NAME[source_island]
      if "Triforce Chart" in chart_name:
        req_string = "%s & Any Wallet Upgrade" % chart_name
      else:
        req_string = chart_name
      self.macro_overrides["Chart for Island %d" % destination] = req_string

  def _override_required_bosses_macro(self):
    if self.inp.required_bosses is None:
      return
    boss_locations = list(self.inp.required_bosses)
    self.macro_overrides["Can Defeat All Required Bosses"] = lambda: and_(*(self.has_accessed(loc) for loc in boss_locations))

  # Requirements

  def req(self, req_name: str, has_accessed_tweak: bool = False) -> Node:
    if req_name.startswith("Can Access Item Location \""):
      match = re.search(r"^Can Access Item Location \"([^\"]+)\"$", req_name)
      assert match, req_name
      if has_accessed_tweak:
        return self.has_accessed(match.group(1))
      return self.location_need(match.group(1))

    if req_name in self.memo:
      return self.memo[req_name]
    if req_name in self.nested_entrance_macros and self.nested_entrance_macros[req_name] in self.stack:
      # Like Logic.check_requirement_met: an entrance nested in the exit currently being resolved can't be how you
      # reach that exit.
      return TRUE
    assert req_name not in self.stack, f"Recursive requirement: {req_name!r} ({self.stack})"
    self.stack.append(req_name)
    result = self._resolve(req_name)
    self.stack.pop()
    self.memo[req_name] = result
    return result

  def _resolve(self, req_name: str) -> Node:
    logic = self.logic
    if req_name in self.macro_overrides:
      override = self.macro_overrides[req_name]
      if isinstance(override, str):
        return self.expression(Logic.parse_logic_expression(override))
      return override()
    if req_name == "Nothing":
      return TRUE
    if req_name == "Impossible":
      return FALSE
    if req_name.startswith("Option \""):
      return TRUE if logic.check_option_enabled_requirement(req_name) else FALSE
    if req_name.startswith("Progressive ") or " Capacity Upgrade" in req_name:
      match = re.search(r"^(Progressive .+|.+ Capacity Upgrade) x(\d+)$", req_name)
      assert match, req_name
      item_name, count = match.group(1), int(match.group(2))
      if item_name == "Progressive Sword" and not logic.swords_in_logic:
        return TRUE if count == 0 else FALSE
      return self.item(item_name, count)
    if " Small Key x" in req_name:
      match = re.search(r"^(.+ Small Key) x(\d+)$", req_name)
      assert match, req_name
      key_name, count = match.group(1), int(match.group(2))
      if self.options.randomize_smallkeys == KeyLunacyMode.START_WITH:
        return TRUE
      return self.item(key_name, count)
    if req_name in logic.all_cleaned_item_names:
      if req_name.endswith(" Big Key") and self.options.randomize_bigkeys == KeyLunacyMode.START_WITH:
        return TRUE
      return self.item(req_name, 1)
    if req_name in logic.macros:
      return self.expression(logic.macros[req_name], has_accessed_tweak=req_name in HAS_ACCESSED_LOCATION_TWEAK_MACROS)
    raise Exception("Unknown requirement name: " + req_name)

  def item(self, item_name: str, count: int) -> Node:
    if self.starting_item_counts.get(item_name, 0) >= count:
      return TRUE
    return has(item_name, count)

  def expression(self, logical_expression: list, has_accessed_tweak: bool = False) -> Node:
    # Mirrors Logic.check_logical_expression_req.
    kind = None
    children = []
    tokens = list(reversed(logical_expression))
    while tokens:
      token = tokens.pop()
      if token == "|":
        assert kind != "and"
        kind = "or"
      elif token == "&":
        assert kind != "or"
        kind = "and"
      elif token == "(":
        children.append(self.expression(tokens.pop(), has_accessed_tweak))
        assert tokens.pop() == ")"
      else:
        children.append(self.req(token, has_accessed_tweak))
    if kind == "or":
      return or_(*children)
    return and_(*children)

  def location_need(self, location_name: str) -> Node:
    key = "\0location " + location_name
    if key in self.memo:
      return self.memo[key]
    assert key not in self.stack, f"Recursive location requirement: {location_name!r}"
    self.stack.append(key)
    need = self.logic.item_locations[location_name]["Need"]
    result = self.expression(need, has_accessed_tweak=location_name in HAS_ACCESSED_LOCATION_TWEAK_LOCATIONS)
    self.stack.pop()
    self.memo[key] = result
    return result

  def has_accessed(self, location_name: str) -> Node:
    # The website's "Has Accessed Other Location": checked, or in logic. Locations the tracker doesn't track can't be
    # checked, so only their requirements count.
    need = self.location_need(location_name)
    if location_name in self.location_index:
      return or_(checked(self.location_index[location_name]), need)
    return need

  def compile(self) -> CompiledLogic:
    roots = [self.location_need(name) for name in self.location_names]
    return _emit(roots, self.req(GOAL_REQUIREMENT))


class _LogicRandoStub:
  # Logic only needs the options until it's initialized from the randomizer's state, which the compiler doesn't do.
  def __init__(self, options: Options):
    self.options = options
    self.fully_initialized = False


def _vanilla_exit_for_entrance(entrance_name: str) -> str | None:
  for zone_exit, zone_entrance in _vanilla_exit_to_entrance().items():
    if zone_entrance.entrance_name == entrance_name:
      return zone_exit.unique_name
  return None

def _vanilla_exit_to_entrance():
  from tracker.locations import VANILLA_EXIT_TO_ENTRANCE
  return VANILLA_EXIT_TO_ENTRANCE


def _emit(location_roots: list[Node], goal: Node | None = None) -> CompiledLogic:
  # The goal is emitted like a location, after them.
  roots = location_roots + ([goal] if goal is not None else [])
  # Count how many times each subexpression is used, over the whole DAG (each use of a shared node counts once per
  # parent occurrence, not per expanded path).
  use_counts: dict[Node, int] = {}
  def count_uses(node: Node):
    use_counts[node] = use_counts.get(node, 0) + 1
    if use_counts[node] > 1:
      return
    for child in node.children:
      count_uses(child)
  for root in roots:
    count_uses(root)

  # Inline size of each node in bytes, given which nodes are slots (decided bottom-up).
  slot_of: dict[Node, int] = {}
  emitted_size: dict[Node, int] = {}
  items: dict[str, int] = {}

  def leaf_size(node: Node) -> int:
    match node.kind:
      case "true" | "false": return 1
      case "has": return 2 if node.args[1] == 1 else 3
      case "visited": return 1
      case "checked": return 3
    raise Exception(f"Unknown node: {node}")

  def inline_size(node: Node) -> int:
    if node in emitted_size:
      return emitted_size[node]
    if node.children:
      size = 0
      for child in node.children:
        size += CALL_SIZE if child in shared else inline_size(child)
      size += 2 * ((len(node.children) - 2) // 254 + 1)
    else:
      size = leaf_size(node)
    emitted_size[node] = size
    return size

  # Decide which nodes are shared (given their own slot): used more than once, and calling is cheaper than inlining.
  shared: set[Node] = set()
  order: list[Node] = []
  visited_nodes: set[Node] = set()
  def post_order(node: Node):
    if node in visited_nodes:
      return
    visited_nodes.add(node)
    for child in node.children:
      post_order(child)
    order.append(node)
  for root in roots:
    post_order(root)
  for node in order:
    if not node.children:
      continue
    uses = use_counts[node]
    size = inline_size(node)
    if uses > 1 and size*uses > size + 1 + CALL_SIZE*uses:
      shared.add(node)

  code = bytearray()
  depth = 0
  max_depth = 0
  num_slots = 0

  def push():
    nonlocal depth, max_depth
    depth += 1
    max_depth = max(max_depth, depth)

  def item_index(item_name: str) -> int:
    if item_name not in items:
      items[item_name] = len(items)
      assert len(items) <= MAX_ITEMS, "Too many items in the tracker logic"
    return items[item_name]

  # Stack space each node needs. Children are emitted from the most demanding to the least (Sethi-Ullman), since each
  # one's result stays on the stack while the next ones are evaluated.
  stack_need: dict[Node, int] = {}
  def children_in_emit_order(node: Node) -> list[Node]:
    return sorted(node.children, key=lambda child: -get_stack_need(child))
  def get_stack_need(node: Node) -> int:
    if node in slot_of or not node.children:
      return 1
    if node not in stack_need:
      stack_need[node] = max(i + get_stack_need(child) for i, child in enumerate(children_in_emit_order(node)))
    return stack_need[node]
  
  def emit_node(node: Node, top_level: bool = False):
    nonlocal depth
    if node in slot_of and not top_level:
      code.extend((OP_CALL, *struct.pack(">H", slot_of[node])))
      push()
      return
    match node.kind:
      case "true":
        code.append(OP_TRUE); push()
      case "false":
        code.append(OP_FALSE); push()
      case "has":
        item_name, count = node.args
        index = item_index(item_name)
        if count == 1:
          code.extend((OP_HAS1, index))
        else:
          assert count <= 255
          code.extend((OP_HAS, index, count))
        push()
      case "visited":
        assert node.args[0] < MAX_VISITED
        code.append(OP_VISITED | node.args[0]); push()
      case "checked":
        code.extend((OP_CHECKED, *struct.pack(">H", node.args[0]))); push()
      case "and" | "or":
        op = OP_AND if node.kind == "and" else OP_OR
        children = children_in_emit_order(node)
        emit_node(children[0])
        pending = 1
        for child in children[1:]:
          emit_node(child)
          pending += 1
          if pending == 255:
            code.extend((op, pending)); depth -= pending - 1
            pending = 1
        if pending > 1:
          code.extend((op, pending)); depth -= pending - 1
      case _:
        raise Exception(f"Unknown node: {node}")

  def store():
    nonlocal depth, num_slots
    code.append(OP_STORE)
    depth -= 1
    assert depth == 0

  # Shared nodes first, in dependency order (post-order puts children before parents).
  for node in order:
    if node in shared:
      emit_node(node, top_level=True)
      store()
      slot_of[node] = num_slots
      num_slots += 1
  for root in roots:
    emit_node(root)
    store()
  code.append(OP_END)

  assert max_depth <= MAX_STACK_DEPTH, f"Tracker logic needs a stack of {max_depth}"
  return CompiledLogic(bytes(code), num_slots, len(location_roots), max_depth, list(items), location_roots, goal)


def compile_tracker_logic(inp: TrackerLogicInput, location_names: Sequence[str], tracked_entrances: Mapping[str, int]) -> CompiledLogic:
  """
  location_names: the tracked locations in table order (TrackerLocationSet).
  tracked_entrances: entrance name -> visited bit index, for the entrances the tracker tracks (TrackerEntranceSet).
  """
  return _Compiler(inp, location_names, tracked_entrances).compile()


# Reference evaluator

@dataclass
class LogicState:
  item_counts: Mapping[str, int] = field(default_factory=dict)
  visited: set[int] = field(default_factory=set)
  checked: set[int] = field(default_factory=set)


def evaluate_bytecode(blob: bytes, item_names: Sequence[str], state: LogicState) -> list[bool]:
  """Runs a serialized LOGIC section the way the C interpreter does. Returns each location's result."""
  return evaluate_bytecode_with_goal(blob, item_names, state)[0]


def evaluate_bytecode_with_goal(blob: bytes, item_names: Sequence[str], state: LogicState) -> tuple[list[bool], bool | None]:
  """Like evaluate_bytecode, and also returns the goal's result (None without a goal slot)."""
  num_slots, num_locations, max_stack, num_items, code_size, num_goals = struct.unpack_from(LOGIC_HEADER_FORMAT, blob, 0)
  assert num_items == len(item_names)
  code = blob[LOGIC_HEADER_SIZE:LOGIC_HEADER_SIZE+code_size]
  counts = [state.item_counts.get(name, 0) for name in item_names]
  results: list[bool] = []
  stack: list[bool] = []
  pc = 0
  while True:
    op = code[pc]
    pc += 1
    if op == OP_END:
      break
    elif op == OP_TRUE:
      stack.append(True)
    elif op == OP_FALSE:
      stack.append(False)
    elif op == OP_STORE:
      results.append(stack.pop())
    elif op in (OP_AND, OP_OR):
      n = code[pc]; pc += 1
      values = stack[-n:]
      del stack[-n:]
      stack.append(all(values) if op == OP_AND else any(values))
    elif op == OP_HAS:
      stack.append(counts[code[pc]] >= code[pc+1]); pc += 2
    elif op == OP_HAS1:
      stack.append(counts[code[pc]] >= 1); pc += 1
    elif op == OP_CHECKED:
      stack.append(struct.unpack_from(">H", code, pc)[0] in state.checked); pc += 2
    elif op == OP_CALL:
      slot = struct.unpack_from(">H", code, pc)[0]; pc += 2
      assert slot < len(results)
      stack.append(results[slot])
    elif op & 0xC0 == OP_VISITED:
      stack.append((op & 0x3F) in state.visited)
    else:
      raise Exception(f"Bad opcode 0x{op:02X} at {pc-1}")
    assert len(stack) <= max_stack
  assert not stack and len(results) == num_slots + num_locations + num_goals
  goal = results[num_slots + num_locations] if num_goals else None
  return results[num_slots:num_slots + num_locations], goal


def evaluate_node(node: Node, state: LogicState, cache: dict | None = None) -> bool:
  """Evaluates an expression tree directly (independently of the bytecode)."""
  if cache is None:
    cache = {}
  if node in cache:
    return cache[node]
  match node.kind:
    case "true": result = True
    case "false": result = False
    case "has": result = state.item_counts.get(node.args[0], 0) >= node.args[1]
    case "visited": result = node.args[0] in state.visited
    case "checked": result = node.args[0] in state.checked
    case "and": result = all(evaluate_node(child, state, cache) for child in node.children)
    case "or": result = any(evaluate_node(child, state, cache) for child in node.children)
    case _: raise Exception(f"Unknown node: {node}")
  cache[node] = result
  return result
