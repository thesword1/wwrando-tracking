# Dolphin automation harness

`tools/dolphin/` lets scripts (and agents) boot an ISO in Dolphin, drive a GameCube
controller, read and write emulated RAM, take screenshots and use savestates. It is meant
for in-game verification of patches and the tracker; it is not run in CI.

Tested with the flatpak `org.DolphinEmu.dolphin-emu` 2606 on Fedora/Nobara 44 (KDE Wayland,
Dolphin runs through XWayland), Python 3.12.

## Quick start

```sh
python tools/dolphin/smoke_test.py "/path/to/The Wind Waker (USA).iso"
# or, via pytest (deselected unless -m dolphin is given):
WW_ISO_PATH=/path/to/iso pytest test/test_dolphin_harness.py -m dolphin
```

The smoke test boots the ISO, checks for `GZLE01` at `0x80000000`, waits for the title
stage (`sea_T`), presses START until the file select stage (`Name`) is loaded, takes a
screenshot, saves and reloads savestate slot 1, and quits Dolphin. It takes about 15 s.

```python
from tools.dolphin.harness import Dolphin

with Dolphin(iso_path, user_dir="/some/scratch/dir") as dolphin:
  dolphin.wait_for_game_id("GZLE01")
  dolphin.pad.press("START")             # press + release, default 0.1 s hold
  dolphin.pad.tilt(0, 1, duration=0.5)   # main stick up for 0.5 s
  stage = dolphin.memory.read_cstring(0x803C9D3C, 8)
  dolphin.memory.write_u32(0x80001800, 0x12345678)
  png = dolphin.screenshot()             # Path to a PNG
  dolphin.save_state(1); dolphin.load_state(1)
```

`Dolphin(...)` options: `user_dir` (default: a new temp dir), `video_backend` (`Vulkan`,
`OGL`, ...), `unlimited_speed`, `audio` (off by default), `batch` (default on: no main
window, only the render window), `initial_save_state` (boot straight into a `.sav` file
via `-s`), `extra_config` (`{"Dolphin.Core.CPUThread": "False"}` → `-C` arguments).

## How it works

### Launching (`harness.py`, `config.py`)

- `config.write_user_dir()` populates an **isolated user directory** (`-u <dir>`) with
  `Dolphin.ini`, `GCPadNew.ini`, `Hotkeys.ini` and `GFX.ini`, and creates the input FIFOs.
  The user's own Dolphin config in `~/.var/app/org.DolphinEmu.dolphin-emu` is never read
  or written.
- Notable settings: skip IPL, no confirm-on-stop, no panic handlers, no OSD messages,
  **background input on** (otherwise pad input is ignored while the render window is
  unfocused), no audio, analytics off, fixed 640x528 render window.
- Hotkeys need a separate setting: `Dolphin.General.HotkeysRequireFocus=False`, passed with `-C`
  on every launch (it has no effect when written to `Dolphin.ini`). Without it, screenshots and
  savestates silently fail whenever the window manager doesn't focus the render window.
- Dolphin is started as
  `flatpak run --filesystem=<user dir> --filesystem=<iso dir>:ro org.DolphinEmu.dolphin-emu -u <user dir> -e <iso> -b`.
  The flatpak can read the host filesystem (`host:ro`) but has a private `/tmp`, so the
  user directory has to be exposed explicitly (needed because scratch dirs live in `/tmp`).
- The host PID of the sandboxed `dolphin-emu` process is found by scanning `/proc` for a
  process named `dolphin-emu` whose command line contains our user directory. This means
  several harness instances, or a harness next to the user's own Dolphin, don't interfere.
- `stop()` sends SIGTERM to that PID, which Dolphin handles as a clean stop
  ("A signal was received..."), and kills it after a timeout.
- Dolphin's output goes to `<user dir>/harness-dolphin.log`.

### Input (`pipe_input.py`)

Dolphin's **Pipe** input backend works under flatpak: every FIFO in `<user dir>/Pipes/`
present at startup becomes an input device `Pipe/0/<name>`. The harness creates:

| FIFO | Use |
|---|---|
| `pad1` | GameCube controller in port 1 (all buttons, D-pad, both sticks, analog triggers) |
| `hk_misc` | Hotkeys: A = screenshot, B = toggle pause, X = frame advance, Y = toggle speed limit |
| `hk_save` | Save state slots 1-10 (A, B, X, Y, Z, START, L, R, D_UP, D_DOWN) |
| `hk_load` | Load state slots 1-10 (same buttons) |

Hotkeys use device-qualified expressions (`` `Pipe/0/hk_save:Button A` ``) so several
pipes can feed the single hotkey controller.

The pipe protocol is line based: `PRESS A`, `RELEASE A`, `SET MAIN <x> <y>` / `SET C <x> <y>`
(0..1, 0.5 = neutral), `SET L <0..1>`. `PipeController` wraps it: `hold`, `release`,
`press(*buttons, duration, after)`, `press_sequence`, `set_main_stick(x, y)` /
`set_c_stick` / `tilt` (x, y in -1..1, **positive y = up**), `set_trigger`, `reset`.
Button names: `A B X Y Z START L R D_UP D_DOWN D_LEFT D_RIGHT` (`UP`/`DOWN`/`LEFT`/`RIGHT`
are accepted as D-pad aliases).

Verified through the sandbox by reading the game's PADStatus (`0x803ED818`): every button
sets the expected bit, main stick up gives stickY = +72, triggers set their analog values;
stick and B were also confirmed to navigate the memory card dialog on screenshots.

Input is polled about once per frame, so presses must last at least a couple of frames
(default 0.1 s). Timings are wall-clock; with `unlimited_speed=True` the game runs faster
than real time, so prefer polling RAM (`dolphin.wait_for(...)`) over sleeping.

### RAM access (`memory.py`)

Dolphin keeps emulated memory in a shared memory object `/dev/shm/dolphin-emu.<pid>`
(inside the flatpak the PID is the sandbox PID, e.g. `dolphin-emu.13`). `DolphinMemory`
finds the first mapping of that object at file offset 0 with size ≥ 24 MiB in
`/proc/<pid>/maps` (MEM1) and reads/writes it through `/proc/<pid>/mem`.

- Works under flatpak: the sandboxed process belongs to the same user, and on this
  machine `/proc/sys/kernel/yama/ptrace_scope` is `0`. With `ptrace_scope = 1` it should
  still work because Dolphin is a descendant of the harness process (not tested). With
  `2`/`3`, RAM access is unavailable.
- Addresses are GameCube virtual addresses: `0x80000000-0x817FFFFF` (cached) and
  `0xC0000000-0xC17FFFFF` (uncached). MEM2/ARAM are not exposed.
- Helpers: `read_bytes/write_bytes`, `read_/write_` `u8 u16 u32 s8 s16 s32 f32`
  (big-endian), `read_cstring`.
- Writes go straight into emulated RAM; the game may overwrite them on the next frame.
- `wait_for_game_id()` retries until the mapping exists and the game ID is in RAM.

`dolphin-memory-engine` (PyPI `dolphin-memory-engine` 1.3.1) also works against the flatpak
build (`hook()` succeeds and reads `GZLE01`), but it attaches to the *first* process named
`dolphin-emu`, so it could hook the user's own Dolphin instead of the harness instance.
That's why the harness uses its own PID-targeted reader, which needs no native
dependency.

### Screenshots

`screenshot()` presses the screenshot hotkey and waits for a new PNG in
`<user dir>/ScreenShots/<game id>/`. Screenshots are the emulated framebuffer at internal
resolution (640x528 at 1x, no OSD or window decorations) and don't depend on the window
being visible or focused. Dolphin names them per second, so the helper waits a second
between consecutive screenshots.

### Savestates

`save_state(slot)` / `load_state(slot)` use the hotkeys for slots 1-10; files are
`<user dir>/StateSaves/<game id>.sNN`. `save_state` waits until the file is written.
`load_state` can't observe completion directly and just waits `settle` seconds. To start
from a known state, pass `initial_save_state=<path>` (Dolphin's `-s`). Savestates are tied
to the Dolphin version.

## Notes and limitations

- Batch mode still opens a render window (there is no headless renderer in the Qt build).
  `dolphin-emu-nogui` exists in the flatpak but wasn't tried; the hotkey-based screenshot
  and savestate helpers rely on the Qt build.
- The memory card in a fresh user dir is empty, so the game asks to create a save file. Use
  a persistent `user_dir` or a savestate to skip that.
- Never commit ISOs, savestates or screenshots of copyrighted content into the repository.
