"""Produce dist/XboxModStudio.exe.

    python build_exe.py              -- the normal build
    python build_exe.py --preview    -- a build that opens without a game, for
                                        someone who wants to read the options
                                        before owning the discs

One file, no installer, no Python needed on the target machine. The imports are
listed explicitly because the entry point defers them until it knows whether it
is opening a window or running a command, which PyInstaller's scan cannot see.

**The binary is NOT called ModStudio.exe**, which is what the PS2 Mod Studio
builds. Two tools with the same file name and a similar icon in the same
Downloads folder is exactly the confusion the teal icon is there to avoid, and
a name is the half of that a shell shows in a list view. It also sidesteps
Windows' icon cache, which is keyed on the path: rebuilding a different icon
into the same ModStudio.exe leaves Explorer showing the old one until the cache
is cleared, and the first thing that looks like is "the icon did not change".
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "XboxModStudio"

HIDDEN = [
    "cli", "gui", "gui.app", "gui.theme", "gui.widgets", "gui.controls",
    "gui.presets", "gui.dialog", "gui.skins", "gui.presence", "gui.discorddialog",
    "tcxbox", "tcxbox.model", "tcxbox.engine", "tcxbox.detect",
    "tcxbox.gamedir", "tcxbox.globfile", "tcxbox.umd", "tcxbox.xbe",
    "tcxbox.xiso",
    "tcxbox.dataedit", "tcxbox.transforms", "tcxbox.rseguns",
    # Imported inside the op functions rather than at module scope, so a
    # frozen build will not find them by following imports.
    "tcxbox.lin", "tcxbox.upackage", "tcxbox.hunt", "tcxbox.rsesidearm",
    "gui.tooltip",
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
    # A preview build opens straight into the option pages with no game
    # loaded, for someone who wants to read what the tool does before -- or
    # without -- owning the discs. It is the same binary with a marker file
    # baked beside the assets; `gui.app.baked_preview` looks for it.
    preview = "--preview" in sys.argv
    name = NAME + (" (preview)" if preview else "")
    marker = os.path.join(ROOT, "assets", "preview.mode")
    if preview:
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("This build opens in preview mode: no game required.\n")
    elif os.path.exists(marker):
        # A normal build must never inherit the marker from a preview build
        # that ran before it, which is the obvious way to ship the wrong exe.
        os.remove(marker)
    print("building version %s%s"
          % (version, "  [preview: opens without a game]" if preview else ""))
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed", "--name", name,
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

    script = os.path.join(ROOT, "%s.py" % NAME)
    if not os.path.exists(script):
        raise SystemExit("no %s.py to build -- the entry script is named after "
                         "NAME, so the two have to move together" % NAME)

    print(" ".join(args))
    rc = subprocess.call(args, cwd=ROOT)
    if rc:
        return rc
    # `name`, not `NAME`: a preview build is written as "... (preview).exe",
    # and checking for the wrong one would report a clean build as a failure.
    exe = os.path.join(ROOT, "dist", name + ".exe")
    # PyInstaller has been seen to exit 0 without producing anything; a build
    # script that says nothing in that case is worse than no build script.
    if not os.path.exists(exe):
        raise SystemExit("PyInstaller exited cleanly but %s is not there"
                         % os.path.basename(exe))
    print("\n%s  v%s  (%.1f MB)"
          % (exe, version, os.path.getsize(exe) / 1048576.0))
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
