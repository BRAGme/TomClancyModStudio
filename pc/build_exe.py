r"""Produce dist/Tom Clancys PC ModStudio <version>.exe.

    python build_exe.py              -- the ordinary build
    python build_exe.py --preview    -- a build that opens in preview mode, for
                                        looking round the options without
                                        owning the games

**No game art is bundled, and that is not an option here.** Every picture the
window uses is decoded from the user's own installation at run time and cached
under %LOCALAPPDATA%; none of it is in this repository and none of it is in the
executable. A machine without the games gets a bare window, which is the
correct outcome.

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
#:
#: The VERSION is part of the filename on purpose. With a fixed name every
#: build downloads over the last one, and a user who opens the copy already
#: sitting on their desktop is running old code with no way of telling --
#: which happened, and cost a round trip working out why new options were
#: "missing".
NAME = "Tom Clancys PC ModStudio"

#: the script PyInstaller is pointed at
ENTRY = "ModStudio.py"

def _package_modules(*packages):
    """Every module in our own packages, named for PyInstaller.

    This used to be a hand-written list, and by version 2.2 it had gone stale
    by six modules. They shipped anyway -- PyInstaller's own analysis follows
    a plain `import` perfectly well -- but a list that has to be remembered is
    a list that will be wrong on the day it matters, which is the day a module
    is reached dynamically. So it is walked instead.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    out = []
    for pkg in packages:
        out.append(pkg)
        for root, _dirs, files in os.walk(os.path.join(here, *pkg.split("."))):
            rel = os.path.relpath(root, here).replace(os.sep, ".")
            for f in sorted(files):
                if f.endswith(".py"):
                    name = rel if f == "__init__.py" else "%s.%s" % (rel, f[:-3])
                    if name not in out:
                        out.append(name)
    return out


HIDDEN = _package_modules("gui", "tcpc") + [
    'cli',
    'webbrowser',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageEnhance',
    'PIL.ImageFilter',
    'PIL.ImageOps',
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
       "name": "Tom Clancy PC Mod Studio"}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main():
    version = app_version()
    preview = "--preview" in sys.argv
    name = "%s %s%s" % (NAME, version, " (preview)" if preview else "")
    print("building version %s" % version)
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
    if preview:
        # A marker rather than a code change, so the preview build is the
        # same binary as the ordinary one plus one empty file.
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
