# Wind Waker Randomizer: Tracking Edition (wwrando-tracking)

A randomizer for The Legend of Zelda: The Wind Waker with an **in-game tracker** built into the sea chart.
It is a fork of tanjo3's [Archipelago Wind Waker Randomizer](https://github.com/tanjo3/wwrando/tree/archipelago)
(itself a fork of LagoLunatic's [Wind Waker Randomizer](https://github.com/LagoLunatic/wwrando)) and patches a vanilla
ISO in one of two modes:

- **Offline mode**: no Archipelago needed. The randomizer generates a solo seed locally, with the options the
  Archipelago Wind Waker world supports (progression locations, the six dungeon item placement modes, swords optional,
  Tuner logic, entrance randomizer, required bosses with always/never required dungeons, starting items, ...). Items
  are placed directly in the game. You get a spoiler log and a permalink to share the seed.
- **Archipelago mode**: give it the `.aptww` file from your Archipelago multiworld and it behaves exactly like tanjo3's
  randomizer. The `.aptww` file decides the seed and gameplay options.

In both modes the patched game gets the **in-game tracker** (on by default): the sea chart shows how many locations
are left on every island and in every dungeon and which of them are in logic, lets you mark locations by hand, and
shows where entrances lead and where treasure charts point once you have found out in the game. It never shows which
item is where.

This is a small project for friends, played on Dolphin. Release builds are provided for Linux and Windows.

## Requirements

The randomizer only supports the North American GameCube version of Wind Waker (MD5:
`d8e4d45af2032a081a0f446384e9261b`). The European and Japanese versions won't work, and neither will Wind Waker HD.
You need your own copy of the ISO; it isn't included and never will be.

Every offline seed is guaranteed to be completable without glitches or tricks (unless you enable trick logic on the
Advanced Options tab). Because Wind Waker is a large game, the *progression location* options limit where progress
items can be: location types you don't select only get unimportant items (rupees, heart pieces, ...), so you can skip
them. The tracker only tracks the locations that can have progress items.

The output ISO is meant for Dolphin. It hasn't been tested on a real GameCube.

## Download

Builds are on the [Releases page](https://github.com/thesword1/wwrando-tracking/releases).

### Windows

Download `wwrando-<version>-windows-x64.zip`, extract it (don't run it from inside the zip) and double-click
`wwrando-tracking.exe`.

It takes a few seconds to start (it unpacks itself first). It keeps its settings (`settings.txt`) and custom player
models (`models/`) in its folder, so extract it somewhere you can write to (not `Program Files`).

The executable isn't signed, so Windows SmartScreen may say "Windows protected your PC": click *More info*, then *Run
anyway*. Some antivirus programs flag PyInstaller executables like this one as a false positive. If yours deletes or
blocks it, add an exception for the folder, or run the randomizer from source instead.

### Linux

Unpack the tarball and start `wwrando-tracking` from its folder:

```sh
tar xzf wwrando-*-linux-x64.tar.gz
cd wwrando-*-linux-x64
./wwrando-tracking
```

It takes a few seconds to start (it unpacks itself first). It keeps its settings (`settings.txt`) and custom player
models (`models/`) in the folder you start it from. If it fails to start with a Qt "xcb" error, install your
distribution's `xcb-util-cursor` package (`libxcb-cursor0` on Debian/Ubuntu).

## Running from source (Linux)

You need git, a C compiler (for gclib's native speedups) and Python 3.12. Python 3.13+ (for example the system Python
on current Fedora/Nobara) is too new for some dependencies, so the easiest way is a Python 3.12 managed by
[uv](https://docs.astral.sh/uv/):

```sh
git clone --recurse-submodules https://github.com/thesword1/wwrando-tracking.git
cd wwrando-tracking
git submodule update --init   # if you cloned without --recurse-submodules

uv venv --python 3.12 --managed-python .venv
. .venv/bin/activate
CFLAGS="-std=gnu17 -fgnu89-inline" uv pip install -r requirements.txt

python wwrando.py
```

The `CFLAGS` are needed with GCC 16 (the default compiler on Fedora 44 / Nobara); without them the gclib speedups fail
to build. They don't hurt with older compilers. Use `requirements_full.txt` instead if you want to run the tests or
build a release (it adds pytest and PyInstaller). Developer documentation is in [`docs/dev/`](docs/dev/README.md).

## Using the randomizer

### GUI

1. **Vanilla Wind Waker ISO**: select your North American ISO.
2. **Randomized Output Folder**: where the patched ISO and logs are written.
3. **APTWW File**: decides the mode. The line under the paths says which mode you're in.
   - Leave it **empty** for **offline mode**. Choose your options on the *Randomizer Settings* tab (progression
     locations, dungeon items, entrance randomizer, other randomizers, gameplay tweaks), the *Starting Items* tab and
     the *Advanced Options* tab (required bosses, difficulty and trick logic, skipping the spoiler log). Enter a seed
     name or press *New seed*.
   - Select an **`.aptww` file** for **Archipelago mode**. The gameplay options are greyed out because they come from
     the file. Only the local settings stay editable: convenience tweaks, cosmetics (*Player Customization* tab), the
     In-Game Tracker option and Enable Tuner Logic (see [below](#archipelago-mode-tuner-logic)).
4. **In-Game Tracker** (Randomizer Settings tab, on by default): adds the tracker to the patched game. Turning it off
   produces the same ISO as a build without the tracker. It doesn't change item placement and isn't part of permalinks.
5. Press **Randomize**.

Offline mode writes `WW Random <seed>.iso`, a spoiler log and a non-spoiler log (no spoiler log if you disabled it).
The **permalink** at the bottom of the window contains the seed and every gameplay option: send it to a friend, who
pastes it into their permalink field to get the same seed. Permalinks only work with the same randomizer version.

Archipelago mode writes `TWW AP_<seed>_P<slot> (<name>).iso`. To play it you also need the Archipelago Wind Waker
client and Dolphin, see the
[Archipelago setup guide](https://github.com/tanjo3/tww_apworld/blob/master/docs/setup_en.md).

### Command line

Without `--aptww`, the command line uses the options saved by the GUI (`settings.txt`, defaults if there is none) and
generates an offline seed. `--clean-iso` and `--output-folder` override the saved paths.

```sh
# Offline seed with the saved options and a random seed name
python wwrando.py --noui --autoseed --clean-iso /path/to/vanilla.iso --output-folder out/

# Offline seed from a permalink (seed and options)
python wwrando.py --noui --permalink <PERMALINK> --clean-iso /path/to/vanilla.iso --output-folder out/

# Archipelago seed (--aptww implies --noui)
python wwrando.py --aptww MySeed.aptww --clean-iso /path/to/vanilla.iso --output-folder out/

# Without the in-game tracker (--tracker forces it on); otherwise the saved setting is used
python wwrando.py --noui --autoseed --no-tracker --clean-iso /path/to/vanilla.iso --output-folder out/

# Only the logs, no ISO needed
python wwrando.py --noui --seed MySeed --dry --output-folder out/
```

With a release build, replace `python wwrando.py` with `./wwrando-tracking` (Linux) or `.\wwrando-tracking.exe`
(Windows, from a Command Prompt or PowerShell in its folder). `--help` lists every option.

## In-game tracker

Open the sea chart (**D-pad Up**). The tracker draws on top of it.

### What it tracks

- Only the seed's **progress locations**: those of the progression location types you selected (in Archipelago mode,
  the ones in your `.aptww` file). Locations that can't have progress items aren't shown. With Required Bosses Mode,
  the dungeons of bosses that aren't required are hidden too.
- A location is **checked** automatically when the game sets its flag (chests, item pickups, NPC rewards, sunken
  treasure, Big Octos, ...), the same way the Archipelago client detects checks. You can also **mark** a location that
  hasn't been detected yet by hand (and unmark your own marks). Detected checks can't be unmarked.
- Marks, visited entrances and small key counts are stored in your save file, so they're kept when you **save** the
  game. Starting a new game, or loading a save from another seed, resets them.

### What the colours mean

On the world view, every sea square with tracked locations has a small counter in its top left corner: the number of
unchecked locations, shown as `in logic/unchecked` (for example `2/5`). The salvage panel shows the total
`Checked n/total`.

| Colour | Counter (square or group) | Location row |
|---|---|---|
| Blue | some unchecked location here is in logic | in logic: you can get it with what you have |
| Red | unchecked locations left, but none in logic | not in logic yet |
| Grey | everything checked | checked (struck through) |
| Dark brown | logic not available (shouldn't happen) | same |

"In logic" follows the randomizer's logic for your settings and your current items, small keys found, entrances
visited and locations checked, like the [WWRando-APTracker](https://thesword1.github.io/WWRando-APTracker/) website:

- Anything behind a randomized entrance is out of logic until you've been through that entrance.
- Mail letters and Knight's Crest farming count once the location they depend on is checked or in logic.
- Required bosses count as defeated once their heart container is checked or in logic.
- Items count when you get them, including items sent by the Archipelago server.

### Views and controls

- **World view**: the counters described above.
- **Square view** (press **A** on a square): a panel lists the square's locations with checkboxes, then its randomized
  entrances (`Outset Island Cave -> ?` until you've been through it, then where it leads) and, if the square has a
  sunken treasure, the chart that leads there (`Chart: not owned` until you own it, then its name).
- **Other locations page** (press **Z**): everything that isn't on a sea square: dungeons, Hyrule, Ganon's Tower,
  Mailbox, The Great Sea and secret caves behind randomized entrances, each with its counter. **A** opens a group's
  location list. A group behind a randomized entrance shows `Entrance: Unknown entrance` until you've been through it.
  Dungeon lists also show where their miniboss and boss doors lead once you've been through them.

| Button | World view | Square view | Other locations page | Group list |
|---|---|---|---|---|
| Z | open other locations | open other locations | close | close |
| Main stick | move cursor (vanilla) | select location | select group | select location |
| X | - | mark / unmark | - | mark / unmark |
| A | zoom in (vanilla) | detail zoom (vanilla) | open group | - |
| B | close chart (vanilla) | zoom out (vanilla) | close page | back to the page |

Holding the stick scrolls; a fresh push past the end of a list wraps around. If you press X on a location the game has
already detected as checked, the row flashes red and nothing changes. While the other locations page is open, the
chart's own buttons (D-pad Left/Down, Y) do nothing until you close it with Z or B.

### No spoilers

- The tracker never shows which item is at a location, only whether it's checked and whether it's in logic.
- An entrance's destination is shown only after you've gone through it.
- A treasure chart's destination is shown only once you own that chart.

### Archipelago mode: Tuner logic

Archipelago doesn't write the "Enable Tuner Logic" option into `.aptww` files. In Archipelago mode it is a local
setting (Advanced Options tab, default off) that only changes the tracker's logic: set it to match your world's
`enable_tuner_logic` option so Tingle Chests are coloured correctly.

## Known limitations

- **Linux and Windows only.** Release builds are for Linux x86-64 with glibc 2.35 or newer (Ubuntu 22.04 and later)
  and 64-bit Windows 10/11. macOS isn't supported; it can try running from source.
- **No hints** in offline mode, and the tracker doesn't show hints in either mode. (Archipelago seeds keep the
  fishmen/Hoho/KoRL hints their `.aptww` file asks for, as in tanjo3's randomizer.) Archipelago server hints (`!hint`)
  can't be shown on the in-game tracker: the game has no network access, and the standard Archipelago Wind Waker
  client never writes hints into the game's memory. That would need a modified client that every player installs, so
  it isn't planned.
- No Triforce shard counter and no "items needed" estimate (the website tracker has one).
- The tracker only tracks progress locations, so it can't help with optional locations.
- Tracker marks are only kept if you save the game. Loading a save from a different seed resets the tracker data.
- Only tested in Dolphin.

## Bugs and questions

Please report problems on this repository's [issue tracker](https://github.com/thesword1/wwrando-tracking/issues). For
an offline seed, include the permalink; for an Archipelago seed, the `.aptww` file if you can.

General questions about playing the randomizer are mostly answered by upstream's
[FAQ](https://lagolunatic.github.io/wwrando/faq/), but please don't report bugs in this fork to the upstream projects.

## Credits

- **LagoLunatic** created the Wind Waker Randomizer, with help from Aelire, CryZe, EthanArmbrust, Fig, Gamma /
  SageOfMirrors, Hypatia, JarheadHME, LordNed, MelonSpeedruns, nbouteme, tanjo3, TrogWW and wooferzfg (see
  [upstream](https://github.com/LagoLunatic/wwrando) for what each contributed).
- **tanjo3** made the [Archipelago version](https://github.com/tanjo3/wwrando/tree/archipelago) this fork is based on,
  and the [Archipelago Wind Waker world](https://github.com/ArchipelagoMW/Archipelago/tree/main/worlds/tww) (with the
  Archipelago contributors), whose options, location data and check detection the offline mode and tracker follow
  (ported code is MIT licensed and attributed in the source).
- The tracker's behaviour follows the [WWRando-APTracker](https://github.com/thesword1/WWRando-APTracker) website,
  which is based on wooferzfg's [TWW Randomizer Tracker](https://github.com/wooferzfg/tww-rando-tracker).
- The [zeldaret/tww](https://github.com/zeldaret/tww) decompilation was the reference for the game's memory layout and
  sea chart code.
- Tracking edition by thesword1.
