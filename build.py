#!/usr/bin/env python3

import os
import platform
import shutil

from version import VERSION_WITHOUT_COMMIT

# Must match app_name in wwrando.spec.
base_name = "wwrando-tracking"

import struct
if (struct.calcsize("P") * 8) == 64:
  bitness_suffix = "_x64"
else:
  bitness_suffix = "_x86"

exe_ext = ""
if platform.system() == "Windows":
  exe_ext = ".exe"
  platform_name = "win"
if platform.system() == "Darwin":
  exe_ext = ".app"
  platform_name = "mac"
if platform.system() == "Linux":
  platform_name = "linux"

exe_path = os.path.join(".", "dist", base_name + exe_ext)
if not (os.path.isfile(exe_path) or os.path.isdir(exe_path)):
  raise Exception("Executable not found: %s" % exe_path)

if platform.system() == "Linux":
  # e.g. wwrando-2.5.2-tracking-linux-x64, which is also the name of the folder the tarball unpacks to.
  release_archive_name = "wwrando-" + VERSION_WITHOUT_COMMIT + "-" + platform_name + bitness_suffix.replace("_", "-")
else:
  release_archive_name = "release_archive_" + VERSION_WITHOUT_COMMIT + bitness_suffix
release_archive_path = os.path.join(".", "dist", release_archive_name)
print("Writing build to path: %s" % (release_archive_path))

if os.path.exists(release_archive_path) and os.path.isdir(release_archive_path):
  shutil.rmtree(release_archive_path)

os.mkdir(release_archive_path)
shutil.copyfile("README.md", os.path.join(release_archive_path, "README.txt"))
shutil.copyfile("LICENSE.txt", os.path.join(release_archive_path, "LICENSE.txt"))

shutil.move(exe_path, os.path.join(release_archive_path, base_name + exe_ext))

if platform.system() == "Darwin":
  shutil.copyfile(os.path.join(".", "models", "About Custom Models.txt"), os.path.join(release_archive_path, "About Custom Models.txt"))
  shutil.make_archive(release_archive_path, "zip", release_archive_path)
else:
  os.mkdir(os.path.join(release_archive_path, "models"))
  shutil.copyfile(os.path.join(".", "models", "About Custom Models.txt"), os.path.join(release_archive_path, "models", "About Custom Models.txt"))

if platform.system() == "Linux":
  # A tarball keeps the executable bit.
  tarball_path = shutil.make_archive(release_archive_path, "gztar", root_dir=os.path.join(".", "dist"), base_dir=release_archive_name)
  print("Wrote release archive: %s" % tarball_path)
