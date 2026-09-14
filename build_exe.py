"""Produce dist/ModStudio.exe.

    python build_exe.py

One file, no installer, no Python needed on the target machine. The imports are
listed explicitly because the entry point defers them until it knows whether it
is opening a window or running a command, which PyInstaller's scan cannot see.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "ModStudio"

HIDDEN = [
    "cli", "gui", "gui.app", "gui.theme", "gui.widgets", "gui.controls",
    "gui.presets", "tcps2", "tcps2.iso", "tcps2.soz", "tcps2.vokes",
    "tcps2.art", "tcps2.model", "tcps2.engine", "tcps2.detect",
    "tcps2.games", "tcps2.games.r6_3", "tcps2.games.ghost_recon",
    "tcps2.games.jungle_storm", "tcps2.games.ghost_recon2",
    "tcps2.games.graw", "tcps2.games.soaf",
    "tcps2.lin", "tcps2.rselzo", "tcps2.transforms", "tcps2.dataedit",
    "tcps2.overlay", "tcps2.rsb", "gui.skins",
    "PIL.Image", "PIL.ImageTk", "PIL.ImageDraw", "PIL.ImageFont",
    "PIL.ImageEnhance", "PIL.ImageFilter",
]

EXCLUDE = ["numpy", "scipy", "matplotlib", "pytest", "PySide6", "PyQt5",
           "PIL.ImageQt", "setuptools", "pip"]


def main():
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed", "--name", NAME,
            "--distpath", os.path.join(ROOT, "dist"),
            "--workpath", os.path.join(ROOT, "build"),
            "--specpath", os.path.join(ROOT, "build")]
    icon = os.path.join(ROOT, "assets", "icon.ico")
    if os.path.exists(icon):
        args += ["--icon", icon,
                 "--add-data", "%s%s%s" % (os.path.join(ROOT, "assets"),
                                           os.pathsep, "assets")]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    for e in EXCLUDE:
        args += ["--exclude-module", e]
    args.append(os.path.join(ROOT, "%s.py" % NAME))

    print(" ".join(args))
    rc = subprocess.call(args, cwd=ROOT)
    if rc:
        return rc
    exe = os.path.join(ROOT, "dist", NAME + ".exe")
    print("\n%s  (%.1f MB)" % (exe, os.path.getsize(exe) / 1048576.0))
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
