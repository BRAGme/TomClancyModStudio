"""Produce dist/Tom Clancys PS2 ModStudio.exe.

    python build_exe.py              -- the public build
    python build_exe.py --with-art   -- a private build with the game's icons
    python build_exe.py --preview    -- a no-disc build for someone without
                                        the games, to look round the options

**No-art is the default on purpose.** The loadout icons are Ubisoft artwork, so
a build that carries them must not be published. Making the safe build the one
you get by typing nothing means the art can only ever ship by asking for it.
The art itself lives in `private-art/`, which is git-ignored, so it is not in
the repository either.

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
#: what the built executable is called. Separate from the entry script,
#: which keeps its own name -- renaming the output must not go looking
#: for a source file that does not exist.
NAME = "Tom Clancys PS2 ModStudio"

#: the script PyInstaller is pointed at
ENTRY = "ModStudio.py"

#: Where a private build picks the game's loadout icons up from, and where they
#: land inside the bundle. Git-ignored; see the module docstring.
ART_SOURCE = "private-art"
ART_TARGET = os.path.join("assets", "gearicons")

HIDDEN = [
    "cli", "gui", "gui.app", "gui.theme", "gui.widgets", "gui.controls",
    "gui.presets", "tcps2", "tcps2.iso", "tcps2.soz", "tcps2.vokes",
    "tcps2.art", "tcps2.model", "tcps2.engine", "tcps2.detect",
    "tcps2.games", "tcps2.games.r6_3", "tcps2.games.ghost_recon",
    "tcps2.games.jungle_storm", "tcps2.games.ghost_recon2",
    "tcps2.games.graw", "tcps2.games.soaf", "tcps2.games.lockdown",
    "tcps2.games.r6tuning", "tcps2.games.rstuning", "tcps2.nimitz",
    "tcps2.lin", "tcps2.rselzo", "tcps2.transforms", "tcps2.dataedit",
    "tcps2.overlay", "tcps2.rsb", "gui.dialog", "gui.skins", "gui.gearicons", "gui.tooltip", "tcps2.utexture",
    "tcps2.psx", "tcps2.upscale",
    "tcps2.rseloadout", "tcps2.rseguns", "tcps2.rsemissions",
    "tcps2.rsewheel", "tcps2.rserpg", "tcps2.rsesidearm", "tcps2.rsescope", "tcps2.rsedraw",
    "tcps2.rsemandown", "tcps2.uscode", "tcps2.rsecanon", "tcps2.rseshadow", "tcps2.rsekits",
    "tcps2.rsechatter",
    # zopfli packs the LIN chunks zlib cannot fit back into their
    # slots. Without it those chunks simply refuse every edit.
    "zopfli", "zopfli.zlib",
    "tcps2.localise", "tcps2.upackage", "tcps2.r6zones",
    "tcps2.games.xboxbuild", "tcps2.games.rseweapons",

    # Discord presence speaks the IPC protocol itself, so this pulls in no
    # third-party package -- but the modules still have to be named here.
    "gui.presence", "gui.discorddialog", "webbrowser",
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
       "name": "Tom Clancy PS2 Mod Studio"}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main():
    version = app_version()
    with_art = "--with-art" in sys.argv
    art = os.path.join(ROOT, ART_SOURCE, "gearicons")
    if with_art and not os.path.isdir(art):
        print("--with-art was asked for but %s does not exist" % art)
        return 2
    preview = "--preview" in sys.argv
    name = NAME + (" (art)" if with_art else "") + (" (preview)" if preview else "")
    print("building version %s%s" % (version,
                                     "  [private, with game art]" if with_art
                                     else "  [public, no game art]"))
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
    if with_art:
        args += ["--add-data", "%s%s%s" % (art, os.pathsep, ART_TARGET)]
    if preview:
        # A marker rather than a code change, so the preview build is the same
        # binary as the public one plus one empty file.
        flag = os.path.join(ROOT, "build", "preview.mode")
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as fh:
            fh.write("built by build_exe.py --preview" + chr(10))
        args += ["--add-data", "%s%s%s" % (flag, os.pathsep, "assets")]
    build_dir = os.path.join(ROOT, "build")
    os.makedirs(build_dir, exist_ok=True)
    args += ["--version-file",
             write_version_file(os.path.join(build_dir, "version.txt"), version)]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    for e in EXCLUDE:
        args += ["--exclude-module", e]
    args.append(os.path.join(ROOT, ENTRY))

    print(" ".join(args))
    rc = subprocess.call(args, cwd=ROOT)
    if rc:
        return rc
    exe = os.path.join(ROOT, "dist", name + ".exe")
    print("\n%s  v%s  (%.1f MB)"
          % (exe, version, os.path.getsize(exe) / 1048576.0))
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
