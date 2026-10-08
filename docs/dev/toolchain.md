# Developer toolchain

Developer notes, not part of the public site (`docs/dev/` is excluded in `mkdocs.yml`).

## Python environment

The randomizer targets Python 3.12. Python 3.14 (the system Python on current Fedora/Nobara) is too new for some of the pinned dependencies, so use a uv-managed 3.12 interpreter:

```sh
git submodule update --init
uv venv --python 3.12 --managed-python .venv
. .venv/bin/activate
CFLAGS="-std=gnu17 -fgnu89-inline" uv pip install -r requirements_full.txt
```

`CFLAGS` is needed when the host compiler is GCC 16 (the default on Fedora 44 / Nobara); without it, building gclib's optional native speedups fails.

## devkitPPC (custom ASM and C patches)

The game's custom code lives in `asm/patches/*.asm` (and C files pulled in with `.include "file.c"`). `asm/assemble.py` assembles it with devkitPPC and writes the precompiled results, which are committed:

- `asm/patch_diffs/*_diff.txt`
- `asm/custom_symbols.txt`

The randomizer itself only reads those committed files, so devkitPPC is only needed when you change the ASM/C.

### Running the assembler (recommended: container)

Requires `podman` (or `docker`); no root and no devkitPro install needed.

```sh
tools/devkitppc/assemble.sh
git diff --stat asm/   # review the regenerated diffs, then commit them
```

The script builds a small local image (`localhost/wwrando-devkitppc`) from `tools/devkitppc/Containerfile` on first use (later runs reuse the cached layers), mounts the repository at `/src`, and runs `python3 asm/assemble.py` inside it. Regenerated files keep your uid (`--userns=keep-id` on podman, `--user` on docker). Set `WWRANDO_DEVKITPPC_IMAGE` to use a differently named local image tag.

### Pinned toolchain version

The Containerfile pins the base image by digest:

| | |
|---|---|
| Image | `docker.io/devkitpro/devkitppc@sha256:4c919aa26151dd43d88ca28c922d1fe2409579a8ba60ef56517baf1abdfb1a48` (`latest` as of 2026-05-03) |
| binutils | 2.46.0.20260210 |
| GCC | 16.1.0 (devkitPPC) |
| Python / ruamel.yaml | 3.11 (Debian 12) / 0.19.x |

With this image, running the assembler on unmodified `master` regenerates every file in `asm/patch_diffs/` and `asm/custom_symbols.txt` byte-identically. If you bump the digest, rerun the assembler on a clean checkout and confirm `git status` stays clean before committing; a different binutils or GCC may encode some instructions differently or change the code GCC produces for C files.

CI (`.github/workflows/asm.yml`) runs the same script on every push/PR that touches `asm/`, `gclib`, or `tools/devkitppc/`, and fails if the regenerated files differ from the committed ones. So whenever you change a patch, commit the regenerated diffs too.

### C files

`.include "foo.c"` in a patch compiles `asm/foo.c` with `powerpc-eabi-gcc -mcpu=750 -Og -fno-inline -fshort-enums -Wall -Werror` to assembly and splices it in at that point. Example:

```asm
.open "sys/main.dol"
.org @NextFreeSpace
.include "my_feature.c"
.close
```

Non-static C functions become global custom symbols (listed in `custom_symbols.txt`) that other patches and `tweaks.py` can reference.

### Without a container

On Windows, install devkitPro to `C:\devkitPro` (the path `assemble.py` expects). On Linux/macOS, install devkitPPC with devkitPro's pacman and set `DEVKITPPC` (for example `/opt/devkitpro/devkitPPC`), then run `python asm/assemble.py` from the venv. A native install isn't pinned, so it may not reproduce the committed diffs exactly; check `git diff` and prefer the container if it doesn't.
