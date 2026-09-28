"""A shotgun for Jungle Storm (SLUS-20820), out of parts the disc already carries.

Jungle Storm ships no shotgun, but it ships everything one needs:

  * **The pellets are already in the engine.** A `<SelectiveOption>` may set
    `RoundsPerPull`, and SimHuman's firing routine (JS 0x003B20C0) loops that
    many times per trigger pull, sending a separate Gunshot message (0x200)
    each time -- and every round is aimed through the reticule's own random
    deviation (0x00383EE0, two RSRandom draws per round), so the rounds of one
    pull land in a cone, not on one line.  That is a shotgun.  Every shipped
    gun sets `RoundsPerPull` to 1 and the spread comes from the accuracy
    fields, which is why nobody notices.  (Sum of All Fears, the same engine,
    added `<ProjectileCount>` and `<ProjectileSpread>` instead -- neither
    string exists in Ghost Recon's or Jungle Storm's executable, so that route
    would need code.  This one needs none: no instruction is patched.)

  * **A free gun slot.** `G36.GUN` is listed in `EQUIP_GUN.DIR`, is carried by
    no kit, and its model `W_HK_G36.QOB` is not on the disc at all -- a leftover
    of a cut weapon, the same free slot SQUIRREL.PRJ was for smoke.  It becomes
    the shotgun, so no weapon is lost and nothing new has to be added to
    GR.IMG (the archive writer can replace a file but not add one).

  * **A shotgun model.** `W_M4_MASTERKEY_SHOTGUN.QOB` is on the disc, in both
    Ghost Recon and Jungle Storm, and referenced by nothing.  A gun may name a
    `w_*` model as well as an `iw_*` one -- the M98 does.

  * **A name.** `WPN_G36` has no line in STRINGS.TXT, so a PC-only keybinding
    line no build of this game can reach ("sidestep_right") carries it, the
    same trick the smoke label uses on "toggle_console".  Same length, so the
    LZO container keeps its size.

One honest consequence: the loop spends one round of the magazine per pellet
(it is clamped by what is in the weapon, JS 0x002C3130), so the magazine is
sized pellets x shells and the HUD counts pellets rather than shells.
"""

from __future__ import annotations

import re
import struct

# ---- what the shotgun is -----------------------------------------------------------------------
DONOR = "/G36.GUN"                                        # the dead slot the shotgun takes over
DONOR_XBG = "/G36.XBG"                                    # its compiled twin, the file the game loads
_DONOR_MODEL = b"w_hk_g36.qob"                            # the cut model, which is not on the disc
DONOR_SIZE = 2690                                         # its plain length; LZO, so this must not change
MODEL = "w_m4_masterkey_shotgun.qob"                      # on the disc, used by nothing else
LABEL_TOKEN = "WPN_G36"                                   # G36.GUN's own token, which has no string
LABEL_TEXT = "SHOTGUN"
LABEL_DONOR = "sidestep_right"                            # a PC keybinding line the PS2 build cannot reach
SHELLS = 8                                                # shells in a full magazine
PELLETS = {"6": 6, "8": 8, "9": 9}    # 9 is what Heroes Unleashed gives all three of its shotguns
#: A trigger pull fires however many rounds the rate of fire has allowed since the pull began
#: (SimHuman 0x003B2150: floor(elapsed x RateOfFire / 60)), and RoundsPerPull only CAPS that for a weapon that
#: is not full auto.  So the pellets come out together only if the rate is high enough to allow all of them
#: inside one frame: 8 pellets at 60 fps needs 28,800.  At 120 the gun fired one round every half second, which
#: is exactly what a first attempt at this did.
RATE = 40000
#: The cut G36 carries a 24x24 reticule rectangle on reticle_car.rsb, whose art is 32x32 -- so the ring drew
#: with its right and bottom quarters missing.  Every gun that still uses that texture (MP5, SOPMOD M4, Bizon)
#: agrees on these: pip and base rectangles, then the pip's base and maximum offsets.
_RETICLE = (0.0, 0.0, 32.0, 32.0, 33.0, 0.0, 37.0, 2.0, 4.0, 120.0)
_GD = (2, 3, 8, 9)                                        # the menu bars: accuracy, stability, recoil, damage
SOUND = "w_ak47_ss.wav"
# Two things decide this. A weapon's sound is loaded per LEVEL from the weapons in it, so a sound belonging to a
# gun nobody carries is silent -- the Barrett's was, and the shotgun made no noise at all. And "_sf" is a full
# auto weapon's SUSTAINED FIRE loop, not one shot: the M16's turned one pull into what sounded like a seven round
# burst. "_ss" is a single shot, and the M9 is the sidearm every kit carries, so it is always in memory.

#: the kits that carry it, per choice.  The shotgun replaces that kit's rifle.
SHOTGUN_KITS = {
    "none": (),
    "some": ("RIFLEMAN-02", "DEMOLITIONS-02"),
    "all": ("RIFLEMAN-02", "RIFLEMAN-06", "DEMOLITIONS-02", "DEMOLITIONS-06",
            "HEAVY-WEAPONS-02", "SNIPER-02"),
}


#: Heroes Unleashed's shotguns (m1014, m870p, saiga12k -- all three agree) keep RIFLE-tight accuracy: 7.2
#: standing, against its own M16's 6.19.  On the PC the pattern is a separate <ProjectileSpread>0.01</> over
#: <ProjectileCount>9</>, and neither field exists in Ghost Recon's or Jungle Storm's PS2 executable.  So on the
#: PS2 the accuracy cone is the only lever there is, and it has to be both the aim and the pattern: every round
#: of the pull is deviated through it separately.  Too wide and the gun simply does not point where you aim,
#: which is what a first attempt at 170, and then 50, got wrong.  These are HU's own, scaled by the setting.
_HU_ACC = (231.35, 318.76, 2662.28,        # run: stand, crouch, prone
           48.05, 62.93, 2662.28,          # walk
           15.49, 19.88, 2662.28,          # shuffle
           7.23, 4.10, 2.62)               # stationary
SPREADS = {"hu": 1.0, "medium": 2.0, "wide": 4.0}
_ACC_NAMES = [m + st + "Accuracy" for m in ("Run", "Walk", "Shuffle", "Stationary")
              for st in ("Stand", "Crouch", "Prone")]


def _acc(spread):
    k = SPREADS.get(spread, 1.0)
    return {n: "%g" % (v * k) for n, v in zip(_ACC_NAMES, _HU_ACC)}


#: the rest of Heroes Unleashed's M1014, in the .GUN's own spelling (the compiler stores |x| for these)
_NUMBERS = dict(Weight="3.95", MaxRange="100", MagazineWeight="0.32", Recoil="117.2",
                VelocityCoefficient0="403.9", VelocityCoefficient1="-0.841", VelocityCoefficient2="-0.086089",
                KillCoefficient1="1.426671", KillCoefficient2="0.027227", StabilizationTime="0.25")


#: what the shotgun changes in the shipped G36.GUN besides the numbers above.  Everything else -- the turn
#: bands, the motion type -- is the donor's own, so the file stays one this build already reads.
_VALUES = [("ModelFileName", MODEL), ("MuzzleFlashScale", "1.74"), ("TracerFrequency", "0")]


def _set(plain: bytes, tag: str, value: str) -> bytes:
    pat = re.compile(rb"<%s>[^<]*</%s>" % (tag.encode(), tag.encode()))
    if not pat.search(plain):
        raise ValueError("%s has no <%s>" % (DONOR, tag))
    return pat.sub(("<%s>%s</%s>" % (tag, value, tag)).encode(), plain, count=1)


def _fit(plain: bytes, n: int) -> bytes:
    """Back to exactly n bytes: spaces before the closing tag, or indentation given up, both ignored by the reader."""
    if len(plain) < n:
        return plain.replace(b"</GunFile>", b" " * (n - len(plain)) + b"</GunFile>", 1)
    lines = plain.split(b"\n")
    over = len(plain) - n
    while over > 0:
        k = max(range(len(lines)), key=lambda i: len(lines[i]) - len(lines[i].lstrip(b" \t")))
        if lines[k][:1] not in (b" ", b"\t"):
            raise ValueError("no indentation left: the shotgun's GunFile is %d bytes over" % over)
        lines[k] = lines[k][1:]
        over -= 1
    return b"\n".join(lines)


def shotgun_gun(donor: bytes, pellets: int, spread: str = "hu") -> bytes:
    """The shipped G36.GUN turned into a shotgun, at exactly its own length.  Ghost Recon ships no compiled
    twin and reads this file itself, so everything the gun is has to be said here."""
    out = donor
    for tag, value in list(_VALUES) + sorted(_NUMBERS.items()) + sorted(_acc(spread).items()):
        out = _set(out, tag, value)
    out = _set(out, "MagazineCapacity", str(pellets * SHELLS))
    # one trigger pull, `pellets` rounds, each aimed through its own deviation
    opt = re.search(rb"<SelectiveOption[^/]*/>", out)
    if not opt:
        raise ValueError("%s has no <SelectiveOption>" % DONOR)
    out = out[:opt.start()] + ('<SelectiveOption RateOfFire = "%d" RoundsPerPull = "%d" StartSound = "%s"/>'
                               % (RATE, pellets, SOUND)).encode() + out[opt.end():]
    # the cut G36 carries a 24x24 reticule rectangle for a 32x32 piece of art, so its ring drew a quarter short
    for tag, value in zip(("ReticuleBaseLeft", "ReticuleBaseTop", "ReticuleBaseRight", "ReticuleBaseBottom",
                           "ReticulePipLeft", "ReticulePipTop", "ReticulePipRight", "ReticulePipBottom",
                           "ReticulePipBaseOffset", "ReticulePipMaxOffset"),
                          ("0", "0", "32", "32", "33", "0", "37", "2", "4", "120")):
        out = _set(out, tag, value)
    # the second zoom is the scope; a shotgun has none
    out = re.sub(rb"<Zoom>[^<]*</Zoom>(\s*)<Zoom>[^<]*</Zoom>",
                 rb"<Zoom>1</Zoom>\g<1><Zoom>1.5</Zoom>", out, count=1)
    return _fit(out, len(donor))


class _Reader:
    def __init__(self, b):
        self.b, self.o = b, 0

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.o)[0]; self.o += 4; return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.o)[0]; self.o += 4; return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.o)[0]; self.o += 2; return v

    def u8(self):
        v = self.b[self.o]; self.o += 1; return v

    def s(self):
        n = self.u32(); v = self.b[self.o:self.o + n]; self.o += n; return v


def shotgun_xbg(donor: bytes, pellets: int, spread: str = "hu") -> bytes:
    """The compiled G36 turned into the shotgun.

    Only the strings and the fire mode are spliced here; every number goes through grhu's field table, which
    already knows this format.  The donor is recognised by its model and name token, which nothing else edits --
    the weapon options may well have rewritten its numbers before this runs, and this is meant to run last.
    """
    from . import grhu
    r = _Reader(donor)
    r.f32()
    model_at = r.o
    model = r.s()
    model_end = r.o
    r.f32()
    token = r.s()
    if model != _DONOR_MODEL or token != LABEL_TOKEN.encode():
        raise ValueError("%s: not the compiled G36 (model %r, token %r)" % (DONOR_XBG, model, token))
    r.u16()
    for _ in range(6):
        r.f32()
    n = r.u32()
    if n != 1:
        raise ValueError("%s: %d selective options, expected 1" % (DONOR_XBG, n))
    opt_at = r.o
    r.o += 5
    start_at = r.o
    r.s()
    end_at = r.o
    r.s()
    tail = r.o
    out = bytearray(donor)
    # spliced back to front, so the offsets taken above stay good
    out[end_at:tail] = struct.pack("<I", 0)                             # no tail-off sound
    out[start_at:end_at] = struct.pack("<I", len(SOUND)) + SOUND.encode()
    out[opt_at:opt_at + 5] = struct.pack("<HHB", RATE, pellets, 0)      # rate, rounds per pull, not full auto
    out[model_at:model_end] = struct.pack("<I", len(MODEL)) + MODEL.encode()
    # the four menu stat bars are the last four words of the file; G36's are zero, so its bars read empty
    out[-16:] = struct.pack("<4I", *_GD)
    values = dict(_NUMBERS, MagazineCapacity=str(pellets * SHELLS), **_acc(spread))
    out = bytearray(grhu.set_xbg_values(bytes(out), values)[0])
    at = grhu.xbg_fields(bytes(out))["StabilizationTime"][0] - 40      # the reticule block sits just before it
    if struct.unpack_from("<4f", out, at) != (0.0, 0.0, 24.0, 24.0):
        raise ValueError("%s: the reticule rectangle is not the cut G36's" % DONOR_XBG)
    struct.pack_into("<10f", out, at, *_RETICLE)
    return bytes(out)


def _op_shotgun_xbg(plain, params):
    out = shotgun_xbg(plain, int(params.get("pellets", 9)), params.get("spread", "hu"))
    return out, 1


# ---- the data edits ----------------------------------------------------------------------------
def _op_shotgun_gun(plain, params):
    if b"<NameToken>%s</NameToken>" % LABEL_TOKEN.encode() not in plain:
        raise ValueError("%s is not the shipped file" % DONOR)
    out = shotgun_gun(plain, int(params.get("pellets", 9)), params.get("spread", "hu"))
    if len(out) != len(plain):
        raise ValueError("the shotgun's GunFile is %d bytes, not %s's %d" % (len(out), DONOR, len(plain)))
    return out, 1


def _op_shotgun_label(plain, params):
    """The shotgun's name, on a PC-only keybinding line, at exactly its length."""
    m = re.search(rb'\t"%s"(\t+)"[^"\r\n]*"' % LABEL_DONOR.encode(), plain)
    if not m:
        raise ValueError("no %s line to carry the shotgun's name" % LABEL_DONOR)
    head, tail = b'\t"' + LABEL_TOKEN.encode() + b'"', b'"' + LABEL_TEXT.encode() + b'"'
    tabs = len(m.group()) - len(head) - len(tail)
    if tabs < 1:
        raise ValueError("the %s line is too short to carry %s" % (LABEL_DONOR, LABEL_TOKEN))
    return plain[:m.start()] + head + b"\t" * tabs + tail + plain[m.end():], 1


_KIT_GUN = re.compile(rb"([ \t]*)<ItemFileName>([a-z0-9_\-]+)\.gun</ItemFileName>", re.I)


def _op_shotgun_kit(plain, params):
    """The kit's first firearm becomes the shotgun, keeping the file's length with indentation."""
    m = _KIT_GUN.search(plain)
    if not m:
        raise ValueError("kit carries no firearm")
    if m.group(2).lower() == b"g36":
        return plain, 0
    out = plain[:m.start()] + m.group().replace(m.group(2) + b".gun", b"g36.gun") + plain[m.end():]
    lines = out.split(b"\n")
    need = len(out) - len(plain)
    while need > 0:                                       # longer: pay with the deepest indentation
        k = max(range(len(lines)), key=lambda i: len(lines[i]) - len(lines[i].lstrip(b" \t")))
        if lines[k][:1] not in (b" ", b"\t"):
            raise ValueError("no indentation left to keep the kit's length")
        lines[k] = lines[k][1:]
        need -= 1
    while need < 0:                                       # shorter: give the indentation back
        k = max(range(len(lines)), key=lambda i: len(lines[i]) - len(lines[i].lstrip(b" \t")))
        lines[k] = lines[k][:1] + lines[k]
        need += 1
    out = b"\n".join(lines)
    if len(out) != len(plain):
        raise ValueError("kit length %d != %d" % (len(out), len(plain)))
    return out, 1


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("shotgun_gun", _op_shotgun_gun)
    dataedit.OPS.setdefault("shotgun_xbg", _op_shotgun_xbg)
    dataedit.OPS.setdefault("shotgun_label", _op_shotgun_label)
    dataedit.OPS.setdefault("shotgun_kit", _op_shotgun_kit)


_register()


def data_edits(v: dict, prefix: str = "js_") -> list:
    """Ghost Recon reads the .GUN itself and ships no .XBG, so it gets every field through the XML;
    Jungle Storm reads the compiled twin, and gets both so the pair stays consistent."""
    if not v.get(prefix + "shotgun"):
        return []
    from .model import FileEdit
    pellets = PELLETS.get(str(v.get(prefix + "shotgun_pellets", "9")), 9)
    spread = v.get(prefix + "shotgun_spread", "hu")
    out = [FileEdit("shotgun_gun", r"/G36\.GUN$", "GR.IMG", {"pellets": pellets, "spread": spread},
                    "G36.GUN becomes a %d-pellet shotgun" % pellets),
           FileEdit("shotgun_label", r"STRINGS\.TXT$", "GR.IMG", {}, "%s = %s" % (LABEL_TOKEN, LABEL_TEXT))]
    if prefix == "js_":
        out.insert(1, FileEdit("shotgun_xbg", r"/G36\.XBG$", "GR.IMG", {"pellets": pellets, "spread": spread},
                               "the compiled gun the game loads, the same %d-pellet shotgun" % pellets))
    kits = SHOTGUN_KITS.get(v.get(prefix + "shotgun_kits", "some"), ())
    if kits:
        out.append(FileEdit("shotgun_kit", r"/(%s)\.KIT$" % "|".join(re.escape(k) for k in kits), "GR.IMG", {},
                            "%d kit(s) carry the shotgun" % len(kits)))
    return out


def js_edits(v: dict) -> list:
    """No instruction is patched: the shotgun is entirely data."""
    return []
