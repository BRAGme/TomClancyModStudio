"""Produce dist/ModStudio.exe.

    python build_exe.py

One file, no installer, no Python needed on the target machine. The imports are
listed explicitly because the entry point defers them until it knows whether it
is opening a window or running a command, which PyInstaller's scan cannot see.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "ModStudio"

HIDDEN = [
    "cli", "gui", "gui.app", "gui.theme", "gui.widgets", "gui.controls",
    "gui.presets", "gui.skins", "gui.presence", "gui.discorddialog",
    "tcxbox", "tcxbox.model", "tcxbox.engine", "tcxbox.detect",
    "tcxbox.gamedir", "tcxbox.globfile", "tcxbox.umd", "tcxbox.xbe",
    "tcxbox.xiso",
    "tcxbox.dataedit", "tcxbox.transforms", "tcxbox.rseguns",
    "tcxbox.art", "tcxbox.rsb", "tcxbox.xpr",
    "tcxbox.games", "tcxbox.games.ghost_recon", "tcxbox.games.ghost_recon2",
    "tcxbox.games.r6_3", "tcxbox.games.graw", "tcxbox.games.r6engine",
    "tcxbox.games.critical_hour",
    "tcxbox.games.rstuning", "tcxbox.games.rseweapons",
    # Discord presence speaks the IPC protocol itself, so this pulls in no
    # third-party package -- but the modules still have to be named here.
    "webbrowser",
    "PIL.Image", "PIL.ImageTk", "PIL.ImageDraw", "PIL.ImageFont",
    "PIL.ImageEnhance", "PIL.ImageFilter",
]

EXCLUDE = ["numpy", "scipy", "matplotlib", "pytest", "PySide6", "PyQt5",
           "PIL.ImageQt", "setuptools", "pip"]


def app_version():
    """The version the window shows, read rather than repeated.

    Parsed out of the source instead of imported: importing the window module
    pulls in tkinter and the whole tool just to read one string, and there is
    no reason for a build script to need a display.
    """
    src = open(os.path.join(ROOT, "gui", "app.py"), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise SystemExit("cannot find VERSION in gui/app.py")
    return m.group(1)


def write_version_file(path, version):
    """A Windows version resource, so the exe's Properties tab is not blank.

    Windows wants four numbers; the app names two, so the rest are zeros.
    """
    parts = [int(n) for n in version.split(".") if n.isdigit()]
    quad = tuple((parts + [0, 0, 0, 0])[:4])
    text = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=%(q)s, prodvers=%(q)s, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'BRAGme'),
        StringStruct('FileDescription', %(name)r),
        StringStruct('FileVersion', %(ver)r),
        StringStruct('InternalName', %(exe)r),
        StringStruct('OriginalFilename', %(exe)r + '.exe'),
        StringStruct('ProductName', %(name)r),
        StringStruct('ProductVersion', %(ver)r)])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""" % {"q": quad, "ver": version, "exe": NAME,
       "name": "Tom Clancy Xbox Mod Studio"}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main():
    version = app_version()
    print("building version %s" % version)
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
    build_dir = os.path.join(ROOT, "build")
    os.makedirs(build_dir, exist_ok=True)
    args += ["--version-file",
             write_version_file(os.path.join(build_dir, "version.txt"), version)]
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
    print("\n%s  v%s  (%.1f MB)"
          % (exe, version, os.path.getsize(exe) / 1048576.0))
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
