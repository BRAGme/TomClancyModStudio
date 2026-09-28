"""Running the game off loose files instead of the disc.

What is on the disc
-------------------

Ubisoft left the dev-kit **host filesystem** in the retail PS2 build. A single
global -- `gp-0x7f60` in `SP.SOZ` -- decides whether the game builds its data
paths for the DVD or for the development host, and 25 sites read it. The vokes
path builder at `PATH_BUILDER` is the one that matters:

    prefix buffer (0x006c4130, empty at runtime)
      + "host0:"  if the flag is set, else "\\"
      + "vokeslm" | "vokesm" | "vokes0" | "vokes1" | "vokes2"
      + ".img"
      + ";1"      only when the flag is clear

so host mode opens exactly ``host0:vokes0.img`` -- a complete, valid path with
nothing left over. Nearby openers do the same for `host0:sounds\\%s`,
`host0:vokes.profile` and loose `psx2game.ini` / `r6gamesettings.ini`.

The flag itself is set from a **command line token**. `FLAG_WRITER` is the one
and only writer, and it stores the result of `strstr(cmdline, "-host")` against
the buffer at `CMDLINE`, which really is a live command line -- a running game
reads e.g. ``-map=meatpacking_a   -loadgvs -ll INI=psx2game.ini``. `-usecd` and
`-debugcd` sit beside it.

Why three words and not one
---------------------------

Forcing the flag alone is not enough, measured twice. As a pnach it never
arrives in time -- PCSX2 applies cheats per frame and the archive mount is over
before the first one lands -- and even **baked into the overlay** it did not
take, because the command-line parse that sets the flag runs after the mount.
That is the same trap the wave work hit with `bStasis`: when an init-time write
does not stick, patch the branch that reads it. So `edits()` forces the two
tests inside the path builder as well, which is what actually worked.

What the emulator has to do
---------------------------

PCSX2 serves `host:` and `host<N>:`, so `host0:` resolves. Two conditions:

* **Enable Host Filesystem** (`EmuCore/HostFs`) must be on -- it is off by
  default and is overridable per game.
* There must be a host root, and **an ISO boot does not set one** on the build
  this was tested against. Booting an **ELF override** does: the root becomes
  the folder holding that ELF. So the loose data lives beside a copy of
  `SLUS_208.83`, and the ISO is still mounted alongside it::

      pcsx2-qt.exe -elf "<root>\\SLUS_208.83" "<root>\\game.iso"

  PCSX2 confirms it in its own log: ``HLE Host: Set 'host:' root path to: ...``

Verified, 2026-09-18
--------------------

With the three words baked into the test ISO's `SP.SOZ` and an ELF-override
boot, the running game held ``<root>\\vokes0.img`` open (an exclusive open
failed with a sharing violation, which does not happen when PCSX2 is running
with no game), the IOP modules loaded from `host0:`, and after the disc copy's
own header was zeroed so no fallback existed the game still reached a map load
and wrote **`-host`** into its own command line.

Still unproven: that an *edit* to a loose archive changes what is played. That
needs a gameplay test, so nothing here is exposed as a setting yet.
"""

from __future__ import annotations

from .model import WordEdit

#: the vokes path builder, and the two tests inside it that pick the device
PATH_BUILDER = 0x001C3F50
PREFIX_TEST = 0x001C3F84          # beq $v0,$zero,+8  -> take the "\" branch
VERSION_TEST = 0x001C40D8         # bne $v0,$zero,+9  -> skip the ";1" suffix

#: the single writer of the host flag, and the flag's own gp-relative slot
FLAG_WRITER = 0x001C4D6C          # beq $v0,$zero,+4  -> "-host" was absent
FLAG_STORE = 0x001C4D84           # sw $s3, -0x7f60($gp)
FLAG_GP_OFFSET = -0x7F60

#: the game's live command line, empty in the image and filled at boot
CMDLINE = 0x005B7DC0

#: switch strings the parser knows
SWITCHES = {"host": 0x005DA4A8, "usecd": 0x005DA4E0, "debugcd": 0x005DBD08}

#: every word this module touches: va -> (stock, forced, why)
WORDS = {
    PREFIX_TEST:  (0x10400008, 0x00000000, 'the prefix is always "host0:"'),
    VERSION_TEST: (0x14400009, 0x10000009, 'never append the ";1" CD suffix'),
    FLAG_WRITER:  (0x10400004, 0x00000000, "the -host flag reads as set"),
}

#: the archive names the builder can produce, in the order it tests them
ARCHIVES = ("vokeslm", "vokesm", "vokes0", "vokes1", "vokes2")

#: what a host root has to contain beside the loose archives for an ELF
#: override to boot: the ELF itself, and everything the loader pulls in early.
ROOT_NEEDS = ("SLUS_208.83", "SYSTEM.CNF", "SP.SOZ", "MP.SOZ",
              "GVS.DAT", "GVSOFF.DAT", "GSROUTER.DAT", "IRX", "OVL",
              "NTSC_CD")


def edits() -> list:
    """The words that move the vokes file system onto `host0:`."""
    return [WordEdit(va, forced, stock, "host filesystem: " + why)
            for va, (stock, forced, why) in sorted(WORDS.items())]


def grow_archive(path: str, extra: int) -> tuple:
    """Add `extra` blank bytes to the end of a LOOSE vokes archive.

    This is the thing the disc cannot do. Inside an ISO an archive is pinned to
    its extent, so once its free runs are used up -- and `vokes0.img` on a
    played disc is already packed solid -- a file that grows has nowhere to go
    and the write is refused. A loose archive is an ordinary file: append
    zeros, tell the header about them, and `Vokes.free_blocks` offers the new
    room on the next open, because it takes the end of the archive from that
    header field rather than from the ISO directory.

    Returns (oldSize, newSize). Blank, because `allocate` reads every candidate
    run and refuses anything that is not all zeros.
    """
    import os
    import struct

    if extra <= 0:
        raise ValueError("extra must be positive")
    old = os.path.getsize(path)
    with open(path, "r+b") as fh:
        declared = struct.unpack("<I", fh.read(4))[0]
        if declared != old:
            raise ValueError("%s: header says %d bytes but the file is %d -- "
                             "refusing to guess which is right"
                             % (os.path.basename(path), declared, old))
        fh.seek(0, os.SEEK_END)
        fh.write(b"\0" * extra)
        fh.seek(0)
        fh.write(struct.pack("<I", old + extra))
    return old, old + extra


def launch_command(root: str, iso: str, exe: str) -> list:
    """The argv that gives PCSX2 a host root at `root`.

    The ELF override is not cosmetic -- it is the only thing that sets the
    root on the build this was tested against.
    """
    import os
    return [exe, "-elf", os.path.join(root, "SLUS_208.83"), iso]
