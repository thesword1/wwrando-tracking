"""Regression test for gclib.bunfoe on Python 3.14.

issubclass(list[u16], X) raises TypeError on 3.14 (returned False on <=3.12), so
BUNFOE fields typed as GenericAlias (list[...], FixedStr[N], MagicStr[N]) crashed
in get_byte_size/read_value/write_value before reaching the GenericAlias branches.
A small BUNFOE class with such fields must round-trip through bytes on both.
"""

import sys
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from enum import Enum

from gclib.bunfoe import BUNFOE, bunfoe, field
from gclib.fs_helpers import FixedStr, MappedBool, u16, u8


class _ChoiceEnum(u8, Enum):
    A = 0
    B = 1


@bunfoe
class _GenericAliasFields(BUNFOE):
    magic: FixedStr[4] = field(default="ABC")
    values: list[u16] = field(length=3, default_factory=lambda: [1, 2, 3])
    flag: MappedBool = False
    choice: _ChoiceEnum = _ChoiceEnum.A


def test_generic_alias_fields_roundtrip():
    original = _GenericAliasFields()
    buffer = BytesIO()
    original.data = buffer
    original.save(0)

    restored = _GenericAliasFields()
    restored.data = BytesIO(buffer.getvalue())
    restored.read(0)

    assert restored.magic == "ABC"
    assert restored.values == [1, 2, 3]
    assert isinstance(restored.flag, MappedBool)
    assert bool(restored.flag) is False
    assert restored.choice is _ChoiceEnum.A
