# Memory map for the in-game tracker (NTSC-U, GZLE01)

Developer reference for the tracker runtime (Phase 4). Every address is for the
North American release (GZLE01). The randomizer changes the game ID to GZLE99,
but that doesn't move any RAM.

Sources:

- **decomp** means [zeldaret/tww](https://github.com/zeldaret/tww) at the
  commit cloned on 2026-10-08. `d_save.cpp`, `d_s_name.cpp`, `m_Do_MemCard*.cpp`
  and `d_menu_fmap.cpp` are all marked `Matching` for GZLE01 in its
  `configure.py`, so the struct layouts and code below are byte-accurate.
  `d_menu_fmap2.cpp` is `NonMatching`.
- **symbols** means `config/GZLE01/symbols.txt` in that repo.
- **rando** means this repository (`asm/patches/*.asm`, `asm/linker.ld`,
  `asm/custom_symbols.txt`, `tweaks.py`).
- **AP** means `worlds/tww/TWWClient.py` and `Locations.py` in Archipelago.

The base of everything is `g_dComIfG_gameInfo = 0x803C4C08` (symbols;
rando `asm/linker.ld:2`). Its layout is `dComIfG_inf_c`
(`include/d/d_com_inf_game.h:914`):

| Offset | Address | Member |
|---|---|---|
| +0x00000 | 0x803C4C08 | `dSv_info_c save` (size 0x12A0) |
| +0x012A0 | 0x803C5EA8 | `dComIfG_play_c play` |
| +0x05D1C | 0x803CA924 | `dDlst_list_c drawlist` |

---

## 1. Save data: `dSv_info_c` / `dSv_save_c`

Layout from `include/d/d_save.h`. `dSv_info_c` starts with `dSv_save_c mSavedata`.
`mSavedata` is the part that gets written to the memory card. The rest is
runtime-only state.

### 1.1 `dSv_info_c` (0x803C4C08, size 0x12A0)

| Offset | Address | Member | Saved to card? |
|---|---|---|---|
| +0x0000 | 0x803C4C08 | `dSv_save_c mSavedata` (0x778) | yes (packed, see 1.3) |
| +0x0778 | 0x803C5380 | `dSv_memory_c mMemory`: live copy of the **current** stage's flags | no (copied in and out of `mSavedata.mMemory[]`) |
| +0x079C | 0x803C53A4 | `dSv_danBit_c mDan`. `mStageNo` (s8) at 0x803C53A4 is the current stage-save index | no |
| +0x07A8 | 0x803C53B0 | `dSv_zone_c mZone[0x20]` (per-room zone bits) | no |
| +0x1128 | 0x803C5D30 | `dSv_restart_c mRestart` | no |
| +0x1158 | 0x803C5D60 | `dSv_event_c mTmp` (temporary event bits; rando uses them at `custom_funcs.asm:161`) | no |
| +0x1258 | 0x803C5E60 | `dSv_turnRestart_c mTurnRestart` | no |
| +0x1290 | 0x803C5E98 | `mDataNum` (selected file slot), `mNewFile`, `mNoFile` | no |
| +0x1298 | 0x803C5EA0 | `u64 mMemCardCheckID` | no |

### 1.2 `dSv_save_c mSavedata` (0x803C4C08, size 0x778)

| Offset | Address | Member | Size |
|---|---|---|---|
| +0x000 | 0x803C4C08 | `dSv_player_c mPlayer` | 0x380 |
| +0x380 | 0x803C4F88 | `dSv_memory_c mMemory[16]` (stage save info, stride 0x24) | 0x240 |
| +0x5C0 | 0x803C51C8 | `dSv_ocean_c mOcean` (`u16[50]`, one per sea room; AP Big Octo checks) | 0x64 |
| +0x624 | 0x803C522C | `dSv_event_c mEvent` (`u8 mFlags[0x100]`) | 0x100 |
| **+0x724** | **0x803C532C** | **`dSv_reserve_c mReserve` (`u8 mReserve[0x50]`)** | **0x50** |
| +0x774 | 0x803C537C | 4 bytes of alignment padding (**not** saved) | 4 |

### 1.3 What gets written to the memory card

`dSv_info_c::memory_to_card` (`src/d/d_save.cpp:1703`, 0x8005E7xx) and
`card_to_memory` (`d_save.cpp:1794`, 0x8005EA24) copy these in order: every
`dSv_player_c` sub-struct (packed, no padding), then `mMemory[16]`, `mOcean`,
`mEvent`, and finally **`mReserve`, all 0x50 bytes**:

```c
memcpy(buffer, dComIfGs_getPReserve(), sizeof(dSv_reserve_c));   // d_save.cpp:1780
memcpy(dComIfGs_getPReserve(), buffer, sizeof(dSv_reserve_c));   // d_save.cpp:1867
```

The packed card image is `dSv_save_c_PACKED`, size 0x768
(`d_save.h`, `STATIC_ASSERT`). Each card slot is
`card_gamedata { u8 data[0x768]; u64 csum; }`
(`include/m_Do/m_Do_MemCardRWmng.h:29`), so the reserve area is covered by the
slot checksum. `initdata_to_card` (`d_save.cpp:~2007`) writes a zeroed
`dSv_reserve_c` into fresh slots.

### 1.4 Verdict: 0x803C532C–0x803C537B is safe tracker storage (0x50 bytes)

**The region is safe to use.** The tracker gets the 80 bytes at
0x803C532C–0x803C537B. The 4 bytes at 0x803C537C–0x803C537F are padding
and are not saved. Don't use them.

Here's the evidence:

1. **It's saved and loaded.** `mReserve` is copied to and from the card in full
   (1.3).
2. **Vanilla never uses it.** In the decomp, the only references to
   `dSv_reserve_c` and `getPReserve` are `dSv_reserve_c::init` (0x8005CB94),
   `memory_to_card`, `card_to_memory` and `initdata_to_card`. To check the
   compiled game itself, the vanilla GZLE01 `main.dol` was scanned:
   - Every D-form instruction with an immediate in 0x532C–0x537F was listed.
     All 23 hits are either `li` constants (rA = 0) or follow a `lis` whose high
     half isn't 0x803C, so none of them is an absolute access to the region.
   - Every `addi rX, rY, 0x4C08` (4343 loads of `g_dComIfG_gameInfo`) was
     followed by a check for any use of rX with an offset in 0x724–0x777. The
     only hits were `memory_to_card` (0x8005E9B4) and `card_to_memory`
     (0x8005EC8C). A third hit at 0x800DFD28 turned out to be inside an
     unrelated function (`daBomb2::Act_c::carry_fuse_start`) where the register
     had been reassigned.

   The `.rel` actors weren't scanned. They reach save data through the inline
   `dComIfGs_*` accessors, and the decomp shows no `getPReserve` caller
   anywhere.
3. **The randomizer and the AP branch never use it.** There are no references to
   0x803C532C–0x803C537F (absolute, or as a gameInfo offset of 0x724–0x777) in
   `asm/patches/*.asm`, `asm/custom_symbols.txt`, `asm/linker.ld` or any
   `*.py`. The highest save address that AP's `Locations.py` uses is event byte
   0x803C532B (`mEvent` byte 0xFF). AP's received-item index uses event bytes
   0x60–0x61 (0x803C528C). The randomizer's custom flags use event bytes
   0x69 and 0x6A (for example, the Tingle statues are event bits 0x6A04–0x6A40,
   `custom_funcs.asm:1441`). All of these are inside `mEvent`, not `mReserve`.

**Caveat: a new game does not clear it.** `dSv_save_c::init`
(`d_save.cpp:1494`) initialises player, memory, ocean and event, but **not
`mReserve`**. `dSv_reserve_c::init` only runs from `initdata_to_card`. A new file
goes through `dScnName_c::NameInMain`, which calls `dComIfGs_init()`, which calls
`dSv_info_c::init` (`d_s_name.cpp:1373`). That never touches the reserve, so RAM
can still hold the reserve bytes from whichever file was loaded earlier in the
session. The tracker must therefore **zero the 0x50 bytes in
`init_save_with_tweaks`** (`custom_funcs.asm:6`). That function replaces the
`bl init__10dSv_save_cFv` at 0x8005D618 inside `dSv_info_c::init`
(`misc_rando_features.asm:8`). Loading an existing file (`card_to_memory`,
`d_s_name.cpp:1213`) restores the saved bytes afterwards, so this is safe.

A Second Quest ("extra") file is started by loading the cleared file without
calling `dComIfGs_init` (`d_s_name.cpp:1214`), so it inherits that file's
tracker bytes. Since every randomizer file is a fresh new game, this doesn't
matter for the tracker. Another reason for the seed tag below.

#### Proposed tracker layout in `mReserve`

| Reserve offset | Address | Size | Contents |
|---|---|---|---|
| 0x00 | 0x803C532C | 1 | layout version (0 means uninitialised) |
| 0x01 | 0x803C532D | 1 | flags (reserved) |
| 0x02 | 0x803C532E | 2 | seed tag (u16 hash written at patch time, so a save from another seed is detected and its tracker data ignored or reset) |
| 0x04 | 0x803C5330 | 6 | small keys **obtained** per dungeon: DRC, FW, TotG, ET, WT, spare |
| 0x0A | 0x803C5336 | 6 | spare |
| 0x10 | 0x803C533C | 48 | manual-mark bits, 384 bits, room for 321 locations |
| 0x40 | 0x803C536C | 8 | visited-entrance bits, 64 bits, room for about 60 entrances |
| 0x48 | 0x803C5374 | 8 | spare |

That's 0x50 bytes in total. 0x803C532C is word-aligned, and the two bitfields
start on 16-byte boundaries (0x10 and 0x40), so they can be read as `u32` words.

#### Fallbacks (not needed; listed in case the layout must grow)

None of these are verified as free. Each would need the same DOL scan before use.

- Event bytes that nothing references (`mEvent`, 0x803C522C + n). Collect
  unused bytes by cross-checking `include/d/d_save_event_flag.inc`, the rando
  ASM and AP.
- The `dSv_memory_c` slot for `STAGE_TEST` (index 0xF, 0x803C51A4, 0x24 bytes).
  This is a debug stage, but the rando's `test_room.asm` can load test stages,
  so check before using it.
- Unused fields in `dSv_player_info_c` (`field_0x25[17]`, `field_0x36[17]`)
  and `dSv_player_map_c` (`field_0x71[16]`). Their purpose is unknown, so they
  would need to be verified.

---

## 2. Stage save info: `dSv_memory_c` / `dSv_memBit_c` (0x24 bytes)

`mSavedata.mMemory[i]` is at 0x803C4F88 + 0x24·i. The live copy for the
current stage is at 0x803C5380. `dSv_info_c::getSave`/`putSave`
(`d_save.cpp:1506`) copy between the two on stage load and unload. **While
the player is inside stage `i`, the live copy is authoritative.** Read
0x803C5380 when the stage index at 0x803C53A4 equals `i`, and the saved slot
otherwise. AP does the same (`CURR_STAGE_*` in `TWWClient.py`).

| Offset | Member | Notes |
|---|---|---|
| +0x00 | `u32 mTbox` | chest-opened bits (`isTbox`: `mTbox & (1 << no)`) |
| +0x04 | `u32 mSwitch[4]` | 128 switch bits: `mSwitch[no >> 5] & (1 << (no & 31))` |
| +0x14 | `u32 mItem[1]` | pickup bits |
| +0x18 | `u32 mVisitedRoom[2]` | visited-room bits |
| +0x20 | `u8 mKeyNum` | **current** small keys (goes down when one is used) |
| +0x21 | `u8 mDungeonItem` | bit0 map, bit1 compass, bit2 big key, bit3 boss defeated, bit4 heart container taken, bit5 boss demo (`dSv_memBit_c` enum) |

All of these are big-endian `u32`s. Bit *n* of word *w* is in the byte at
`base + 4w + 3 - (n >> 3)`, with mask `1 << (n & 7)`.

Stage-save indices (`dSv_save_c::SaveStageTbl`):

| Index | Name | Slot address | `mKeyNum` address |
|---|---|---|---|
| 0x0 | Sea | 0x803C4F88 | |
| 0x1 | Sea (alt) | 0x803C4FAC | |
| 0x2 | Forsaken Fortress | 0x803C4FD0 | |
| 0x3 | Dragon Roost Cavern | 0x803C4FF4 | 0x803C5014 |
| 0x4 | Forbidden Woods | 0x803C5018 | 0x803C5038 |
| 0x5 | Tower of the Gods | 0x803C503C | 0x803C505C |
| 0x6 | Earth Temple | 0x803C5060 | 0x803C5080 |
| 0x7 | Wind Temple | 0x803C5084 | 0x803C50A4 |
| 0x8 | Ganon's Tower | 0x803C50A8 | |
| 0x9 | Hyrule | 0x803C50CC | |
| 0xA | Ship interiors | 0x803C50F0 | |
| 0xB | Misc (mostly interiors) | 0x803C5114 | |
| 0xC | Sub-dungeons (caves) | 0x803C5138 | |
| 0xD | Sub-dungeons (added later) | 0x803C515C | |
| 0xE | Blue Chu Jelly / misc | 0x803C5180 | |
| 0xF | Test | 0x803C51A4 | |

**Small-key logic (D12):** `mKeyNum` is the current count, not the number
obtained, so the tracker keeps its own "obtained" counter in `mReserve`
(1.4). Keys reach `mKeyNum` in three ways:

- `item_func_small_key` (0x800C31B0) calls `dComIfGp_setItemKeyNumCount(1)`.
  This is a pending delta in `play.mItemKeyNumCount` (+0x48D4, 0x803CA77C)
  that the HUD applies to the live `mKeyNum`.
- The rando's `generic_small_key_item_get_func` (`custom_funcs.asm:1015`,
  `asm/custom_symbols.txt`) is reached through the per-dungeon wrappers
  `drc_`/`fw_`/`totg_`/`et_`/`wt_small_key_item_get_func`, which are item IDs
  0x13, 0x1D, 0x5B, 0x73 and 0x77 (`tweaks.py:608`). It either adds to the other
  dungeon's saved slot, adds to the live slot, or falls through to the vanilla
  function.

Hook the five per-dungeon wrappers. Each wrapper knows its own dungeon, so this
works whether or not the key is picked up inside that dungeon. AP deliveries
also go through `execItemGet`, so they're counted too.

---

## 3. Inventory and progress addresses (`dSv_player_c`, 0x803C4C08)

`dSv_player_c` offsets come from `d_save.h`. Semantics come from the
`item_func_*` implementations in `src/d/d_item.cpp`.

### 3.1 Status (`dSv_player_status_a_c`, 0x803C4C08)

| Address | Field | Meaning |
|---|---|---|
| 0x803C4C08 | `u16 mMaxLife` | quarter hearts |
| 0x803C4C0A | `u16 mLife` | AP `CURR_HEALTH_ADDR` |
| 0x803C4C0C | `u16 mRupee` | |
| 0x803C4C11 | `u8 mSelectItem[5]` | X/Y/Z item slot assignments |
| 0x803C4C16 | `u8 mSelectEquip[4]` | [0] equipped sword item, [1] shield, [2] bracelets |
| 0x803C4C1A | `u8 mWalletSize` | 0 = 200, 1 = 1000, 2 = 5000 (`getRupeeMax`) |
| 0x803C4C1B | `u8 mMaxMagic` | 0 = none, 16 = magic meter, 32 = double magic (`item_func_max_mp_up1` adds 32) |
| 0x803C4C1C | `u8 mMagic` | |

### 3.2 Item slots (`dSv_player_item_c mItems[21]`, 0x803C4C44)

0xFF means empty. Slot index (`dInvSlot_*_e`, `d_com_inf_game.h:1072`) → address:

| Slot | Address | Item (values) |
|---|---|---|
| 0 | 0x803C4C44 | Telescope |
| 1 | 0x803C4C45 | Sail |
| 2 | 0x803C4C46 | Wind Waker |
| 3 | 0x803C4C47 | Grappling Hook |
| 4 | 0x803C4C48 | Spoils Bag |
| 5 | 0x803C4C49 | Boomerang |
| 6 | 0x803C4C4A | Deku Leaf |
| 7 | 0x803C4C4B | Tingle Tuner |
| 8 | 0x803C4C4C | Picto Box (0x23) / Deluxe Picto Box (0x26) |
| 9 | 0x803C4C4D | Iron Boots |
| 10 | 0x803C4C4E | Magic Armor |
| 11 | 0x803C4C4F | Bait Bag |
| 12 | 0x803C4C50 | Bow (0x27) / Fire & Ice Arrows (0x35) / Light Arrows (0x36) |
| 13 | 0x803C4C51 | Bombs |
| 14–17 | 0x803C4C52–55 | Bottles (non-0xFF means owned) |
| 18 | 0x803C4C56 | Delivery Bag |
| 19 | 0x803C4C57 | Hookshot |
| 20 | 0x803C4C58 | Skull Hammer |

`dSv_player_get_item_c mItemFlags[21]` at **0x803C4C59** holds "ever owned"
bits per slot (`onItem(slot, bit)`). Progressive items set different bits:
Bow bit0, Fire & Ice Arrows bit1, Light Arrows bit2 (slot 12, byte 0x803C4C65);
Picto bit0, Deluxe bit1 (slot 8, 0x803C4C61). **For logic, use these bits rather
than the slot value.**

### 3.3 Ammo, capacities and bags

| Address | Field |
|---|---|
| 0x803C4C70 | picture count |
| 0x803C4C71 | arrows |
| 0x803C4C72 | bombs |
| 0x803C4C77 | **arrow capacity** (30 / 60 / 99) |
| 0x803C4C78 | **bomb capacity** (30 / 60 / 99) |
| 0x803C4C7E | spoils bag contents `[8]` |
| 0x803C4C86 | bait bag contents `[8]` |
| 0x803C4C8E | delivery bag contents `[8]` (AP `LETTER_BASE_ADDR`) |
| 0x803C4C98 | `u32` delivery-bag ever-owned bits (`onReserve(i)`; AP `LETTER_OWND_ADDR`) |
| 0x803C4C9C | spoils ever-owned bits |
| 0x803C4C9D | bait ever-owned bits |

### 3.4 Collection (`dSv_player_collect_c`, 0x803C4CBC)

| Address | Field | Bits |
|---|---|---|
| 0x803C4CBC | `mCollect[0]` | swords: bit0 Hero's Sword, bit1 Master Sword (powerless), bit2 half power, bit3 full power |
| 0x803C4CBD | `mCollect[1]` | shields: bit0 Hero's Shield, bit1 Mirror Shield |
| 0x803C4CBE | `mCollect[2]` | bit0 Power Bracelets |
| 0x803C4CBF | `mCollect[3]` | bit0 Pirate's Charm |
| 0x803C4CC0 | `mCollect[4]` | bit0 Hero's Charm |
| 0x803C4CC5 | `mTact` | songs: bit0 Wind's Requiem, 1 Ballad of Gales, 2 Command Melody, 3 Earth God's Lyric, 4 Wind God's Aria, 5 Song of Passing (`item_func_tact_song1..6`, item IDs 0x6D–0x72) |
| 0x803C4CC6 | `mTriforce` | Triforce shards bit0–7 (`getTriforceNum` 0x8005B230 counts them) |
| 0x803C4CC7 | `mSymbol` | pearls: bit0 Nayru's, bit1 Din's, bit2 Farore's (`dSymbol_*_e`) |

### 3.5 Charts (`dSv_player_map_c`, 0x803C4CCC)

Four 128-bit tables of `u32[4]`. Chart number *N* (1-based `collectMapNo`) uses
bit index *N−1* (`dComIfGs_*CollectMap(N)` call `…Map(N-1)`):

| Address | Table | Set by |
|---|---|---|
| 0x803C4CCC | `field_0x0[0]` | (unused by the map functions) |
| 0x803C4CDC | **GetMap: chart owned** | `item_func_collectmapN` → `onGetMap`. Item ID = 0xFF − N, e.g. 0xC2 = chart 61 and 0xFE = chart 1. The same function also **clears** the Open and Complete bits for that chart |
| 0x803C4CEC | OpenMap: chart deciphered/opened | `dMenu_Fmap2_c` (`d_menu_fmap2.cpp:978`) |
| 0x803C4CFC | **CompleteMap: treasure salvaged** | `daSalvage` (`d_a_salvage.cpp:510`). This is AP's `CHARTS_BITFLD_ADDR` |

`mFmapBits[49]` at 0x803C4D0C has one byte per sea square (island index).
bit0 = square visited ("arrive grid", `isSaveArriveGrid`), bit1 = the GBA
equivalent. The Triforce-chart deciphered bits are in `field_0x81` at
0x803C4D4D.

Accessors: `isGetMap__16dSv_player_map_cFi` 0x8005B3CC,
`isCompleteMap__16dSv_player_map_cFi` 0x8005B7DC,
`isOpenMap__16dSv_player_map_cFi` 0x8005B5D4.

### 3.6 Events

`dSv_event_c` at 0x803C522C. Bit ID `0xBBMM` means byte `BB`, mask `MM`
(`onEventBit`: `mFlags[id >> 8] |= id & 0xFF`, `d_save.cpp:1187`).
`isEventBit__11dSv_event_cFUs` = 0x8005CB34.

- Tingle statues owned (rando custom bits): 0x6A04 Dragon, 0x6A08 Forbidden,
  0x6A10 Goddess, 0x6A20 Earth, 0x6A40 Wind. That's byte 0x803C5296
  (`custom_funcs.asm:1434`–1514).
- Tingle Island statue *rewards* (location checks, AP): 0x803C523E bit 0x40,
  0x803C5249 bits 0x0F.
- AP received-item index: event bytes 0x60–0x61 (0x803C528C, u16).

### 3.7 Current stage, room and spawn (`dComIfG_play_c`, 0x803C5EA8)

| Address | Field |
|---|---|
| 0x803C53A4 | `mDan.mStageNo` (s8): current stage-save index (AP `CURR_STAGE_ID_ADDR`) |
| 0x803C9D3C | `play.mCurStage.mName[8]` (+0x3E94): current stage name, e.g. `"sea"`, `"M_NewD2"` (AP `CURR_STAGE_NAME_ADDR`) |
| 0x803C9D44 | `mCurStage.mPoint` (s16): spawn ID |
| 0x803C9D46 | `mCurStage.mRoomNo` (s8) |
| 0x803C9D47 | `mCurStage.mLayer` (s8) |
| 0x803C9D48 | `play.mNextStage` (`dStage_nextStage_c`: name[8], point s16 @+8, room s8 @+0xA, layer @+0xB, `mEnable` @+0xC = 0x803C9D54) |
| 0x803F6A78 | `dStage_roomControl_c::mStayNo` (current room the player is in) |
| 0x803CA908 | `play.mCurrentGrafPort` (`J2DOrthoGraph*`, +0x4A60) |

`dComIfGp_setNextStage__FPCcsScScfUliSc` (0x800537C8) is the common entry
point that doors, exits and warps use to request a stage change, with the
destination's name, spawn and room as arguments. Even so, the safer hook for
"entrance visited" bits is reading `mCurStage` (0x803C9D3C) once the new
stage has loaded, because that catches every path into a stage.

### 3.8 Item-get path

| Symbol | Address |
|---|---|
| `execItemGet__FUc` | 0x800C2DFC: `item_func_ptr[itemNo]()` (`d_item.cpp:534`) |
| `item_func_ptr` | 0x803888C8 (`.data`, `ItemGetFunc*[0x100]`). The rando overwrites entries (`tweaks.py:268,604`) |
| `checkItemGet__FUci` | 0x800C2E30 |
| `dComIfGs_checkGetItemNum__FUc` | 0x80053F70 |
| `item_func_small_key__Fv` | 0x800C31B0 |
| rando custom item funcs | `asm/custom_symbols.txt` (for example `progressive_*_item_func`, `*_small_key_item_get_func`, `give_archipelago_item` 0x803FE818) |
| AP give-item array | `give_archipelago_item_array` (0x803FE87C now). It moves when custom code grows, so always resolve it through `custom_symbols.txt` |

`execItemGet` is called from field pickups (`d_a_item.cpp`), the item-get
demo (`d_a_demo_item.cpp`, used by chests and gifts), shops
(`d_shop.cpp:1398`), several NPCs (`d_a_npc_*`), `d_a_race_item_static.cpp`
and the AP give queue. Hooking the start of `execItemGet` is enough for an "inventory
changed, re-evaluate logic" dirty flag.

---

## 4. Sea chart menu: `dMenu_Fmap_c`

The source is `src/d/d_menu_fmap.cpp` (Matching on GZLE01). The window code
that opens and closes it is `src/d/d_menu_window.cpp`. The Y-button "compare
charts" page is the separate `dMenu_Fmap2_c` (`d_menu_fmap2.cpp`, NonMatching),
owned as member `mFmap2`.

### 4.1 Key methods (symbols)

| Method | Address | Role |
|---|---|---|
| `_create__12dMenu_Fmap_cFv` | 0x801AF848 | allocs, screen setup |
| `screenSet__12dMenu_Fmap_cFv` | 0x801AFBDC | loads the `.blo` panes |
| `initialize__12dMenu_Fmap_cFv` | 0x801B06D4 | |
| `_open__12dMenu_Fmap_cFv` | 0x801B4B44 | open animation (normal mode) |
| `_close__12dMenu_Fmap_cFv` | 0x801B4C0C | |
| `isFmapClose__12dMenu_Fmap_cFv` | 0x801B190C | polled by the window code |
| `_move__12dMenu_Fmap_cFv` | 0x801B4D78 | per-frame input. Switches on `mFmapMode` (normal / warp / wallpaper / fishman) |
| `move_normal__12dMenu_Fmap_cFv` | 0x801B65D8 | `mainProc[mMainProcIdx]` |
| `FmapProc__12dMenu_Fmap_cFv` | 0x801B6610 | normal sea chart. **Checks Y first**, then calls `FmapProcMain` |
| `FmapProcMain__12dMenu_Fmap_cFv` | 0x801B4F40 | close check, then `fmapProcMain[mFmapProcIdx]` (zoom state machine) |
| `SelectGrid__12dMenu_Fmap_cFv` | 0x801B5034 | world view: stick moves the cursor, A zooms in |
| `zoom1000x1000Init__12dMenu_Fmap_cFv` | 0x801B5878 | entering square (sector) view |
| `ZoomGridLv1Proc__12dMenu_Fmap_cFv` | 0x801B5D6C | **square view** input (A = detail zoom, B = back) |
| `ZoomGridLv2Proc__12dMenu_Fmap_cFv` | 0x801B6388 | detail (island) view input (B = back) |
| `HikakuProc` / `fmap2Open` / `fmap2Move` / `fmap2Close` | 0x801B66DC / 0x801B6714 / 0x801B678C / 0x801B68A0 | Y "compare" sub-page |
| `islandNameChange` / `changeIslandName` | 0x801B1CF0 / 0x801B1D48 | island name box text |
| `getButtonIconMode__12dMenu_Fmap_cFv` | 0x801BAFCC | which button-help icons are shown |
| `_draw__12dMenu_Fmap_cFv` | 0x801B4E14 | queues `fmapDl` on `set2DOpa`, plus `mFmap2._draw()` on the compare page |
| `draw__12dDlst_FMAP_cFv` | 0x801BB024 | the display-list callback that actually draws the screen |
| `_open_warpMode` / `moveMain_warpMode` / `wrapMove` | 0x801B78B0 / 0x801B7EA8 / 0x801B7EF8 | Ballad of Gales warp chart (rando already patches `wrapMove` at 0x801B80EC) |

The cursor and zoom state is kept in the `fmapSv` save object (the getters in
`d_menu_fmap.h`):

- `getCtCurX/Y()`: −3..3. Square index is `(x + 3) + (y + 3) * 7`, from 0 to 48.
  Sea square number = index + 1.
- `getCtFmapZoom()`: `FMAP_ZOOM_WORLD`, `_SECTOR` (square view) or `_DETAIL`.

### 4.2 Buttons used by the sea chart

How the chart opens: on the field, **D-pad Up** opens the sea chart, provided
the stage has no dungeon map and event 0x0908 is set
(`d_menu_window.cpp:961`). While the chart is open (`MENU_STATE_FMAP_MOVE`,
`d_menu_window.cpp:1287`), the window code only polls `isFmapClose()`. All
input goes through `dMenu_Fmap_c::_move`.

| Mode / view | Buttons read |
|---|---|
| Normal: every zoom level (`FmapProc`) | **Y**: open the compare page (`dMenu_Fmap2_c`). Checked before anything else, so it works in world, square **and** detail view |
| Normal: every zoom level (`FmapProcMain`) | **D-pad Left / D-pad Down**: close the chart. **B** closes it only in world zoom |
| World view (`SelectGrid`) | Main stick (`STControl` triggers) moves the cursor. A zooms into the square |
| Square view (`ZoomGridLv1Proc`) | A: detail zoom (if the square is visited). B: back to world. Main stick is **not** read |
| Detail view (`ZoomGridLv2Proc`) | B: back |
| Compare page (`fmap2Move`, `dMenu_Fmap2_c::_move`) | Y back, B / D-Left / D-Down close, A, main stick, L/R (page) |
| Warp mode (`wrapMove`, `wrapSelect`) | A, B, D-pad Down, main stick |
| Wallpaper (`_move` + window) | Left / Down / B / A / X / Y close |
| Fishman | any of A B X Y L R Z Start |

So in **normal mode** (every zoom level) and in **warp mode**, nothing reads
**X, Z, L, R, Start, D-pad Up, D-pad Right or the C-stick**.

**Y is not free.** In vanilla, pressing Y anywhere on the normal sea chart,
including square view, opens the chart-compare page. Pick one of these:

1. **Recommended: use X to toggle a location in square view.** X is unused in
   every normal-mode view and needs no vanilla behaviour change.
2. Keep Y, but hook `FmapProc` (0x801B6610) so that while
   `getCtFmapZoom() != FMAP_ZOOM_WORLD` and the tracker list is shown, Y is
   consumed by the tracker. The compare page then only opens from world view.
   This is a vanilla behaviour change and should be reported to the owner.

**Z is free.** Nothing reads it in normal mode, so Z can open and close the
separate dungeon/other list page.

Selection inside the square-view list: **D-pad Left/Down close the whole
chart**, so they can't be used for the list. Use the **main stick** (unused in
square view) or D-pad Up/Right and the C-stick. Main-stick triggers can reuse
the existing `stick` (`STControl*`) member.

The debug map-select patch (`map_select.asm`) fires while Y+Z+D-Down are held.
It only runs in `dScnPly_Draw` while Link is loaded, and D-Down closes the
chart anyway, so it doesn't conflict.

Raw pad state, if hooks need it outside `CPad_*` macros:
`g_mDoCPd_cpadInfo` is at 0x803A4DF0 (`interface_of_controller_pad[4]`,
stride 0x3C). For pad 0, `mButtonHold` is at 0x803A4E20 and `mButtonTrig` at
**0x803A4E22**. Byte 0 is `left 0x80, right 0x40, down 0x20, up 0x10, z 0x08,
r 0x04, l 0x02, a 0x01`. Byte 1 is `b 0x80, x 0x40, y 0x20, start 0x10`
(`c_API_controller_pad.h`). The rando's map select reads
`mPadButton__10JUTGamePad` (0x803ED848) instead.

### 4.3 Drawing text from the sea chart

`dMenu_Fmap_c::_draw` doesn't draw anything itself. It queues the
`dDlst_FMAP_c fmapDl` object on the 2D opaque list with
`dComIfGd_set2DOpa(&fmapDl)`. Later, while the display lists are drawn,
`dDlst_FMAP_c::draw` runs:

```c
J2DOrthoGraph* grafPort = dComIfGp_getCurrentGrafPort();  // *(0x803CA908)
grafPort->setPort();                                      // setPort__13J2DOrthoGraphFv 0x802CDCB4
scrn->draw(0.0f, 0.0f, grafPort);
```

The cleanest hook is the **tail of `dDlst_FMAP_c::draw` (0x801BB024)**. At
that point the ortho port (640×480 screen space) is already set up and the
chart's own panes are drawn underneath. Add the tracker's text and boxes
there. Alternatively, queue a separate `dDlst_base_c` from `_draw` with
`dComIfGd_set2DOpa`. That needs a vtable in custom code, so the tail hook is
simpler.

Fonts: the chart's `mFont` and `mRFont` come from `mDoExt_getMesgFont()` and
`mDoExt_getRubyFont()` (`d_menu_window.cpp:1490`, through `setFont`), so the
message font is already loaded whenever the chart is open.

Available drawing primitives:

| Symbol | Address | Use |
|---|---|---|
| `mDoExt_getMesgFont__Fv` | 0x800168E0 | returns the `JUTFont*` used by message boxes (`JUTResFont`) |
| `mDoExt_getRubyFont__Fv` | 0x80016A7C | furigana font |
| `__ct__8J2DPrintFP7JUTFontffQ28JUtility6TColor…` | 0x802CE108 | `J2DPrint(font, charSpace, lineSpace, charColor, gradColor, black, white)`; object size 0x5C, has a vtable, so construct it on the stack |
| `locate__8J2DPrintFff` | 0x802CE4BC | |
| `printReturn__8J2DPrintFPCcff18J2DTextBoxHBinding18J2DTextBoxVBindingffUc` | 0x802CE4D8 | `(str, boxW, boxH, hBind, vBind, offX, offY, alpha)`. Draws at the current GX matrix. Supports `\n` and the J2D escape codes (`\x1BCC[rrggbbaa]` colour and so on) |
| `initchar__8J2DPrintFv` | 0x802CF600 | |
| `drawString_size_scale__7JUTFontFffffPCcUlb` | 0x802C1F24 | simpler: `font->drawString_size_scale(x, y, w, h, str, len, true)` after `font->setGX()` (vtable +0x0C) and `setCharColor` (0x802C1E1C) |
| `draw__10J2DTextBoxFfff18J2DTextBoxHBinding` | 0x802D5928 | reference pattern (see below) |
| `J2DFillBox__FffffQ28JUtility6TColor` | 0x802CDF3C | solid rectangles (row highlight, colour swatches) |
| `GXLoadPosMtxImm` / `GXSetCurrentMtx` / `PSMTXIdentity` | 0x80326F38 / 0x80326FD8 / 0x8030D09C | position matrix for `printReturn` |
| `sprintf` / `snprintf` | 0x8032B904 / 0x8032B9E4 | counters such as `"3/5"` |

This is the reference pattern, `J2DTextBox::draw` (`J2DTextBox.cpp:134`):

```c
J2DPrint print(font, charSpace, lineSpace, charColor, gradColor, black, white);
print.setFontSize(sizeX, sizeY);          // inline: writes +0x50/+0x54
makeMatrix(x, y); GXLoadPosMtxImm(mtx, 0); GXSetCurrentMtx(0);
print.printReturn(str, width, 0.0f, HBIND_LEFT, VBIND_TOP, 0.0f, -sizeY, alpha);
MTXIdentity(mtx); GXLoadPosMtxImm(mtx, 0);
```

From C, the J2DPrint path means declaring a 0x5C-byte buffer, calling the
constructor and the methods by their mangled names (added to
`asm/linker.ld`), and running the destructor `__dt__8J2DPrintFv` (0x802CF8AC) afterwards. The `JUTFont::drawString_size_scale` path needs
fewer symbols, but it doesn't handle colour escape codes. Pick per use.

---

## 5. Quick reference: symbols to add to `asm/linker.ld`

These aren't in `linker.ld` yet. Addresses come from the decomp's symbols
file. Check them against `framework.map` in the ISO when adding.

```
isGetMap__16dSv_player_map_cFi = 0x8005b3cc;
isOpenMap__16dSv_player_map_cFi = 0x8005b5d4;
isCompleteMap__16dSv_player_map_cFi = 0x8005b7dc;
isDungeonItem__12dSv_memBit_cFi = 0x8005c844;
dComIfGs_checkGetItemNum__FUc = 0x80053f70;
mStayNo__20dStage_roomControl_c = 0x803f6a78;
g_mDoCPd_cpadInfo = 0x803a4df0;
mDoExt_getMesgFont__Fv = 0x800168e0;
mDoExt_getRubyFont__Fv = 0x80016a7c;
__ct__8J2DPrintFP7JUTFontffQ28JUtility6TColorQ28JUtility6TColorQ28JUtility6TColorQ28JUtility6TColor = 0x802ce108;
locate__8J2DPrintFff = 0x802ce4bc;
printReturn__8J2DPrintFPCcff18J2DTextBoxHBinding18J2DTextBoxVBindingffUc = 0x802ce4d8;
setCharColor__7JUTFontFQ28JUtility6TColor = 0x802c1e1c;
drawString_size_scale__7JUTFontFffffPCcUlb = 0x802c1f24;
J2DFillBox__FffffQ28JUtility6TColor = 0x802cdf3c;
setPort__13J2DOrthoGraphFv = 0x802cdcb4;
GXLoadPosMtxImm = 0x80326f38;
GXSetCurrentMtx = 0x80326fd8;
PSMTXIdentity = 0x8030d09c;
snprintf = 0x8032b9e4;
FmapProc__12dMenu_Fmap_cFv = 0x801b6610;
ZoomGridLv1Proc__12dMenu_Fmap_cFv = 0x801b5d6c;
draw__12dDlst_FMAP_cFv = 0x801bb024;
```

`execItemGet__FUc`, `init__10dSv_info_cFv`, `init__10dSv_save_cFv`,
`item_func_small_key__Fv`, `isEventBit__11dSv_event_cFUs`,
`isTbox__12dSv_memBit_cFi`, `isSwitch__10dSv_info_cFii`,
`dComIfGp_setNextStage__FPCcsScScfUliSc` and `mPadButton__10JUTGamePad` are
already defined in `asm/linker.ld`.
