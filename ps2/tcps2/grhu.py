"""Heroes Unleashed, PS2: the data-file half of the port (Ghost Recon and Jungle Storm).

Heroes Unleashed is a PC realism mod. The parts of it these discs can take are
built from its own files, value for value:

  * spotting distances -- code, see grhuspot;
  * the damage model -- CMBTMODL.XML. The PS2 file has the same eleven fields
    as HU's, including the four armour levels. HU's head factor is -1: the
    kill chance is 1 - factor / energy (CombatModelFile::GetKillChance, GR
    0x003D4AE0), so a negative factor makes every head hit lethal, as on PC.
    Chest 100 as stock; abdomen 300 (stock 400); arms 1350 / 2050 and legs
    900 / 1800 (stock 700 / 1000 / 500 / 800) -- limb hits are survivable,
    torso and head hits are not. Armour 0 / 400 / 750 / 950 (stock 0 / 150 /
    350 / 750).

  * weapons -- every PS2 .GUN with an HU counterpart takes that gun's
    ballistics (velocity and kill coefficients, range), weight and magazine,
    recoil, all twelve stance/movement accuracies, turn bands and settle
    time, exactly as HU writes them. HU gives the AI its own, far less
    accurate copy of each gun (<name>_npc.gun). Jungle Storm already keeps
    separate player copies of the AK family (PLAYER_AK47...): those take
    HU's player numbers and the AI's copies HU's AI numbers. Every other gun
    is one file shared by you and the AI, so the setting picks whose numbers
    it gets. Fire modes, zoom levels and reticles stay as shipped; so do the
    stationary guns and the three with no HU counterpart (A-91, Z84, the
    generic NATO MG).

  * soldier skills -- not HU's numbers. HU rewrites every soldier on a
    25-255 scale (weapon skill 0.025-0.255 for most enemies); this engine
    reads the four skills as whole numbers and clamps the adjusted skill to
    0-8 (IkeSimulationMgr::GetAdjustedWeapon, GR 0x0039D8E0), so HU's values
    would make every enemy the worst possible shot and every soldier on both
    sides a perfect sneak. What is ported is HU's stated aim -- "no longer
    any enemies with super-human weapon accuracy": every hostile template's
    weapon skill two steps lower (never below 1). Your squad is untouched.

Where the numbers go differs by game. Ghost Recon reads the .GUN XML: those
files are compressed and must keep their length, so `hu_values` writes HU's
numbers exactly and gives the bytes back from indentation, CRLF and trailing
zeros of the numbers it does not change. Jungle Storm never reads a .GUN -- it
loads each gun's compiled twin, <name>.XBG, so `hu_xbg` writes the same
numbers into those binary fields in place (see xbg_fields). CMBTMODL.XML's
values fit its stock widths as they are.
"""

from __future__ import annotations

import re

from .model import FileEdit

_NUMBER = re.compile(rb"(<(\w+)>)(\s*)(-?\d+(?:\.\d+)?)(\s*)(</\2>)")
_ZEROS = re.compile(rb"(<(\w+)>\s*-?\d+\.\d*?)(0+)(\s*</\2>)")


def _fit_length(buf: bytes, n: int, keep: set) -> bytes:
    """`buf` brought to exactly `n` bytes without changing what it says.

    Longer: indentation (whitespace between a newline and a tag) goes first,
    then the carriage return of CRLF pairs, then trailing zeros of numbers
    whose tags are not in `keep` (15.000000 -> 15.0). Shorter: a tab of
    indentation goes back after a newline. Raises ValueError when there is not
    enough to shed.
    """
    out = bytearray(buf)
    while len(out) > n:
        m = re.search(rb"\n[\t ]+<", out)
        if m:
            del out[m.start() + 1]
            continue
        i = out.find(b"\r\n")
        if i >= 0:
            del out[i]
            continue
        for m in _ZEROS.finditer(bytes(out)):
            if m.group(2).decode("latin1") in keep:
                continue
            body = m.group(1)
            if body.endswith(b".") and len(m.group(3)) == 1:
                continue                       # keep one decimal: 15.0
            del out[m.end(1)]
            break
        else:
            raise ValueError("no inert bytes left to shed")
    while len(out) < n:
        i = out.find(b"\n")
        if i < 0:
            raise ValueError("nowhere to pad")
        out[i + 1:i + 1] = b"\t"
    return bytes(out)


def set_values_exact(plain: bytes, values: dict):
    """Write each tag's value exactly as given, keeping the file's length (see _fit_length)."""
    count = [0]

    def sub(m):
        tag = m.group(2).decode("latin1")
        if tag not in values:
            return m.group(0)
        new = values[tag].encode("latin1")
        if new == m.group(4):
            return m.group(0)
        count[0] += 1
        return m.group(1) + m.group(3) + new + m.group(5) + m.group(6)

    out = _NUMBER.sub(sub, plain)
    return _fit_length(out, len(plain), set(values)), count[0]


def _op_hu_values(plain, params):
    return set_values_exact(plain, params.get("values", {}))


# ---- Jungle Storm's compiled guns ------------------------------------------
# Jungle Storm never reads a .GUN: every gun ships a compiled twin, <name>.XBG
# (uncompressed, ~300 bytes), and that is what the game loads -- a save state
# of a disc whose .GUN files carried HU's numbers held none of them, and holds
# the XBG's form of the stock ones (the compiler stores |x| for the velocity and
# kill coefficients; -0.890357 in AK47.GUN is +0.890357 in AK47.XBG and in
# memory). Ghost Recon has no XBG files and reads the XML.
#
# Layout (little-endian, strings are u32 length + bytes), checked field for
# field against the .GUN of all 66 Jungle Storm guns:
#   f32 VersionNumber, str model, f32 Weight, str name token, u16 magazine,
#   f32 MaxRange, VelocityCoefficient0..2, KillCoefficient1..2,
#   u32 n selective options x (u16 rate, 3 x u8 flags, str start, str end sound),
#   3 x f32 zoom, f32 MagazineWeight, Recoil, the 12 accuracies (run / walk /
#   shuffle / stationary x stand / crouch / prone), TurnBandVelocity1..5,
#   TurnBandMultiplier1..5, str reticle, 10 x f32 reticle, f32 StabilizationTime, ...
_XBG_ACC = [m + s + "Accuracy" for m in ("Run", "Walk", "Shuffle", "Stationary")
            for s in ("Stand", "Crouch", "Prone")]
_XBG_ABS = {"VelocityCoefficient1", "VelocityCoefficient2", "KillCoefficient1", "KillCoefficient2"}


def xbg_fields(b: bytes) -> dict:
    """{tag: (offset, 'f' or 'h')} of the numeric fields an .XBG carries."""
    o = 0
    out = {}

    def need(n):
        if o + n > len(b):
            raise ValueError("XBG ends inside a field at 0x%x" % o)

    def f(tag):
        nonlocal o
        need(4); out[tag] = (o, "f"); o += 4

    def s():
        nonlocal o
        need(4); n = int.from_bytes(b[o:o + 4], "little")
        if n > 128:
            raise ValueError("XBG string of %d bytes at 0x%x" % (n, o))
        need(4 + n); o += 4 + n

    f("VersionNumber"); s(); f("Weight"); s()
    need(2); out["MagazineCapacity"] = (o, "h"); o += 2
    for t in ("MaxRange", "VelocityCoefficient0", "VelocityCoefficient1", "VelocityCoefficient2",
              "KillCoefficient1", "KillCoefficient2"):
        f(t)
    need(4); nsel = int.from_bytes(b[o:o + 4], "little"); o += 4
    if nsel > 8:
        raise ValueError("XBG with %d selective options" % nsel)
    for _ in range(nsel):
        need(5); o += 5; s(); s()
    need(12); o += 12
    for t in ["MagazineWeight", "Recoil"] + _XBG_ACC:
        f(t)
    for k in range(1, 6):
        f("TurnBandVelocity%d" % k)
    for k in range(1, 6):
        f("TurnBandMultiplier%d" % k)
    s()
    need(40); o += 40
    f("StabilizationTime")
    return out


def set_xbg_values(b: bytes, values: dict):
    """Write each tag's value into the compiled gun, as the compiler would have."""
    import struct
    fields = xbg_fields(b)
    out = bytearray(b)
    n = 0
    for tag, text in values.items():
        if tag not in fields or tag == "VersionNumber":
            continue
        off, kind = fields[tag]
        x = float(text)
        if tag in _XBG_ABS:
            x = abs(x)
        new = struct.pack("<H", int(round(x))) if kind == "h" else struct.pack("<f", x)
        if bytes(out[off:off + len(new)]) != new:
            out[off:off + len(new)] = new
            n += 1
    return bytes(out), n


def _op_hu_xbg(plain, params):
    return set_xbg_values(plain, params.get("values", {}))


def _register():
    """Make `hu_values` and `hu_xbg` operations the data editor knows, without editing it."""
    from . import dataedit
    dataedit.OPS.setdefault("hu_values", _op_hu_values)
    dataedit.OPS.setdefault("hu_xbg", _op_hu_xbg)


_register()

#: Mods/Heroes Unleashed/equip/cmbtmodl.xml
HU_COMBAT_MODEL = {
    "BallisticHeadFactor": "-1.0",
    "BallisticChestFactor": "100.0",
    "BallisticArmoredChestFactor0": "0.0",
    "BallisticArmoredChestFactor1": "400.0",
    "BallisticArmoredChestFactor2": "750.0",
    "BallisticArmoredChestFactor3": "950.0",
    "BallisticAbdomenFactor": "300.0",
    "BallisticUpperArmFactor": "1350.0",
    "BallisticLowerArmFactor": "2050.0",
    "BallisticUpperLegFactor": "900.0",
    "BallisticLowerLegFactor": "1800.0",
}


def on(prefix: str, v: dict, part: str) -> bool:
    """Is this Heroes Unleashed part asked for, directly or through the all-in-one switch?"""
    return bool(v.get(prefix + "hu_all") or v.get(prefix + "hu_" + part))


def without_overridden(prefix: str, v: dict) -> dict:
    """The values with the cards HU replaces put back to stock, so the two never both edit a file."""
    if on(prefix, v, "damage"):
        v = dict(v)
        v[prefix + "lethality"] = "stock"
    return v


HU_GUNS = {
    'ak47wi': {
        'player': {'Weight': '3.62', 'MagazineCapacity': '30', 'MagazineWeight': '0.58', 'MaxRange': '450', 'VelocityCoefficient0': '715.1', 'VelocityCoefficient1': '-0.785', 'VelocityCoefficient2': '-0.000304', 'KillCoefficient1': '0.640618', 'KillCoefficient2': '0.006829', 'Recoil': '39.5', 'RunStandAccuracy': '261.29', 'RunCrouchAccuracy': '361.42', 'RunProneAccuracy': '2683.25', 'WalkStandAccuracy': '51.39', 'WalkCrouchAccuracy': '68.13', 'WalkProneAccuracy': '2683.25', 'ShuffleStandAccuracy': '14.80', 'ShuffleCrouchAccuracy': '19.53', 'ShuffleProneAccuracy': '2683.25', 'StationaryStandAccuracy': '5.81', 'StationaryCrouchAccuracy': '2.68', 'StationaryProneAccuracy': '1.25', 'TurnBandVelocity1': '1.59', 'TurnBandMultiplier1': '3.10', 'TurnBandVelocity2': '2.85', 'TurnBandMultiplier2': '4.78', 'TurnBandVelocity3': '4.54', 'TurnBandMultiplier3': '7.02', 'TurnBandVelocity4': '6.68', 'TurnBandMultiplier4': '9.86', 'StabilizationTime': '0.23'},
        'ai': {'Weight': '3.62', 'MagazineCapacity': '30', 'MagazineWeight': '0.58', 'MaxRange': '450', 'VelocityCoefficient0': '715.1', 'VelocityCoefficient1': '-0.785', 'VelocityCoefficient2': '-0.000304', 'KillCoefficient1': '0.640618', 'KillCoefficient2': '0.006829', 'Recoil': '39.5', 'RunStandAccuracy': '2612.9', 'RunCrouchAccuracy': '3614.2', 'RunProneAccuracy': '26832.5', 'WalkStandAccuracy': '513.9', 'WalkCrouchAccuracy': '681.3', 'WalkProneAccuracy': '26832.5', 'ShuffleStandAccuracy': '148.0', 'ShuffleCrouchAccuracy': '195.3', 'ShuffleProneAccuracy': '26832.5', 'StationaryStandAccuracy': '58.1', 'StationaryCrouchAccuracy': '26.8', 'StationaryProneAccuracy': '12.5', 'TurnBandVelocity1': '1.59', 'TurnBandMultiplier1': '3.10', 'TurnBandVelocity2': '2.85', 'TurnBandMultiplier2': '4.78', 'TurnBandVelocity3': '4.54', 'TurnBandMultiplier3': '7.02', 'TurnBandVelocity4': '6.68', 'TurnBandMultiplier4': '9.86', 'StabilizationTime': '0.23'},
    },
    'ak74i30': {
        'player': {'Weight': '3.40', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '500', 'VelocityCoefficient0': '900.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.000749', 'KillCoefficient1': '0.347461', 'KillCoefficient2': '0.002957', 'Recoil': '21.0', 'RunStandAccuracy': '279.11', 'RunCrouchAccuracy': '386.45', 'RunProneAccuracy': '2695.48', 'WalkStandAccuracy': '54.18', 'WalkCrouchAccuracy': '72.02', 'WalkProneAccuracy': '2695.48', 'ShuffleStandAccuracy': '15.24', 'ShuffleCrouchAccuracy': '20.20', 'ShuffleProneAccuracy': '2695.48', 'StationaryStandAccuracy': '5.80', 'StationaryCrouchAccuracy': '2.64', 'StationaryProneAccuracy': '1.19', 'TurnBandVelocity1': '1.56', 'TurnBandMultiplier1': '3.20', 'TurnBandVelocity2': '2.81', 'TurnBandMultiplier2': '4.96', 'TurnBandVelocity3': '4.48', 'TurnBandMultiplier3': '7.31', 'TurnBandVelocity4': '6.60', 'TurnBandMultiplier4': '10.29', 'StabilizationTime': '0.24'},
        'ai': {'Weight': '3.40', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '500', 'VelocityCoefficient0': '900.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.000749', 'KillCoefficient1': '0.347461', 'KillCoefficient2': '0.002957', 'Recoil': '21.0', 'RunStandAccuracy': '2791.1', 'RunCrouchAccuracy': '3864.5', 'RunProneAccuracy': '26954.8', 'WalkStandAccuracy': '541.8', 'WalkCrouchAccuracy': '720.2', 'WalkProneAccuracy': '26954.8', 'ShuffleStandAccuracy': '152.4', 'ShuffleCrouchAccuracy': '202.0', 'ShuffleProneAccuracy': '26954.8', 'StationaryStandAccuracy': '58.0', 'StationaryCrouchAccuracy': '26.4', 'StationaryProneAccuracy': '11.9', 'TurnBandVelocity1': '1.56', 'TurnBandMultiplier1': '3.20', 'TurnBandVelocity2': '2.81', 'TurnBandMultiplier2': '4.96', 'TurnBandVelocity3': '4.48', 'TurnBandMultiplier3': '7.31', 'TurnBandVelocity4': '6.60', 'TurnBandMultiplier4': '10.29', 'StabilizationTime': '0.24'},
    },
    'ak74i30_gp25': {
        'player': {'Weight': '4.90', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '500', 'VelocityCoefficient0': '900.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.000749', 'KillCoefficient1': '0.347461', 'KillCoefficient2': '0.002957', 'Recoil': '19.0', 'RunStandAccuracy': '345.64', 'RunCrouchAccuracy': '479.74', 'RunProneAccuracy': '2740.57', 'WalkStandAccuracy': '64.81', 'WalkCrouchAccuracy': '86.73', 'WalkProneAccuracy': '2740.57', 'ShuffleStandAccuracy': '17.13', 'ShuffleCrouchAccuracy': '22.96', 'ShuffleProneAccuracy': '2740.57', 'StationaryStandAccuracy': '5.99', 'StationaryCrouchAccuracy': '2.71', 'StationaryProneAccuracy': '1.20', 'TurnBandVelocity1': '1.40', 'TurnBandMultiplier1': '3.29', 'TurnBandVelocity2': '2.58', 'TurnBandMultiplier2': '5.23', 'TurnBandVelocity3': '4.18', 'TurnBandMultiplier3': '7.86', 'TurnBandVelocity4': '6.23', 'TurnBandMultiplier4': '11.20', 'StabilizationTime': '0.26'},
        'ai': {'Weight': '4.90', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '500', 'VelocityCoefficient0': '900.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.000749', 'KillCoefficient1': '0.347461', 'KillCoefficient2': '0.002957', 'Recoil': '19.0', 'RunStandAccuracy': '3456.4', 'RunCrouchAccuracy': '4797.4', 'RunProneAccuracy': '27405.7', 'WalkStandAccuracy': '648.1', 'WalkCrouchAccuracy': '867.3', 'WalkProneAccuracy': '27405.7', 'ShuffleStandAccuracy': '171.3', 'ShuffleCrouchAccuracy': '229.6', 'ShuffleProneAccuracy': '27405.7', 'StationaryStandAccuracy': '59.9', 'StationaryCrouchAccuracy': '27.1', 'StationaryProneAccuracy': '12.0', 'TurnBandVelocity1': '1.40', 'TurnBandMultiplier1': '3.29', 'TurnBandVelocity2': '2.58', 'TurnBandMultiplier2': '5.23', 'TurnBandVelocity3': '4.18', 'TurnBandMultiplier3': '7.86', 'TurnBandVelocity4': '6.23', 'TurnBandMultiplier4': '11.20', 'StabilizationTime': '0.26'},
    },
    'aks74uw30': {
        'player': {'Weight': '2.71', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '300', 'VelocityCoefficient0': '734.9', 'VelocityCoefficient1': '-0.902', 'VelocityCoefficient2': '0.001251', 'KillCoefficient1': '0.283687', 'KillCoefficient2': '0.003006', 'Recoil': '20.5', 'RunStandAccuracy': '130.89', 'RunCrouchAccuracy': '178.21', 'RunProneAccuracy': '2592.00', 'WalkStandAccuracy': '31.33', 'WalkCrouchAccuracy': '40.05', 'WalkProneAccuracy': '2592.00', 'ShuffleStandAccuracy': '11.92', 'ShuffleCrouchAccuracy': '14.98', 'ShuffleProneAccuracy': '2592.00', 'StationaryStandAccuracy': '6.24', 'StationaryCrouchAccuracy': '3.33', 'StationaryProneAccuracy': '1.98', 'TurnBandVelocity1': '2.06', 'TurnBandMultiplier1': '2.25', 'TurnBandVelocity2': '3.49', 'TurnBandMultiplier2': '3.30', 'TurnBandVelocity3': '5.36', 'TurnBandMultiplier3': '4.66', 'TurnBandVelocity4': '7.67', 'TurnBandMultiplier4': '6.35', 'StabilizationTime': '0.20'},
        'ai': {'Weight': '2.71', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '300', 'VelocityCoefficient0': '734.9', 'VelocityCoefficient1': '-0.902', 'VelocityCoefficient2': '0.001251', 'KillCoefficient1': '0.283687', 'KillCoefficient2': '0.003006', 'Recoil': '20.5', 'RunStandAccuracy': '1308.9', 'RunCrouchAccuracy': '1782.1', 'RunProneAccuracy': '25920.0', 'WalkStandAccuracy': '313.3', 'WalkCrouchAccuracy': '400.5', 'WalkProneAccuracy': '25920.0', 'ShuffleStandAccuracy': '119.2', 'ShuffleCrouchAccuracy': '149.8', 'ShuffleProneAccuracy': '25920.0', 'StationaryStandAccuracy': '62.4', 'StationaryCrouchAccuracy': '33.3', 'StationaryProneAccuracy': '19.8', 'TurnBandVelocity1': '2.06', 'TurnBandMultiplier1': '2.25', 'TurnBandVelocity2': '3.49', 'TurnBandMultiplier2': '3.30', 'TurnBandVelocity3': '5.36', 'TurnBandMultiplier3': '4.66', 'TurnBandVelocity4': '7.67', 'TurnBandMultiplier4': '6.35', 'StabilizationTime': '0.20'},
    },
    'an94': {
        'player': {'Weight': '4.15', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '400', 'VelocityCoefficient0': '880.0', 'VelocityCoefficient1': '-0.811', 'VelocityCoefficient2': '-0.000538', 'KillCoefficient1': '0.448654', 'KillCoefficient2': '0.003907', 'Recoil': '20.8', 'RunStandAccuracy': '308.91', 'RunCrouchAccuracy': '428.21', 'RunProneAccuracy': '2715.75', 'WalkStandAccuracy': '58.98', 'WalkCrouchAccuracy': '78.65', 'WalkProneAccuracy': '2715.75', 'ShuffleStandAccuracy': '16.13', 'ShuffleCrouchAccuracy': '21.48', 'ShuffleProneAccuracy': '2715.75', 'StationaryStandAccuracy': '5.93', 'StationaryCrouchAccuracy': '2.71', 'StationaryProneAccuracy': '1.24', 'TurnBandVelocity1': '1.47', 'TurnBandMultiplier1': '3.19', 'TurnBandVelocity2': '2.68', 'TurnBandMultiplier2': '5.01', 'TurnBandVelocity3': '4.31', 'TurnBandMultiplier3': '7.47', 'TurnBandVelocity4': '6.39', 'TurnBandMultiplier4': '10.59', 'StabilizationTime': '0.25'},
        'ai': {'Weight': '4.15', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '400', 'VelocityCoefficient0': '880.0', 'VelocityCoefficient1': '-0.811', 'VelocityCoefficient2': '-0.000538', 'KillCoefficient1': '0.448654', 'KillCoefficient2': '0.003907', 'Recoil': '20.8', 'RunStandAccuracy': '3089.1', 'RunCrouchAccuracy': '4282.1', 'RunProneAccuracy': '27157.5', 'WalkStandAccuracy': '589.8', 'WalkCrouchAccuracy': '786.5', 'WalkProneAccuracy': '27157.5', 'ShuffleStandAccuracy': '161.3', 'ShuffleCrouchAccuracy': '214.8', 'ShuffleProneAccuracy': '27157.5', 'StationaryStandAccuracy': '59.3', 'StationaryCrouchAccuracy': '27.1', 'StationaryProneAccuracy': '12.4', 'TurnBandVelocity1': '1.47', 'TurnBandMultiplier1': '3.19', 'TurnBandVelocity2': '2.68', 'TurnBandMultiplier2': '5.01', 'TurnBandVelocity3': '4.31', 'TurnBandMultiplier3': '7.47', 'TurnBandVelocity4': '6.39', 'TurnBandMultiplier4': '10.59', 'StabilizationTime': '0.25'},
    },
    'an94_gp25': {
        'player': {'Weight': '5.65', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '400', 'VelocityCoefficient0': '880.0', 'VelocityCoefficient1': '-0.811', 'VelocityCoefficient2': '-0.000538', 'KillCoefficient1': '0.448654', 'KillCoefficient2': '0.003907', 'Recoil': '19.3', 'RunStandAccuracy': '374.25', 'RunCrouchAccuracy': '519.84', 'RunProneAccuracy': '2759.72', 'WalkStandAccuracy': '69.43', 'WalkCrouchAccuracy': '93.10', 'WalkProneAccuracy': '2759.72', 'ShuffleStandAccuracy': '17.99', 'ShuffleCrouchAccuracy': '24.19', 'ShuffleProneAccuracy': '2759.72', 'StationaryStandAccuracy': '6.12', 'StationaryCrouchAccuracy': '2.78', 'StationaryProneAccuracy': '1.24', 'TurnBandVelocity1': '1.33', 'TurnBandMultiplier1': '3.27', 'TurnBandVelocity2': '2.48', 'TurnBandMultiplier2': '5.26', 'TurnBandVelocity3': '4.06', 'TurnBandMultiplier3': '7.97', 'TurnBandVelocity4': '6.08', 'TurnBandMultiplier4': '11.44', 'StabilizationTime': '0.26'},
        'ai': {'Weight': '5.65', 'MagazineCapacity': '30', 'MagazineWeight': '0.33', 'MaxRange': '400', 'VelocityCoefficient0': '880.0', 'VelocityCoefficient1': '-0.811', 'VelocityCoefficient2': '-0.000538', 'KillCoefficient1': '0.448654', 'KillCoefficient2': '0.003907', 'Recoil': '19.3', 'RunStandAccuracy': '3742.5', 'RunCrouchAccuracy': '5198.4', 'RunProneAccuracy': '27597.2', 'WalkStandAccuracy': '694.3', 'WalkCrouchAccuracy': '931.0', 'WalkProneAccuracy': '27597.2', 'ShuffleStandAccuracy': '179.9', 'ShuffleCrouchAccuracy': '241.9', 'ShuffleProneAccuracy': '27597.2', 'StationaryStandAccuracy': '61.2', 'StationaryCrouchAccuracy': '27.8', 'StationaryProneAccuracy': '12.4', 'TurnBandVelocity1': '1.33', 'TurnBandMultiplier1': '3.27', 'TurnBandVelocity2': '2.48', 'TurnBandMultiplier2': '5.26', 'TurnBandVelocity3': '4.06', 'TurnBandMultiplier3': '7.97', 'TurnBandVelocity4': '6.08', 'TurnBandMultiplier4': '11.44', 'StabilizationTime': '0.26'},
    },
    'at4': {
        'player': {'Weight': '6.70', 'MagazineCapacity': '1', 'MagazineWeight': '1.80', 'MaxRange': '300', 'Recoil': '256.9', 'RunStandAccuracy': '329.68', 'RunCrouchAccuracy': '456.23', 'RunProneAccuracy': '2729.27', 'WalkStandAccuracy': '64.67', 'WalkCrouchAccuracy': '85.56', 'WalkProneAccuracy': '2729.27', 'ShuffleStandAccuracy': '19.24', 'ShuffleCrouchAccuracy': '24.95', 'ShuffleProneAccuracy': '2729.27', 'StationaryStandAccuracy': '8.46', 'StationaryCrouchAccuracy': '5.10', 'StationaryProneAccuracy': '3.49', 'TurnBandVelocity1': '1.09', 'TurnBandMultiplier1': '1.98', 'TurnBandVelocity2': '2.14', 'TurnBandMultiplier2': '3.33', 'TurnBandVelocity3': '3.60', 'TurnBandMultiplier3': '5.22', 'TurnBandVelocity4': '5.49', 'TurnBandMultiplier4': '7.68', 'StabilizationTime': '0.30'},
        'ai': {'Weight': '6.70', 'MagazineCapacity': '1', 'MagazineWeight': '1.80', 'MaxRange': '300', 'Recoil': '256.9', 'RunStandAccuracy': '3296.8', 'RunCrouchAccuracy': '4562.3', 'RunProneAccuracy': '27292.7', 'WalkStandAccuracy': '646.7', 'WalkCrouchAccuracy': '855.6', 'WalkProneAccuracy': '27292.7', 'ShuffleStandAccuracy': '192.4', 'ShuffleCrouchAccuracy': '249.5', 'ShuffleProneAccuracy': '27292.7', 'StationaryStandAccuracy': '84.6', 'StationaryCrouchAccuracy': '51.0', 'StationaryProneAccuracy': '34.9', 'TurnBandVelocity1': '1.09', 'TurnBandMultiplier1': '1.98', 'TurnBandVelocity2': '2.14', 'TurnBandMultiplier2': '3.33', 'TurnBandVelocity3': '3.60', 'TurnBandMultiplier3': '5.22', 'TurnBandVelocity4': '5.49', 'TurnBandMultiplier4': '7.68', 'StabilizationTime': '0.30'},
    },
    'bizon9x18': {
        'player': {'Weight': '2.80', 'MagazineCapacity': '64', 'MagazineWeight': '1.20', 'MaxRange': '200', 'VelocityCoefficient0': '339.9', 'VelocityCoefficient1': '-0.931', 'VelocityCoefficient2': '0.009145', 'KillCoefficient1': '0.293951', 'KillCoefficient2': '0.006766', 'Recoil': '14.0', 'RunStandAccuracy': '127.83', 'RunCrouchAccuracy': '173.73', 'RunProneAccuracy': '2589.73', 'WalkStandAccuracy': '31.22', 'WalkCrouchAccuracy': '39.75', 'WalkProneAccuracy': '2589.73', 'ShuffleStandAccuracy': '12.24', 'ShuffleCrouchAccuracy': '15.28', 'ShuffleProneAccuracy': '2589.73', 'StationaryStandAccuracy': '6.63', 'StationaryCrouchAccuracy': '3.71', 'StationaryProneAccuracy': '2.34', 'TurnBandVelocity1': '2.00', 'TurnBandMultiplier1': '2.07', 'TurnBandVelocity2': '3.41', 'TurnBandMultiplier2': '3.05', 'TurnBandVelocity3': '5.26', 'TurnBandMultiplier3': '4.33', 'TurnBandVelocity4': '7.55', 'TurnBandMultiplier4': '5.91', 'StabilizationTime': '0.20'},
        'ai': {'Weight': '2.80', 'MagazineCapacity': '64', 'MagazineWeight': '1.20', 'MaxRange': '200', 'VelocityCoefficient0': '339.9', 'VelocityCoefficient1': '-0.931', 'VelocityCoefficient2': '0.009145', 'KillCoefficient1': '0.293951', 'KillCoefficient2': '0.006766', 'Recoil': '14.0', 'RunStandAccuracy': '1278.3', 'RunCrouchAccuracy': '1737.3', 'RunProneAccuracy': '25897.3', 'WalkStandAccuracy': '312.2', 'WalkCrouchAccuracy': '397.5', 'WalkProneAccuracy': '25897.3', 'ShuffleStandAccuracy': '122.4', 'ShuffleCrouchAccuracy': '152.8', 'ShuffleProneAccuracy': '25897.3', 'StationaryStandAccuracy': '66.3', 'StationaryCrouchAccuracy': '37.1', 'StationaryProneAccuracy': '23.4', 'TurnBandVelocity1': '2.00', 'TurnBandMultiplier1': '2.07', 'TurnBandVelocity2': '3.41', 'TurnBandMultiplier2': '3.05', 'TurnBandVelocity3': '5.26', 'TurnBandMultiplier3': '4.33', 'TurnBandVelocity4': '7.55', 'TurnBandMultiplier4': '5.91', 'StabilizationTime': '0.20'},
    },
    'dpm': {
        'player': {'Weight': '9.12', 'MagazineCapacity': '47', 'MagazineWeight': '2.90', 'MaxRange': '800', 'VelocityCoefficient0': '839.7', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001340', 'KillCoefficient1': '0.905210', 'KillCoefficient2': '0.008344', 'Recoil': '38.8', 'RunStandAccuracy': '1550.13', 'RunCrouchAccuracy': '2169.01', 'RunProneAccuracy': '3456.72', 'WalkStandAccuracy': '256.92', 'WalkCrouchAccuracy': '352.76', 'WalkProneAccuracy': '3456.72', 'ShuffleStandAccuracy': '50.91', 'ShuffleCrouchAccuracy': '72.43', 'ShuffleProneAccuracy': '3456.72', 'StationaryStandAccuracy': '9.09', 'StationaryCrouchAccuracy': '3.47', 'StationaryProneAccuracy': '0.92', 'TurnBandVelocity1': '0.77', 'TurnBandMultiplier1': '5.09', 'TurnBandVelocity2': '1.64', 'TurnBandMultiplier2': '9.43', 'TurnBandVelocity3': '2.92', 'TurnBandMultiplier3': '15.79', 'TurnBandVelocity4': '4.63', 'TurnBandMultiplier4': '24.27', 'StabilizationTime': '0.39'},
        'ai': {'Weight': '9.12', 'MagazineCapacity': '47', 'MagazineWeight': '2.90', 'MaxRange': '800', 'VelocityCoefficient0': '839.7', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001340', 'KillCoefficient1': '0.905210', 'KillCoefficient2': '0.008344', 'Recoil': '38.8', 'RunStandAccuracy': '15501.3', 'RunCrouchAccuracy': '21690.1', 'RunProneAccuracy': '34567.2', 'WalkStandAccuracy': '2569.2', 'WalkCrouchAccuracy': '3527.6', 'WalkProneAccuracy': '34567.2', 'ShuffleStandAccuracy': '509.1', 'ShuffleCrouchAccuracy': '724.3', 'ShuffleProneAccuracy': '34567.2', 'StationaryStandAccuracy': '90.9', 'StationaryCrouchAccuracy': '34.7', 'StationaryProneAccuracy': '9.2', 'TurnBandVelocity1': '0.77', 'TurnBandMultiplier1': '5.09', 'TurnBandVelocity2': '1.64', 'TurnBandMultiplier2': '9.43', 'TurnBandVelocity3': '2.92', 'TurnBandMultiplier3': '15.79', 'TurnBandVelocity4': '4.63', 'TurnBandMultiplier4': '24.27', 'StabilizationTime': '0.39'},
    },
    'dragunov': {
        'player': {'Weight': '4.50', 'MagazineCapacity': '10', 'MagazineWeight': '0.36', 'MaxRange': '1300', 'VelocityCoefficient0': '830.0', 'VelocityCoefficient1': '-0.871', 'VelocityCoefficient2': '0.001561', 'KillCoefficient1': '0.912832', 'KillCoefficient2': '0.008522', 'Recoil': '57.2', 'RunStandAccuracy': '737.88', 'RunCrouchAccuracy': '1030.02', 'RunProneAccuracy': '2992.74', 'WalkStandAccuracy': '126.99', 'WalkCrouchAccuracy': '172.99', 'WalkProneAccuracy': '2992.74', 'ShuffleStandAccuracy': '27.72', 'ShuffleCrouchAccuracy': '38.65', 'ShuffleProneAccuracy': '2992.74', 'StationaryStandAccuracy': '6.60', 'StationaryCrouchAccuracy': '2.57', 'StationaryProneAccuracy': '0.74', 'TurnBandVelocity1': '1.12', 'TurnBandMultiplier1': '4.84', 'TurnBandVelocity2': '2.18', 'TurnBandMultiplier2': '8.10', 'TurnBandVelocity3': '3.66', 'TurnBandMultiplier3': '12.65', 'TurnBandVelocity4': '5.57', 'TurnBandMultiplier4': '18.54', 'StabilizationTime': '0.30'},
        'ai': {'Weight': '4.50', 'MagazineCapacity': '10', 'MagazineWeight': '0.36', 'MaxRange': '1300', 'VelocityCoefficient0': '830.0', 'VelocityCoefficient1': '-0.871', 'VelocityCoefficient2': '0.001561', 'KillCoefficient1': '0.912832', 'KillCoefficient2': '0.008522', 'Recoil': '57.2', 'RunStandAccuracy': '7378.8', 'RunCrouchAccuracy': '10300.2', 'RunProneAccuracy': '29927.4', 'WalkStandAccuracy': '1269.9', 'WalkCrouchAccuracy': '1729.9', 'WalkProneAccuracy': '29927.4', 'ShuffleStandAccuracy': '277.2', 'ShuffleCrouchAccuracy': '386.5', 'ShuffleProneAccuracy': '29927.4', 'StationaryStandAccuracy': '66.0', 'StationaryCrouchAccuracy': '25.7', 'StationaryProneAccuracy': '7.4', 'TurnBandVelocity1': '1.12', 'TurnBandMultiplier1': '4.84', 'TurnBandVelocity2': '2.18', 'TurnBandMultiplier2': '8.10', 'TurnBandVelocity3': '3.66', 'TurnBandMultiplier3': '12.65', 'TurnBandVelocity4': '5.57', 'TurnBandMultiplier4': '18.54', 'StabilizationTime': '0.30'},
    },
    'fal5000i': {
        'player': {'Weight': '4.25', 'MagazineCapacity': '20', 'MagazineWeight': '0.74', 'MaxRange': '800', 'VelocityCoefficient0': '840.0', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000513', 'KillCoefficient1': '0.899421', 'KillCoefficient2': '0.008248', 'Recoil': '56.2', 'RunStandAccuracy': '511.96', 'RunCrouchAccuracy': '713.11', 'RunProneAccuracy': '2850.23', 'WalkStandAccuracy': '91.10', 'WalkCrouchAccuracy': '123.24', 'WalkProneAccuracy': '2850.23', 'ShuffleStandAccuracy': '21.54', 'ShuffleCrouchAccuracy': '29.53', 'ShuffleProneAccuracy': '2850.23', 'StationaryStandAccuracy': '6.17', 'StationaryCrouchAccuracy': '2.57', 'StationaryProneAccuracy': '0.94', 'TurnBandVelocity1': '1.24', 'TurnBandMultiplier1': '3.99', 'TurnBandVelocity2': '2.35', 'TurnBandMultiplier2': '6.51', 'TurnBandVelocity3': '3.88', 'TurnBandMultiplier3': '9.99', 'TurnBandVelocity4': '5.86', 'TurnBandMultiplier4': '14.46', 'StabilizationTime': '0.28'},
        'ai': {'Weight': '4.25', 'MagazineCapacity': '20', 'MagazineWeight': '0.74', 'MaxRange': '800', 'VelocityCoefficient0': '840.0', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000513', 'KillCoefficient1': '0.899421', 'KillCoefficient2': '0.008248', 'Recoil': '56.2', 'RunStandAccuracy': '5119.6', 'RunCrouchAccuracy': '7131.1', 'RunProneAccuracy': '28502.3', 'WalkStandAccuracy': '911.0', 'WalkCrouchAccuracy': '1232.4', 'WalkProneAccuracy': '28502.3', 'ShuffleStandAccuracy': '215.4', 'ShuffleCrouchAccuracy': '295.3', 'ShuffleProneAccuracy': '28502.3', 'StationaryStandAccuracy': '61.7', 'StationaryCrouchAccuracy': '25.7', 'StationaryProneAccuracy': '9.4', 'TurnBandVelocity1': '1.24', 'TurnBandMultiplier1': '3.99', 'TurnBandVelocity2': '2.35', 'TurnBandMultiplier2': '6.51', 'TurnBandVelocity3': '3.88', 'TurnBandMultiplier3': '9.99', 'TurnBandVelocity4': '5.86', 'TurnBandMultiplier4': '14.46', 'StabilizationTime': '0.28'},
    },
    'g36k': {
        'player': {'Weight': '4.07', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '850.1', 'VelocityCoefficient1': '-0.805', 'VelocityCoefficient2': '-0.000555', 'KillCoefficient1': '0.390081', 'KillCoefficient2': '0.003512', 'Recoil': '23.4', 'RunStandAccuracy': '255.97', 'RunCrouchAccuracy': '353.93', 'RunProneAccuracy': '2679.58', 'WalkStandAccuracy': '50.62', 'WalkCrouchAccuracy': '67.03', 'WalkProneAccuracy': '2679.58', 'ShuffleStandAccuracy': '14.73', 'ShuffleCrouchAccuracy': '19.39', 'ShuffleProneAccuracy': '2679.58', 'StationaryStandAccuracy': '5.87', 'StationaryCrouchAccuracy': '2.76', 'StationaryProneAccuracy': '1.32', 'TurnBandVelocity1': '1.58', 'TurnBandMultiplier1': '3.00', 'TurnBandVelocity2': '2.84', 'TurnBandMultiplier2': '4.63', 'TurnBandVelocity3': '4.53', 'TurnBandMultiplier3': '6.82', 'TurnBandVelocity4': '6.66', 'TurnBandMultiplier4': '9.58', 'StabilizationTime': '0.23'},
        'ai': {'Weight': '4.07', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '850.1', 'VelocityCoefficient1': '-0.805', 'VelocityCoefficient2': '-0.000555', 'KillCoefficient1': '0.390081', 'KillCoefficient2': '0.003512', 'Recoil': '23.4', 'RunStandAccuracy': '2559.7', 'RunCrouchAccuracy': '3539.3', 'RunProneAccuracy': '26795.8', 'WalkStandAccuracy': '506.2', 'WalkCrouchAccuracy': '670.3', 'WalkProneAccuracy': '26795.8', 'ShuffleStandAccuracy': '147.3', 'ShuffleCrouchAccuracy': '193.9', 'ShuffleProneAccuracy': '26795.8', 'StationaryStandAccuracy': '58.7', 'StationaryCrouchAccuracy': '27.6', 'StationaryProneAccuracy': '13.2', 'TurnBandVelocity1': '1.58', 'TurnBandMultiplier1': '3.00', 'TurnBandVelocity2': '2.84', 'TurnBandMultiplier2': '4.63', 'TurnBandVelocity3': '4.53', 'TurnBandMultiplier3': '6.82', 'TurnBandVelocity4': '6.66', 'TurnBandMultiplier4': '9.58', 'StabilizationTime': '0.23'},
    },
    'g3a3': {
        'player': {'Weight': '4.40', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '800.1', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000707', 'KillCoefficient1': '0.856669', 'KillCoefficient2': '0.008248', 'Recoil': '52.5', 'RunStandAccuracy': '452.23', 'RunCrouchAccuracy': '629.33', 'RunProneAccuracy': '2811.35', 'WalkStandAccuracy': '81.61', 'WalkCrouchAccuracy': '110.07', 'WalkProneAccuracy': '2811.35', 'ShuffleStandAccuracy': '19.90', 'ShuffleCrouchAccuracy': '27.11', 'ShuffleProneAccuracy': '2811.35', 'StationaryStandAccuracy': '6.05', 'StationaryCrouchAccuracy': '2.57', 'StationaryProneAccuracy': '0.98', 'TurnBandVelocity1': '1.30', 'TurnBandMultiplier1': '3.81', 'TurnBandVelocity2': '2.44', 'TurnBandMultiplier2': '6.16', 'TurnBandVelocity3': '4.00', 'TurnBandMultiplier3': '9.37', 'TurnBandVelocity4': '6.00', 'TurnBandMultiplier4': '13.49', 'StabilizationTime': '0.27'},
        'ai': {'Weight': '4.40', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '800.1', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000707', 'KillCoefficient1': '0.856669', 'KillCoefficient2': '0.008248', 'Recoil': '52.5', 'RunStandAccuracy': '4522.3', 'RunCrouchAccuracy': '6293.3', 'RunProneAccuracy': '28113.5', 'WalkStandAccuracy': '816.1', 'WalkCrouchAccuracy': '1100.7', 'WalkProneAccuracy': '28113.5', 'ShuffleStandAccuracy': '199.0', 'ShuffleCrouchAccuracy': '271.1', 'ShuffleProneAccuracy': '28113.5', 'StationaryStandAccuracy': '60.5', 'StationaryCrouchAccuracy': '25.7', 'StationaryProneAccuracy': '9.8', 'TurnBandVelocity1': '1.30', 'TurnBandMultiplier1': '3.81', 'TurnBandVelocity2': '2.44', 'TurnBandMultiplier2': '6.16', 'TurnBandVelocity3': '4.00', 'TurnBandMultiplier3': '9.37', 'TurnBandVelocity4': '6.00', 'TurnBandMultiplier4': '13.49', 'StabilizationTime': '0.27'},
    },
    'gp25_ak74i30': {
        'player': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '189.8', 'RunStandAccuracy': '150.62', 'RunCrouchAccuracy': '202.91', 'RunProneAccuracy': '2604.49', 'WalkStandAccuracy': '40.77', 'WalkCrouchAccuracy': '50.57', 'WalkProneAccuracy': '2604.49', 'ShuffleStandAccuracy': '19.17', 'ShuffleCrouchAccuracy': '22.72', 'ShuffleProneAccuracy': '2604.49', 'StationaryStandAccuracy': '12.87', 'StationaryCrouchAccuracy': '9.63', 'StationaryProneAccuracy': '7.96', 'TurnBandVelocity1': '1.38', 'TurnBandMultiplier1': '1.21', 'TurnBandVelocity2': '2.55', 'TurnBandMultiplier2': '1.92', 'TurnBandVelocity3': '4.14', 'TurnBandMultiplier3': '2.90', 'TurnBandVelocity4': '6.18', 'TurnBandMultiplier4': '4.14', 'StabilizationTime': '0.26'},
        'ai': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '189.8', 'RunStandAccuracy': '1506.2', 'RunCrouchAccuracy': '2029.1', 'RunProneAccuracy': '26044.9', 'WalkStandAccuracy': '407.7', 'WalkCrouchAccuracy': '505.7', 'WalkProneAccuracy': '26044.9', 'ShuffleStandAccuracy': '191.7', 'ShuffleCrouchAccuracy': '227.2', 'ShuffleProneAccuracy': '26044.9', 'StationaryStandAccuracy': '128.7', 'StationaryCrouchAccuracy': '96.3', 'StationaryProneAccuracy': '79.6', 'TurnBandVelocity1': '1.38', 'TurnBandMultiplier1': '1.21', 'TurnBandVelocity2': '2.55', 'TurnBandMultiplier2': '1.92', 'TurnBandVelocity3': '4.14', 'TurnBandMultiplier3': '2.90', 'TurnBandVelocity4': '6.18', 'TurnBandMultiplier4': '4.14', 'StabilizationTime': '0.26'},
    },
    'gp25_an94': {
        'player': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '172.9', 'RunStandAccuracy': '163.48', 'RunCrouchAccuracy': '220.94', 'RunProneAccuracy': '2613.57', 'WalkStandAccuracy': '42.83', 'WalkCrouchAccuracy': '53.42', 'WalkProneAccuracy': '2613.57', 'ShuffleStandAccuracy': '19.53', 'ShuffleCrouchAccuracy': '23.26', 'ShuffleProneAccuracy': '2613.57', 'StationaryStandAccuracy': '12.91', 'StationaryCrouchAccuracy': '9.64', 'StationaryProneAccuracy': '7.96', 'TurnBandVelocity1': '1.31', 'TurnBandMultiplier1': '1.22', 'TurnBandVelocity2': '2.46', 'TurnBandMultiplier2': '1.97', 'TurnBandVelocity3': '4.02', 'TurnBandMultiplier3': '2.99', 'TurnBandVelocity4': '6.03', 'TurnBandMultiplier4': '4.30', 'StabilizationTime': '0.27'},
        'ai': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '172.9', 'RunStandAccuracy': '1634.8', 'RunCrouchAccuracy': '2209.4', 'RunProneAccuracy': '26135.7', 'WalkStandAccuracy': '428.3', 'WalkCrouchAccuracy': '534.2', 'WalkProneAccuracy': '26135.7', 'ShuffleStandAccuracy': '195.3', 'ShuffleCrouchAccuracy': '232.6', 'ShuffleProneAccuracy': '26135.7', 'StationaryStandAccuracy': '129.1', 'StationaryCrouchAccuracy': '96.4', 'StationaryProneAccuracy': '79.6', 'TurnBandVelocity1': '1.31', 'TurnBandMultiplier1': '1.22', 'TurnBandVelocity2': '2.46', 'TurnBandMultiplier2': '1.97', 'TurnBandVelocity3': '4.02', 'TurnBandMultiplier3': '2.99', 'TurnBandVelocity4': '6.03', 'TurnBandMultiplier4': '4.30', 'StabilizationTime': '0.27'},
    },
    'gp25_groza': {
        'player': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '205.8', 'RunStandAccuracy': '93.87', 'RunCrouchAccuracy': '123.32', 'RunProneAccuracy': '2564.03', 'WalkStandAccuracy': '31.70', 'WalkCrouchAccuracy': '38.02', 'WalkProneAccuracy': '2564.03', 'ShuffleStandAccuracy': '17.56', 'ShuffleCrouchAccuracy': '20.37', 'ShuffleProneAccuracy': '2564.03', 'StationaryStandAccuracy': '12.70', 'StationaryCrouchAccuracy': '9.57', 'StationaryProneAccuracy': '7.96', 'TurnBandVelocity1': '1.85', 'TurnBandMultiplier1': '1.12', 'TurnBandVelocity2': '3.22', 'TurnBandMultiplier2': '1.67', 'TurnBandVelocity3': '5.01', 'TurnBandMultiplier3': '2.40', 'TurnBandVelocity4': '7.25', 'TurnBandMultiplier4': '3.30', 'StabilizationTime': '0.21'},
        'ai': {'MagazineCapacity': '1', 'MagazineWeight': '0.25', 'MaxRange': '400', 'Recoil': '205.8', 'RunStandAccuracy': '938.7', 'RunCrouchAccuracy': '1233.2', 'RunProneAccuracy': '25640.3', 'WalkStandAccuracy': '317.0', 'WalkCrouchAccuracy': '380.2', 'WalkProneAccuracy': '25640.3', 'ShuffleStandAccuracy': '175.6', 'ShuffleCrouchAccuracy': '203.7', 'ShuffleProneAccuracy': '25640.3', 'StationaryStandAccuracy': '127.0', 'StationaryCrouchAccuracy': '95.7', 'StationaryProneAccuracy': '79.6', 'TurnBandVelocity1': '1.85', 'TurnBandMultiplier1': '1.12', 'TurnBandVelocity2': '3.22', 'TurnBandMultiplier2': '1.67', 'TurnBandVelocity3': '5.01', 'TurnBandMultiplier3': '2.40', 'TurnBandVelocity4': '7.25', 'TurnBandMultiplier4': '3.30', 'StabilizationTime': '0.21'},
    },
    'groza': {
        'player': {'Weight': '2.93', 'MagazineCapacity': '20', 'MagazineWeight': '0.70', 'MaxRange': '700', 'VelocityCoefficient0': '299.9', 'VelocityCoefficient1': '-0.829', 'VelocityCoefficient2': '0.003000', 'KillCoefficient1': '0.674479', 'KillCoefficient2': '0.017294', 'Recoil': '31.7', 'RunStandAccuracy': '166.03', 'RunCrouchAccuracy': '227.84', 'RunProneAccuracy': '2617.04', 'WalkStandAccuracy': '36.18', 'WalkCrouchAccuracy': '47.08', 'WalkProneAccuracy': '2617.04', 'ShuffleStandAccuracy': '12.11', 'ShuffleCrouchAccuracy': '15.60', 'ShuffleProneAccuracy': '2617.04', 'StationaryStandAccuracy': '5.54', 'StationaryCrouchAccuracy': '2.61', 'StationaryProneAccuracy': '1.26', 'TurnBandVelocity1': '2.03', 'TurnBandMultiplier1': '2.91', 'TurnBandVelocity2': '3.45', 'TurnBandMultiplier2': '4.27', 'TurnBandVelocity3': '5.31', 'TurnBandMultiplier3': '6.04', 'TurnBandVelocity4': '7.61', 'TurnBandMultiplier4': '8.24', 'StabilizationTime': '0.20'},
        'ai': {'Weight': '2.93', 'MagazineCapacity': '20', 'MagazineWeight': '0.70', 'MaxRange': '700', 'VelocityCoefficient0': '299.9', 'VelocityCoefficient1': '-0.829', 'VelocityCoefficient2': '0.003000', 'KillCoefficient1': '0.674479', 'KillCoefficient2': '0.017294', 'Recoil': '31.7', 'RunStandAccuracy': '1660.3', 'RunCrouchAccuracy': '2278.4', 'RunProneAccuracy': '26170.4', 'WalkStandAccuracy': '361.8', 'WalkCrouchAccuracy': '470.8', 'WalkProneAccuracy': '26170.4', 'ShuffleStandAccuracy': '121.1', 'ShuffleCrouchAccuracy': '156.0', 'ShuffleProneAccuracy': '26170.4', 'StationaryStandAccuracy': '55.4', 'StationaryCrouchAccuracy': '26.1', 'StationaryProneAccuracy': '12.6', 'TurnBandVelocity1': '2.03', 'TurnBandMultiplier1': '2.91', 'TurnBandVelocity2': '3.45', 'TurnBandMultiplier2': '4.27', 'TurnBandVelocity3': '5.31', 'TurnBandMultiplier3': '6.04', 'TurnBandVelocity4': '7.61', 'TurnBandMultiplier4': '8.24', 'StabilizationTime': '0.20'},
    },
    'hk4380acp': {
        'player': {'Weight': '0.48', 'MagazineCapacity': '7', 'MagazineWeight': '0.11', 'MaxRange': '100', 'VelocityCoefficient0': '298.7', 'VelocityCoefficient1': '-0.937', 'VelocityCoefficient2': '0.004978', 'KillCoefficient1': '0.206688', 'KillCoefficient2': '0.005417', 'Recoil': '29.6', 'RunStandAccuracy': '29.61', 'RunCrouchAccuracy': '34.81', 'RunProneAccuracy': '2518.28', 'WalkStandAccuracy': '18.05', 'WalkCrouchAccuracy': '20.50', 'WalkProneAccuracy': '2518.28', 'ShuffleStandAccuracy': '12.13', 'ShuffleCrouchAccuracy': '13.98', 'ShuffleProneAccuracy': '2518.28', 'StationaryStandAccuracy': '8.98', 'StationaryCrouchAccuracy': '6.13', 'StationaryProneAccuracy': '4.73', 'TurnBandVelocity1': '6.92', 'TurnBandMultiplier1': '1.17', 'TurnBandVelocity2': '9.55', 'TurnBandMultiplier2': '1.44', 'TurnBandVelocity3': '12.65', 'TurnBandMultiplier3': '1.75', 'TurnBandVelocity4': '16.20', 'TurnBandMultiplier4': '2.11', 'StabilizationTime': '0.09'},
        'ai': {'Weight': '0.48', 'MagazineCapacity': '7', 'MagazineWeight': '0.11', 'MaxRange': '100', 'VelocityCoefficient0': '298.7', 'VelocityCoefficient1': '-0.937', 'VelocityCoefficient2': '0.004978', 'KillCoefficient1': '0.206688', 'KillCoefficient2': '0.005417', 'Recoil': '29.6', 'RunStandAccuracy': '296.1', 'RunCrouchAccuracy': '348.1', 'RunProneAccuracy': '25182.8', 'WalkStandAccuracy': '180.5', 'WalkCrouchAccuracy': '205.0', 'WalkProneAccuracy': '25182.8', 'ShuffleStandAccuracy': '121.3', 'ShuffleCrouchAccuracy': '139.8', 'ShuffleProneAccuracy': '25182.8', 'StationaryStandAccuracy': '89.8', 'StationaryCrouchAccuracy': '61.3', 'StationaryProneAccuracy': '47.3', 'TurnBandVelocity1': '6.92', 'TurnBandMultiplier1': '1.17', 'TurnBandVelocity2': '9.55', 'TurnBandMultiplier2': '1.44', 'TurnBandVelocity3': '12.65', 'TurnBandMultiplier3': '1.75', 'TurnBandVelocity4': '16.20', 'TurnBandMultiplier4': '2.11', 'StabilizationTime': '0.09'},
    },
    'l96a1': {
        'player': {'Weight': '6.80', 'MagazineCapacity': '10', 'MagazineWeight': '0.38', 'MaxRange': '900', 'VelocityCoefficient0': '850.4', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001421', 'KillCoefficient1': '1.083948', 'KillCoefficient2': '0.009873', 'Recoil': '59.1', 'RunStandAccuracy': '936.68', 'RunCrouchAccuracy': '1308.82', 'RunProneAccuracy': '3112.71', 'WalkStandAccuracy': '158.75', 'WalkCrouchAccuracy': '216.95', 'WalkProneAccuracy': '3112.71', 'ShuffleStandAccuracy': '33.36', 'ShuffleCrouchAccuracy': '46.88', 'ShuffleProneAccuracy': '3112.71', 'StationaryStandAccuracy': '7.17', 'StationaryCrouchAccuracy': '2.75', 'StationaryProneAccuracy': '0.75', 'TurnBandVelocity1': '1.01', 'TurnBandMultiplier1': '5.07', 'TurnBandVelocity2': '2.01', 'TurnBandMultiplier2': '8.72', 'TurnBandVelocity3': '3.43', 'TurnBandMultiplier3': '13.89', 'TurnBandVelocity4': '5.28', 'TurnBandMultiplier4': '20.62', 'StabilizationTime': '0.32'},
        'ai': {'Weight': '6.80', 'MagazineCapacity': '10', 'MagazineWeight': '0.38', 'MaxRange': '900', 'VelocityCoefficient0': '850.4', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001421', 'KillCoefficient1': '1.083948', 'KillCoefficient2': '0.009873', 'Recoil': '59.1', 'RunStandAccuracy': '9366.8', 'RunCrouchAccuracy': '13088.2', 'RunProneAccuracy': '31127.1', 'WalkStandAccuracy': '1587.5', 'WalkCrouchAccuracy': '2169.5', 'WalkProneAccuracy': '31127.1', 'ShuffleStandAccuracy': '333.6', 'ShuffleCrouchAccuracy': '468.8', 'ShuffleProneAccuracy': '31127.1', 'StationaryStandAccuracy': '71.7', 'StationaryCrouchAccuracy': '27.5', 'StationaryProneAccuracy': '7.5', 'TurnBandVelocity1': '1.01', 'TurnBandMultiplier1': '5.07', 'TurnBandVelocity2': '2.01', 'TurnBandMultiplier2': '8.72', 'TurnBandVelocity3': '3.43', 'TurnBandMultiplier3': '13.89', 'TurnBandVelocity4': '5.28', 'TurnBandMultiplier4': '20.62', 'StabilizationTime': '0.32'},
    },
    'm16a4rfx': {
        'player': {'Weight': '3.76', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '947.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001193', 'KillCoefficient1': '0.428073', 'KillCoefficient2': '0.003455', 'Recoil': '24.8', 'RunStandAccuracy': '344.44', 'RunCrouchAccuracy': '478.07', 'RunProneAccuracy': '2739.77', 'WalkStandAccuracy': '64.59', 'WalkCrouchAccuracy': '86.44', 'WalkProneAccuracy': '2739.77', 'ShuffleStandAccuracy': '17.07', 'ShuffleCrouchAccuracy': '22.88', 'ShuffleProneAccuracy': '2739.77', 'StationaryStandAccuracy': '5.96', 'StationaryCrouchAccuracy': '2.68', 'StationaryProneAccuracy': '1.17', 'TurnBandVelocity1': '1.41', 'TurnBandMultiplier1': '3.33', 'TurnBandVelocity2': '2.59', 'TurnBandMultiplier2': '5.27', 'TurnBandVelocity3': '4.21', 'TurnBandMultiplier3': '7.91', 'TurnBandVelocity4': '6.26', 'TurnBandMultiplier4': '11.28', 'StabilizationTime': '0.25'},
        'ai': {'Weight': '3.76', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '947.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001193', 'KillCoefficient1': '0.428073', 'KillCoefficient2': '0.003455', 'Recoil': '24.8', 'RunStandAccuracy': '3444.4', 'RunCrouchAccuracy': '4780.7', 'RunProneAccuracy': '27397.7', 'WalkStandAccuracy': '645.9', 'WalkCrouchAccuracy': '864.4', 'WalkProneAccuracy': '27397.7', 'ShuffleStandAccuracy': '170.7', 'ShuffleCrouchAccuracy': '228.8', 'ShuffleProneAccuracy': '27397.7', 'StationaryStandAccuracy': '59.6', 'StationaryCrouchAccuracy': '26.8', 'StationaryProneAccuracy': '11.7', 'TurnBandVelocity1': '1.41', 'TurnBandMultiplier1': '3.33', 'TurnBandVelocity2': '2.59', 'TurnBandMultiplier2': '5.27', 'TurnBandVelocity3': '4.21', 'TurnBandMultiplier3': '7.91', 'TurnBandVelocity4': '6.26', 'TurnBandMultiplier4': '11.28', 'StabilizationTime': '0.25'},
    },
    'm16a4rfx_m203': {
        'player': {'Weight': '5.12', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '947.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001193', 'KillCoefficient1': '0.428073', 'KillCoefficient2': '0.003455', 'Recoil': '22.7', 'RunStandAccuracy': '415.38', 'RunCrouchAccuracy': '577.56', 'RunProneAccuracy': '2787.06', 'WalkStandAccuracy': '75.93', 'WalkCrouchAccuracy': '102.14', 'WalkProneAccuracy': '2787.06', 'ShuffleStandAccuracy': '19.08', 'ShuffleCrouchAccuracy': '25.82', 'ShuffleProneAccuracy': '2787.06', 'StationaryStandAccuracy': '6.17', 'StationaryCrouchAccuracy': '2.75', 'StationaryProneAccuracy': '1.18', 'TurnBandVelocity1': '1.28', 'TurnBandMultiplier1': '3.41', 'TurnBandVelocity2': '2.41', 'TurnBandMultiplier2': '5.53', 'TurnBandVelocity3': '3.97', 'TurnBandMultiplier3': '8.44', 'TurnBandVelocity4': '5.96', 'TurnBandMultiplier4': '12.16', 'StabilizationTime': '0.27'},
        'ai': {'Weight': '5.12', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '947.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001193', 'KillCoefficient1': '0.428073', 'KillCoefficient2': '0.003455', 'Recoil': '22.7', 'RunStandAccuracy': '4153.8', 'RunCrouchAccuracy': '5775.6', 'RunProneAccuracy': '27870.6', 'WalkStandAccuracy': '759.3', 'WalkCrouchAccuracy': '1021.4', 'WalkProneAccuracy': '27870.6', 'ShuffleStandAccuracy': '190.8', 'ShuffleCrouchAccuracy': '258.2', 'ShuffleProneAccuracy': '27870.6', 'StationaryStandAccuracy': '61.7', 'StationaryCrouchAccuracy': '27.5', 'StationaryProneAccuracy': '11.8', 'TurnBandVelocity1': '1.28', 'TurnBandMultiplier1': '3.41', 'TurnBandVelocity2': '2.41', 'TurnBandMultiplier2': '5.53', 'TurnBandVelocity3': '3.97', 'TurnBandMultiplier3': '8.44', 'TurnBandVelocity4': '5.96', 'TurnBandMultiplier4': '12.16', 'StabilizationTime': '0.27'},
    },
    'm1911': {
        'player': {'Weight': '1.11', 'MagazineCapacity': '7', 'MagazineWeight': '0.30', 'MaxRange': '100', 'VelocityCoefficient0': '253.0', 'VelocityCoefficient1': '-0.968', 'VelocityCoefficient2': '0.026853', 'KillCoefficient1': '0.423811', 'KillCoefficient2': '0.013173', 'Recoil': '41.8', 'RunStandAccuracy': '33.00', 'RunCrouchAccuracy': '39.98', 'RunProneAccuracy': '2520.97', 'WalkStandAccuracy': '17.69', 'WalkCrouchAccuracy': '20.37', 'WalkProneAccuracy': '2520.97', 'ShuffleStandAccuracy': '11.28', 'ShuffleCrouchAccuracy': '13.14', 'ShuffleProneAccuracy': '2520.97', 'StationaryStandAccuracy': '8.05', 'StationaryCrouchAccuracy': '5.25', 'StationaryProneAccuracy': '3.88', 'TurnBandVelocity1': '5.58', 'TurnBandMultiplier1': '1.33', 'TurnBandVelocity2': '7.94', 'TurnBandMultiplier2': '1.67', 'TurnBandVelocity3': '10.76', 'TurnBandMultiplier3': '2.08', 'TurnBandVelocity4': '14.04', 'TurnBandMultiplier4': '2.55', 'StabilizationTime': '0.10'},
        'ai': {'Weight': '1.11', 'MagazineCapacity': '7', 'MagazineWeight': '0.30', 'MaxRange': '100', 'VelocityCoefficient0': '253.0', 'VelocityCoefficient1': '-0.968', 'VelocityCoefficient2': '0.026853', 'KillCoefficient1': '0.423811', 'KillCoefficient2': '0.013173', 'Recoil': '41.8', 'RunStandAccuracy': '330.0', 'RunCrouchAccuracy': '399.8', 'RunProneAccuracy': '25209.7', 'WalkStandAccuracy': '176.9', 'WalkCrouchAccuracy': '203.7', 'WalkProneAccuracy': '25209.7', 'ShuffleStandAccuracy': '112.8', 'ShuffleCrouchAccuracy': '131.4', 'ShuffleProneAccuracy': '25209.7', 'StationaryStandAccuracy': '80.5', 'StationaryCrouchAccuracy': '52.5', 'StationaryProneAccuracy': '38.8', 'TurnBandVelocity1': '5.58', 'TurnBandMultiplier1': '1.33', 'TurnBandVelocity2': '7.94', 'TurnBandMultiplier2': '1.67', 'TurnBandVelocity3': '10.76', 'TurnBandMultiplier3': '2.08', 'TurnBandVelocity4': '14.04', 'TurnBandMultiplier4': '2.55', 'StabilizationTime': '0.10'},
    },
    'm203_m16a4rfx': {
        'player': {'MagazineCapacity': '1', 'MagazineWeight': '0.24', 'MaxRange': '400', 'Recoil': '163.6', 'RunStandAccuracy': '210.39', 'RunCrouchAccuracy': '288.19', 'RunProneAccuracy': '2647.16', 'WalkStandAccuracy': '47.20', 'WalkCrouchAccuracy': '60.74', 'WalkProneAccuracy': '2647.16', 'ShuffleStandAccuracy': '17.55', 'ShuffleCrouchAccuracy': '21.76', 'ShuffleProneAccuracy': '2647.16', 'StationaryStandAccuracy': '9.78', 'StationaryCrouchAccuracy': '6.57', 'StationaryProneAccuracy': '5.00', 'TurnBandVelocity1': '1.26', 'TurnBandMultiplier1': '1.57', 'TurnBandVelocity2': '2.39', 'TurnBandMultiplier2': '2.55', 'TurnBandVelocity3': '3.93', 'TurnBandMultiplier3': '3.90', 'TurnBandVelocity4': '5.92', 'TurnBandMultiplier4': '5.63', 'StabilizationTime': '0.27'},
        'ai': {'MagazineCapacity': '1', 'MagazineWeight': '0.24', 'MaxRange': '400', 'Recoil': '163.6', 'RunStandAccuracy': '2103.9', 'RunCrouchAccuracy': '2881.9', 'RunProneAccuracy': '26471.6', 'WalkStandAccuracy': '472.0', 'WalkCrouchAccuracy': '607.4', 'WalkProneAccuracy': '26471.6', 'ShuffleStandAccuracy': '175.5', 'ShuffleCrouchAccuracy': '217.6', 'ShuffleProneAccuracy': '26471.6', 'StationaryStandAccuracy': '97.8', 'StationaryCrouchAccuracy': '65.7', 'StationaryProneAccuracy': '50.0', 'TurnBandVelocity1': '1.26', 'TurnBandMultiplier1': '1.57', 'TurnBandVelocity2': '2.39', 'TurnBandMultiplier2': '2.55', 'TurnBandVelocity3': '3.93', 'TurnBandMultiplier3': '3.90', 'TurnBandVelocity4': '5.92', 'TurnBandMultiplier4': '5.63', 'StabilizationTime': '0.27'},
    },
    'm240b': {
        'player': {'Weight': '10.07', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1800', 'VelocityCoefficient0': '905.3', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000197', 'KillCoefficient1': '0.969259', 'KillCoefficient2': '0.008248', 'Recoil': '41.1', 'RunStandAccuracy': '1635.91', 'RunCrouchAccuracy': '2289.30', 'RunProneAccuracy': '3502.14', 'WalkStandAccuracy': '270.62', 'WalkCrouchAccuracy': '371.73', 'WalkProneAccuracy': '3502.14', 'ShuffleStandAccuracy': '53.34', 'ShuffleCrouchAccuracy': '75.98', 'ShuffleProneAccuracy': '3502.14', 'StationaryStandAccuracy': '9.34', 'StationaryCrouchAccuracy': '3.54', 'StationaryProneAccuracy': '0.92', 'TurnBandVelocity1': '0.75', 'TurnBandMultiplier1': '5.16', 'TurnBandVelocity2': '1.62', 'TurnBandMultiplier2': '9.63', 'TurnBandVelocity3': '2.89', 'TurnBandMultiplier3': '16.18', 'TurnBandVelocity4': '4.59', 'TurnBandMultiplier4': '24.94', 'StabilizationTime': '0.40'},
        'ai': {'Weight': '10.07', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1800', 'VelocityCoefficient0': '905.3', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000197', 'KillCoefficient1': '0.969259', 'KillCoefficient2': '0.008248', 'Recoil': '41.1', 'RunStandAccuracy': '16359.1', 'RunCrouchAccuracy': '22893.0', 'RunProneAccuracy': '35021.4', 'WalkStandAccuracy': '2706.2', 'WalkCrouchAccuracy': '3717.3', 'WalkProneAccuracy': '35021.4', 'ShuffleStandAccuracy': '533.4', 'ShuffleCrouchAccuracy': '759.8', 'ShuffleProneAccuracy': '35021.4', 'StationaryStandAccuracy': '93.4', 'StationaryCrouchAccuracy': '35.4', 'StationaryProneAccuracy': '9.2', 'TurnBandVelocity1': '0.75', 'TurnBandMultiplier1': '5.16', 'TurnBandVelocity2': '1.62', 'TurnBandMultiplier2': '9.63', 'TurnBandVelocity3': '2.89', 'TurnBandMultiplier3': '16.18', 'TurnBandVelocity4': '4.59', 'TurnBandMultiplier4': '24.94', 'StabilizationTime': '0.40'},
    },
    'm249saw': {
        'player': {'Weight': '7.71', 'MagazineCapacity': '200', 'MagazineWeight': '3.60', 'MaxRange': '1100', 'VelocityCoefficient0': '915.0', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000999', 'KillCoefficient1': '0.413208', 'KillCoefficient2': '0.003455', 'Recoil': '19.0', 'RunStandAccuracy': '790.28', 'RunCrouchAccuracy': '1103.31', 'RunProneAccuracy': '3024.73', 'WalkStandAccuracy': '135.79', 'WalkCrouchAccuracy': '185.00', 'WalkProneAccuracy': '3024.73', 'ShuffleStandAccuracy': '29.67', 'ShuffleCrouchAccuracy': '41.29', 'ShuffleProneAccuracy': '3024.73', 'StationaryStandAccuracy': '7.20', 'StationaryCrouchAccuracy': '3.05', 'StationaryProneAccuracy': '1.16', 'TurnBandVelocity1': '0.95', 'TurnBandMultiplier1': '3.86', 'TurnBandVelocity2': '1.93', 'TurnBandMultiplier2': '6.73', 'TurnBandVelocity3': '3.32', 'TurnBandMultiplier3': '10.82', 'TurnBandVelocity4': '5.14', 'TurnBandMultiplier4': '16.18', 'StabilizationTime': '0.33'},
        'ai': {'Weight': '7.71', 'MagazineCapacity': '200', 'MagazineWeight': '3.60', 'MaxRange': '1100', 'VelocityCoefficient0': '915.0', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000999', 'KillCoefficient1': '0.413208', 'KillCoefficient2': '0.003455', 'Recoil': '19.0', 'RunStandAccuracy': '7902.8', 'RunCrouchAccuracy': '11033.1', 'RunProneAccuracy': '30247.3', 'WalkStandAccuracy': '1357.9', 'WalkCrouchAccuracy': '1850.0', 'WalkProneAccuracy': '30247.3', 'ShuffleStandAccuracy': '296.7', 'ShuffleCrouchAccuracy': '412.9', 'ShuffleProneAccuracy': '30247.3', 'StationaryStandAccuracy': '72.0', 'StationaryCrouchAccuracy': '30.5', 'StationaryProneAccuracy': '11.6', 'TurnBandVelocity1': '0.95', 'TurnBandMultiplier1': '3.86', 'TurnBandVelocity2': '1.93', 'TurnBandMultiplier2': '6.73', 'TurnBandVelocity3': '3.32', 'TurnBandMultiplier3': '10.82', 'TurnBandVelocity4': '5.14', 'TurnBandMultiplier4': '16.18', 'StabilizationTime': '0.33'},
    },
    'm24sws': {
        'player': {'Weight': '10.30', 'MagazineCapacity': '5', 'MagazineWeight': '0.20', 'MaxRange': '800', 'VelocityCoefficient0': '853.4', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001409', 'KillCoefficient1': '1.087833', 'KillCoefficient2': '0.009873', 'Recoil': '50.8', 'RunStandAccuracy': '1075.19', 'RunCrouchAccuracy': '1503.04', 'RunProneAccuracy': '3193.62', 'WalkStandAccuracy': '180.91', 'WalkCrouchAccuracy': '247.61', 'WalkProneAccuracy': '3193.62', 'ShuffleStandAccuracy': '37.31', 'ShuffleCrouchAccuracy': '52.64', 'ShuffleProneAccuracy': '3193.62', 'StationaryStandAccuracy': '7.60', 'StationaryCrouchAccuracy': '2.91', 'StationaryProneAccuracy': '0.78', 'TurnBandVelocity1': '0.94', 'TurnBandMultiplier1': '5.11', 'TurnBandVelocity2': '1.91', 'TurnBandMultiplier2': '8.96', 'TurnBandVelocity3': '3.29', 'TurnBandMultiplier3': '14.44', 'TurnBandVelocity4': '5.10', 'TurnBandMultiplier4': '21.65', 'StabilizationTime': '0.34'},
        'ai': {'Weight': '10.30', 'MagazineCapacity': '5', 'MagazineWeight': '0.20', 'MaxRange': '800', 'VelocityCoefficient0': '853.4', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001409', 'KillCoefficient1': '1.087833', 'KillCoefficient2': '0.009873', 'Recoil': '50.8', 'RunStandAccuracy': '10751.9', 'RunCrouchAccuracy': '15030.4', 'RunProneAccuracy': '31936.2', 'WalkStandAccuracy': '1809.1', 'WalkCrouchAccuracy': '2476.1', 'WalkProneAccuracy': '31936.2', 'ShuffleStandAccuracy': '373.1', 'ShuffleCrouchAccuracy': '526.4', 'ShuffleProneAccuracy': '31936.2', 'StationaryStandAccuracy': '76.0', 'StationaryCrouchAccuracy': '29.1', 'StationaryProneAccuracy': '7.8', 'TurnBandVelocity1': '0.94', 'TurnBandMultiplier1': '5.11', 'TurnBandVelocity2': '1.91', 'TurnBandMultiplier2': '8.96', 'TurnBandVelocity3': '3.29', 'TurnBandMultiplier3': '14.44', 'TurnBandVelocity4': '5.10', 'TurnBandMultiplier4': '21.65', 'StabilizationTime': '0.34'},
    },
    'm4a1i': {
        'player': {'Weight': '2.88', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '883.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000816', 'KillCoefficient1': '0.399168', 'KillCoefficient2': '0.003455', 'Recoil': '26.0', 'RunStandAccuracy': '191.69', 'RunCrouchAccuracy': '263.70', 'RunProneAccuracy': '2634.97', 'WalkStandAccuracy': '40.56', 'WalkCrouchAccuracy': '53.03', 'WalkProneAccuracy': '2634.97', 'ShuffleStandAccuracy': '13.13', 'ShuffleCrouchAccuracy': '16.97', 'ShuffleProneAccuracy': '2634.97', 'StationaryStandAccuracy': '5.91', 'StationaryCrouchAccuracy': '2.91', 'StationaryProneAccuracy': '1.52', 'TurnBandVelocity1': '1.78', 'TurnBandMultiplier1': '2.69', 'TurnBandVelocity2': '3.11', 'TurnBandMultiplier2': '4.06', 'TurnBandVelocity3': '4.88', 'TurnBandMultiplier3': '5.86', 'TurnBandVelocity4': '7.08', 'TurnBandMultiplier4': '8.12', 'StabilizationTime': '0.22'},
        'ai': {'Weight': '2.88', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '883.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000816', 'KillCoefficient1': '0.399168', 'KillCoefficient2': '0.003455', 'Recoil': '26.0', 'RunStandAccuracy': '1916.9', 'RunCrouchAccuracy': '2637.0', 'RunProneAccuracy': '26349.7', 'WalkStandAccuracy': '405.6', 'WalkCrouchAccuracy': '530.3', 'WalkProneAccuracy': '26349.7', 'ShuffleStandAccuracy': '131.3', 'ShuffleCrouchAccuracy': '169.7', 'ShuffleProneAccuracy': '26349.7', 'StationaryStandAccuracy': '59.1', 'StationaryCrouchAccuracy': '29.1', 'StationaryProneAccuracy': '15.2', 'TurnBandVelocity1': '1.78', 'TurnBandMultiplier1': '2.69', 'TurnBandVelocity2': '3.11', 'TurnBandMultiplier2': '4.06', 'TurnBandVelocity3': '4.88', 'TurnBandMultiplier3': '5.86', 'TurnBandVelocity4': '7.08', 'TurnBandMultiplier4': '8.12', 'StabilizationTime': '0.22'},
    },
    'm4a1m68': {
        'player': {'Weight': '3.39', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '883.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000816', 'KillCoefficient1': '0.399168', 'KillCoefficient2': '0.003455', 'Recoil': '24.7', 'RunStandAccuracy': '207.19', 'RunCrouchAccuracy': '285.42', 'RunProneAccuracy': '2645.78', 'WalkStandAccuracy': '43.04', 'WalkCrouchAccuracy': '56.45', 'WalkProneAccuracy': '2645.78', 'ShuffleStandAccuracy': '13.57', 'ShuffleCrouchAccuracy': '17.61', 'ShuffleProneAccuracy': '2645.78', 'StationaryStandAccuracy': '5.95', 'StationaryCrouchAccuracy': '2.92', 'StationaryProneAccuracy': '1.52', 'TurnBandVelocity1': '1.70', 'TurnBandMultiplier1': '2.72', 'TurnBandVelocity2': '3.01', 'TurnBandMultiplier2': '4.13', 'TurnBandVelocity3': '4.75', 'TurnBandMultiplier3': '6.01', 'TurnBandVelocity4': '6.92', 'TurnBandMultiplier4': '8.37', 'StabilizationTime': '0.22'},
        'ai': {'Weight': '3.39', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '600', 'VelocityCoefficient0': '883.9', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000816', 'KillCoefficient1': '0.399168', 'KillCoefficient2': '0.003455', 'Recoil': '24.7', 'RunStandAccuracy': '2071.9', 'RunCrouchAccuracy': '2854.2', 'RunProneAccuracy': '26457.8', 'WalkStandAccuracy': '430.4', 'WalkCrouchAccuracy': '564.5', 'WalkProneAccuracy': '26457.8', 'ShuffleStandAccuracy': '135.7', 'ShuffleCrouchAccuracy': '176.1', 'ShuffleProneAccuracy': '26457.8', 'StationaryStandAccuracy': '59.5', 'StationaryCrouchAccuracy': '29.2', 'StationaryProneAccuracy': '15.2', 'TurnBandVelocity1': '1.70', 'TurnBandMultiplier1': '2.72', 'TurnBandVelocity2': '3.01', 'TurnBandMultiplier2': '4.13', 'TurnBandVelocity3': '4.75', 'TurnBandMultiplier3': '6.01', 'TurnBandVelocity4': '6.92', 'TurnBandMultiplier4': '8.37', 'StabilizationTime': '0.22'},
    },
    'm60': {
        'player': {'Weight': '9.90', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1100', 'VelocityCoefficient0': '853.4', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000448', 'KillCoefficient1': '0.913780', 'KillCoefficient2': '0.008248', 'Recoil': '38.9', 'RunStandAccuracy': '1151.32', 'RunCrouchAccuracy': '1609.74', 'RunProneAccuracy': '3237.21', 'WalkStandAccuracy': '193.19', 'WalkCrouchAccuracy': '264.56', 'WalkProneAccuracy': '3237.21', 'ShuffleStandAccuracy': '39.60', 'ShuffleCrouchAccuracy': '55.92', 'ShuffleProneAccuracy': '3237.21', 'StationaryStandAccuracy': '7.94', 'StationaryCrouchAccuracy': '3.10', 'StationaryProneAccuracy': '0.90', 'TurnBandVelocity1': '0.87', 'TurnBandMultiplier1': '4.78', 'TurnBandVelocity2': '1.81', 'TurnBandMultiplier2': '8.56', 'TurnBandVelocity3': '3.15', 'TurnBandMultiplier3': '13.98', 'TurnBandVelocity4': '4.92', 'TurnBandMultiplier4': '21.15', 'StabilizationTime': '0.36'},
        'ai': {'Weight': '9.90', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1100', 'VelocityCoefficient0': '853.4', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000448', 'KillCoefficient1': '0.913780', 'KillCoefficient2': '0.008248', 'Recoil': '38.9', 'RunStandAccuracy': '11513.2', 'RunCrouchAccuracy': '16097.4', 'RunProneAccuracy': '32372.1', 'WalkStandAccuracy': '1931.9', 'WalkCrouchAccuracy': '2645.6', 'WalkProneAccuracy': '32372.1', 'ShuffleStandAccuracy': '396.0', 'ShuffleCrouchAccuracy': '559.2', 'ShuffleProneAccuracy': '32372.1', 'StationaryStandAccuracy': '79.4', 'StationaryCrouchAccuracy': '31.0', 'StationaryProneAccuracy': '9.0', 'TurnBandVelocity1': '0.87', 'TurnBandMultiplier1': '4.78', 'TurnBandVelocity2': '1.81', 'TurnBandMultiplier2': '8.56', 'TurnBandVelocity3': '3.15', 'TurnBandMultiplier3': '13.98', 'TurnBandVelocity4': '4.92', 'TurnBandMultiplier4': '21.15', 'StabilizationTime': '0.36'},
    },
    'm82a1': {
        'player': {'Weight': '14.24', 'MagazineCapacity': '10', 'MagazineWeight': '1.87', 'MaxRange': '1800', 'VelocityCoefficient0': '853.1', 'VelocityCoefficient1': '-0.932', 'VelocityCoefficient2': '0.003362', 'KillCoefficient1': '4.393277', 'KillCoefficient2': '0.040288', 'Recoil': '300.3', 'RunStandAccuracy': '3335.38', 'RunCrouchAccuracy': '4672.58', 'RunProneAccuracy': '4304.25', 'WalkStandAccuracy': '542.07', 'WalkCrouchAccuracy': '747.47', 'WalkProneAccuracy': '4304.25', 'ShuffleStandAccuracy': '101.43', 'ShuffleCrouchAccuracy': '146.23', 'ShuffleProneAccuracy': '4304.25', 'StationaryStandAccuracy': '14.13', 'StationaryCrouchAccuracy': '5.02', 'StationaryProneAccuracy': '0.90', 'TurnBandVelocity1': '0.59', 'TurnBandMultiplier1': '6.73', 'TurnBandVelocity2': '1.36', 'TurnBandMultiplier2': '13.49', 'TurnBandVelocity3': '2.52', 'TurnBandMultiplier3': '23.75', 'TurnBandVelocity4': '4.11', 'TurnBandMultiplier4': '37.74', 'StabilizationTime': '0.48'},
        'ai': {'Weight': '14.24', 'MagazineCapacity': '10', 'MagazineWeight': '1.87', 'MaxRange': '1800', 'VelocityCoefficient0': '853.1', 'VelocityCoefficient1': '-0.932', 'VelocityCoefficient2': '0.003362', 'KillCoefficient1': '4.393277', 'KillCoefficient2': '0.040288', 'Recoil': '300.3', 'RunStandAccuracy': '33353.8', 'RunCrouchAccuracy': '46725.8', 'RunProneAccuracy': '43042.5', 'WalkStandAccuracy': '5420.7', 'WalkCrouchAccuracy': '7474.7', 'WalkProneAccuracy': '43042.5', 'ShuffleStandAccuracy': '1014.3', 'ShuffleCrouchAccuracy': '1462.3', 'ShuffleProneAccuracy': '43042.5', 'StationaryStandAccuracy': '141.3', 'StationaryCrouchAccuracy': '50.2', 'StationaryProneAccuracy': '9.0', 'TurnBandVelocity1': '0.59', 'TurnBandMultiplier1': '6.73', 'TurnBandVelocity2': '1.36', 'TurnBandMultiplier2': '13.49', 'TurnBandVelocity3': '2.52', 'TurnBandMultiplier3': '23.75', 'TurnBandVelocity4': '4.11', 'TurnBandMultiplier4': '37.74', 'StabilizationTime': '0.48'},
    },
    'm98': {
        'player': {'Weight': '7.00', 'MagazineCapacity': '10', 'MagazineWeight': '0.45', 'MaxRange': '1200', 'VelocityCoefficient0': '975.1', 'VelocityCoefficient1': '-0.905', 'VelocityCoefficient2': '0.002179', 'KillCoefficient1': '1.775499', 'KillCoefficient2': '0.014188', 'Recoil': '120.4', 'RunStandAccuracy': '935.36', 'RunCrouchAccuracy': '1306.95', 'RunProneAccuracy': '3111.92', 'WalkStandAccuracy': '158.57', 'WalkCrouchAccuracy': '216.69', 'WalkProneAccuracy': '3111.92', 'ShuffleStandAccuracy': '33.35', 'ShuffleCrouchAccuracy': '46.85', 'ShuffleProneAccuracy': '3111.92', 'StationaryStandAccuracy': '7.19', 'StationaryCrouchAccuracy': '2.78', 'StationaryProneAccuracy': '0.77', 'TurnBandVelocity1': '1.00', 'TurnBandMultiplier1': '4.97', 'TurnBandVelocity2': '2.00', 'TurnBandMultiplier2': '8.58', 'TurnBandVelocity3': '3.41', 'TurnBandMultiplier3': '13.67', 'TurnBandVelocity4': '5.26', 'TurnBandMultiplier4': '20.34', 'StabilizationTime': '0.32'},
        'ai': {'Weight': '7.00', 'MagazineCapacity': '10', 'MagazineWeight': '0.45', 'MaxRange': '1200', 'VelocityCoefficient0': '975.1', 'VelocityCoefficient1': '-0.905', 'VelocityCoefficient2': '0.002179', 'KillCoefficient1': '1.775499', 'KillCoefficient2': '0.014188', 'Recoil': '120.4', 'RunStandAccuracy': '9353.6', 'RunCrouchAccuracy': '13069.5', 'RunProneAccuracy': '31119.2', 'WalkStandAccuracy': '1585.7', 'WalkCrouchAccuracy': '2166.9', 'WalkProneAccuracy': '31119.2', 'ShuffleStandAccuracy': '333.5', 'ShuffleCrouchAccuracy': '468.5', 'ShuffleProneAccuracy': '31119.2', 'StationaryStandAccuracy': '71.9', 'StationaryCrouchAccuracy': '27.8', 'StationaryProneAccuracy': '7.7', 'TurnBandVelocity1': '1.00', 'TurnBandMultiplier1': '4.97', 'TurnBandVelocity2': '2.00', 'TurnBandMultiplier2': '8.58', 'TurnBandVelocity3': '3.41', 'TurnBandMultiplier3': '13.67', 'TurnBandVelocity4': '5.26', 'TurnBandMultiplier4': '20.34', 'StabilizationTime': '0.32'},
    },
    'm9pistol': {
        'player': {'Weight': '1.00', 'MagazineCapacity': '15', 'MagazineWeight': '0.23', 'MaxRange': '100', 'VelocityCoefficient0': '353.9', 'VelocityCoefficient1': '-0.949', 'VelocityCoefficient2': '0.006978', 'KillCoefficient1': '0.288680', 'KillCoefficient2': '0.006398', 'Recoil': '28.7', 'RunStandAccuracy': '33.08', 'RunCrouchAccuracy': '40.14', 'RunProneAccuracy': '2521.06', 'WalkStandAccuracy': '17.61', 'WalkCrouchAccuracy': '20.29', 'WalkProneAccuracy': '2521.06', 'ShuffleStandAccuracy': '11.17', 'ShuffleCrouchAccuracy': '13.03', 'ShuffleProneAccuracy': '2521.06', 'StationaryStandAccuracy': '7.95', 'StationaryCrouchAccuracy': '5.15', 'StationaryProneAccuracy': '3.79', 'TurnBandVelocity1': '5.56', 'TurnBandMultiplier1': '1.35', 'TurnBandVelocity2': '7.92', 'TurnBandMultiplier2': '1.70', 'TurnBandVelocity3': '10.74', 'TurnBandMultiplier3': '2.11', 'TurnBandVelocity4': '14.01', 'TurnBandMultiplier4': '2.59', 'StabilizationTime': '0.10'},
        'ai': {'Weight': '1.00', 'MagazineCapacity': '15', 'MagazineWeight': '0.23', 'MaxRange': '100', 'VelocityCoefficient0': '353.9', 'VelocityCoefficient1': '-0.949', 'VelocityCoefficient2': '0.006978', 'KillCoefficient1': '0.288680', 'KillCoefficient2': '0.006398', 'Recoil': '28.7', 'RunStandAccuracy': '330.8', 'RunCrouchAccuracy': '401.4', 'RunProneAccuracy': '25210.6', 'WalkStandAccuracy': '176.1', 'WalkCrouchAccuracy': '202.9', 'WalkProneAccuracy': '25210.6', 'ShuffleStandAccuracy': '111.7', 'ShuffleCrouchAccuracy': '130.3', 'ShuffleProneAccuracy': '25210.6', 'StationaryStandAccuracy': '79.5', 'StationaryCrouchAccuracy': '51.5', 'StationaryProneAccuracy': '37.9', 'TurnBandVelocity1': '5.56', 'TurnBandMultiplier1': '1.35', 'TurnBandVelocity2': '7.92', 'TurnBandMultiplier2': '1.70', 'TurnBandVelocity3': '10.74', 'TurnBandMultiplier3': '2.11', 'TurnBandVelocity4': '14.01', 'TurnBandMultiplier4': '2.59', 'StabilizationTime': '0.10'},
    },
    'm9pistolsd': {
        'player': {'Weight': '1.17', 'MagazineCapacity': '15', 'MagazineWeight': '0.23', 'MaxRange': '100', 'VelocityCoefficient0': '353.9', 'VelocityCoefficient1': '-0.949', 'VelocityCoefficient2': '0.006978', 'KillCoefficient1': '0.288680', 'KillCoefficient2': '0.006398', 'Recoil': '26.9', 'RunStandAccuracy': '44.29', 'RunCrouchAccuracy': '55.86', 'RunProneAccuracy': '2529.24', 'WalkStandAccuracy': '19.40', 'WalkCrouchAccuracy': '22.77', 'WalkProneAccuracy': '2529.24', 'ShuffleStandAccuracy': '11.49', 'ShuffleCrouchAccuracy': '13.50', 'ShuffleProneAccuracy': '2529.24', 'StationaryStandAccuracy': '7.98', 'StationaryCrouchAccuracy': '5.16', 'StationaryProneAccuracy': '3.79', 'TurnBandVelocity1': '3.89', 'TurnBandMultiplier1': '1.42', 'TurnBandVelocity2': '5.86', 'TurnBandMultiplier2': '1.87', 'TurnBandVelocity3': '8.29', 'TurnBandMultiplier3': '2.42', 'TurnBandVelocity4': '11.16', 'TurnBandMultiplier4': '3.07', 'StabilizationTime': '0.13'},
        'ai': {'Weight': '1.17', 'MagazineCapacity': '15', 'MagazineWeight': '0.23', 'MaxRange': '100', 'VelocityCoefficient0': '353.9', 'VelocityCoefficient1': '-0.949', 'VelocityCoefficient2': '0.006978', 'KillCoefficient1': '0.288680', 'KillCoefficient2': '0.006398', 'Recoil': '26.9', 'RunStandAccuracy': '442.9', 'RunCrouchAccuracy': '558.6', 'RunProneAccuracy': '25292.4', 'WalkStandAccuracy': '194.0', 'WalkCrouchAccuracy': '227.7', 'WalkProneAccuracy': '25292.4', 'ShuffleStandAccuracy': '114.9', 'ShuffleCrouchAccuracy': '135.0', 'ShuffleProneAccuracy': '25292.4', 'StationaryStandAccuracy': '79.8', 'StationaryCrouchAccuracy': '51.6', 'StationaryProneAccuracy': '37.9', 'TurnBandVelocity1': '3.89', 'TurnBandMultiplier1': '1.42', 'TurnBandVelocity2': '5.86', 'TurnBandMultiplier2': '1.87', 'TurnBandVelocity3': '8.29', 'TurnBandMultiplier3': '2.42', 'TurnBandVelocity4': '11.16', 'TurnBandMultiplier4': '3.07', 'StabilizationTime': '0.13'},
    },
    'makarov': {
        'player': {'Weight': '0.73', 'MagazineCapacity': '8', 'MagazineWeight': '0.12', 'MaxRange': '100', 'VelocityCoefficient0': '314.9', 'VelocityCoefficient1': '-0.952', 'VelocityCoefficient2': '0.012724', 'KillCoefficient1': '0.213280', 'KillCoefficient2': '0.005315', 'Recoil': '24.9', 'RunStandAccuracy': '29.99', 'RunCrouchAccuracy': '35.48', 'RunProneAccuracy': '2518.62', 'WalkStandAccuracy': '17.81', 'WalkCrouchAccuracy': '20.29', 'WalkProneAccuracy': '2518.62', 'ShuffleStandAccuracy': '11.83', 'ShuffleCrouchAccuracy': '13.67', 'ShuffleProneAccuracy': '2518.62', 'StationaryStandAccuracy': '8.67', 'StationaryCrouchAccuracy': '5.84', 'StationaryProneAccuracy': '4.45', 'TurnBandVelocity1': '6.66', 'TurnBandMultiplier1': '1.22', 'TurnBandVelocity2': '9.24', 'TurnBandMultiplier2': '1.50', 'TurnBandVelocity3': '12.28', 'TurnBandMultiplier3': '1.83', 'TurnBandVelocity4': '15.78', 'TurnBandMultiplier4': '2.21', 'StabilizationTime': '0.09'},
        'ai': {'Weight': '0.73', 'MagazineCapacity': '8', 'MagazineWeight': '0.12', 'MaxRange': '100', 'VelocityCoefficient0': '314.9', 'VelocityCoefficient1': '-0.952', 'VelocityCoefficient2': '0.012724', 'KillCoefficient1': '0.213280', 'KillCoefficient2': '0.005315', 'Recoil': '24.9', 'RunStandAccuracy': '299.9', 'RunCrouchAccuracy': '354.8', 'RunProneAccuracy': '25186.2', 'WalkStandAccuracy': '178.1', 'WalkCrouchAccuracy': '202.9', 'WalkProneAccuracy': '25186.2', 'ShuffleStandAccuracy': '118.3', 'ShuffleCrouchAccuracy': '136.7', 'ShuffleProneAccuracy': '25186.2', 'StationaryStandAccuracy': '86.7', 'StationaryCrouchAccuracy': '58.4', 'StationaryProneAccuracy': '44.5', 'TurnBandVelocity1': '6.66', 'TurnBandMultiplier1': '1.22', 'TurnBandVelocity2': '9.24', 'TurnBandMultiplier2': '1.50', 'TurnBandVelocity3': '12.28', 'TurnBandMultiplier3': '1.83', 'TurnBandVelocity4': '15.78', 'TurnBandMultiplier4': '2.21', 'StabilizationTime': '0.09'},
    },
    'mg3gpmg': {
        'player': {'Weight': '11.50', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1500', 'VelocityCoefficient0': '819.9', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000611', 'KillCoefficient1': '0.877881', 'KillCoefficient2': '0.008248', 'Recoil': '35.7', 'RunStandAccuracy': '1704.75', 'RunCrouchAccuracy': '2385.83', 'RunProneAccuracy': '3538.16', 'WalkStandAccuracy': '281.65', 'WalkCrouchAccuracy': '386.98', 'WalkProneAccuracy': '3538.16', 'ShuffleStandAccuracy': '55.32', 'ShuffleCrouchAccuracy': '78.86', 'ShuffleProneAccuracy': '3538.16', 'StationaryStandAccuracy': '9.57', 'StationaryCrouchAccuracy': '3.63', 'StationaryProneAccuracy': '0.95', 'TurnBandVelocity1': '0.73', 'TurnBandMultiplier1': '5.11', 'TurnBandVelocity2': '1.59', 'TurnBandMultiplier2': '9.61', 'TurnBandVelocity3': '2.84', 'TurnBandMultiplier3': '16.24', 'TurnBandVelocity4': '4.53', 'TurnBandMultiplier4': '25.13', 'StabilizationTime': '0.41'},
        'ai': {'Weight': '11.50', 'MagazineCapacity': '100', 'MagazineWeight': '3.10', 'MaxRange': '1500', 'VelocityCoefficient0': '819.9', 'VelocityCoefficient1': '-0.838', 'VelocityCoefficient2': '0.000611', 'KillCoefficient1': '0.877881', 'KillCoefficient2': '0.008248', 'Recoil': '35.7', 'RunStandAccuracy': '17047.5', 'RunCrouchAccuracy': '23858.3', 'RunProneAccuracy': '35381.6', 'WalkStandAccuracy': '2816.5', 'WalkCrouchAccuracy': '3869.8', 'WalkProneAccuracy': '35381.6', 'ShuffleStandAccuracy': '553.2', 'ShuffleCrouchAccuracy': '788.6', 'ShuffleProneAccuracy': '35381.6', 'StationaryStandAccuracy': '95.7', 'StationaryCrouchAccuracy': '36.3', 'StationaryProneAccuracy': '9.5', 'TurnBandVelocity1': '0.73', 'TurnBandMultiplier1': '5.11', 'TurnBandVelocity2': '1.59', 'TurnBandMultiplier2': '9.61', 'TurnBandVelocity3': '2.84', 'TurnBandMultiplier3': '16.24', 'TurnBandVelocity4': '4.53', 'TurnBandMultiplier4': '25.13', 'StabilizationTime': '0.41'},
    },
    'mm1': {
        'player': {'Weight': '5.70', 'MagazineCapacity': '12', 'MagazineWeight': '2.88', 'MaxRange': '400', 'Recoil': '117.1', 'RunStandAccuracy': '126.09', 'RunCrouchAccuracy': '170.02', 'RunProneAccuracy': '2587.85', 'WalkStandAccuracy': '33.64', 'WalkCrouchAccuracy': '42.00', 'WalkProneAccuracy': '2587.85', 'ShuffleStandAccuracy': '15.05', 'ShuffleCrouchAccuracy': '18.17', 'ShuffleProneAccuracy': '2587.85', 'StationaryStandAccuracy': '9.44', 'StationaryCrouchAccuracy': '6.40', 'StationaryProneAccuracy': '4.90', 'TurnBandVelocity1': '1.69', 'TurnBandMultiplier1': '1.46', 'TurnBandVelocity2': '2.99', 'TurnBandMultiplier2': '2.23', 'TurnBandVelocity3': '4.72', 'TurnBandMultiplier3': '3.25', 'TurnBandVelocity4': '6.89', 'TurnBandMultiplier4': '4.53', 'StabilizationTime': '0.22'},
        'ai': {'Weight': '5.70', 'MagazineCapacity': '12', 'MagazineWeight': '2.88', 'MaxRange': '400', 'Recoil': '117.1', 'RunStandAccuracy': '1260.9', 'RunCrouchAccuracy': '1700.2', 'RunProneAccuracy': '25878.5', 'WalkStandAccuracy': '336.4', 'WalkCrouchAccuracy': '420.0', 'WalkProneAccuracy': '25878.5', 'ShuffleStandAccuracy': '150.5', 'ShuffleCrouchAccuracy': '181.7', 'ShuffleProneAccuracy': '25878.5', 'StationaryStandAccuracy': '94.4', 'StationaryCrouchAccuracy': '64.0', 'StationaryProneAccuracy': '49.0', 'TurnBandVelocity1': '1.69', 'TurnBandMultiplier1': '1.46', 'TurnBandVelocity2': '2.99', 'TurnBandMultiplier2': '2.23', 'TurnBandVelocity3': '4.72', 'TurnBandMultiplier3': '3.25', 'TurnBandVelocity4': '6.89', 'TurnBandMultiplier4': '4.53', 'StabilizationTime': '0.22'},
    },
    'mp5a4i': {
        'player': {'Weight': '2.54', 'MagazineCapacity': '30', 'MagazineWeight': '0.46', 'MaxRange': '200', 'VelocityCoefficient0': '399.9', 'VelocityCoefficient1': '-0.923', 'VelocityCoefficient2': '0.005457', 'KillCoefficient1': '0.326226', 'KillCoefficient2': '0.006374', 'Recoil': '20.9', 'RunStandAccuracy': '112.04', 'RunCrouchAccuracy': '151.54', 'RunProneAccuracy': '2578.45', 'WalkStandAccuracy': '28.81', 'WalkCrouchAccuracy': '36.37', 'WalkProneAccuracy': '2578.45', 'ShuffleStandAccuracy': '11.91', 'ShuffleCrouchAccuracy': '14.75', 'ShuffleProneAccuracy': '2578.45', 'StationaryStandAccuracy': '6.70', 'StationaryCrouchAccuracy': '3.81', 'StationaryProneAccuracy': '2.45', 'TurnBandVelocity1': '2.14', 'TurnBandMultiplier1': '1.99', 'TurnBandVelocity2': '3.60', 'TurnBandMultiplier2': '2.90', 'TurnBandVelocity3': '5.49', 'TurnBandMultiplier3': '4.07', 'TurnBandVelocity4': '7.84', 'TurnBandMultiplier4': '5.52', 'StabilizationTime': '0.19'},
        'ai': {'Weight': '2.54', 'MagazineCapacity': '30', 'MagazineWeight': '0.46', 'MaxRange': '200', 'VelocityCoefficient0': '399.9', 'VelocityCoefficient1': '-0.923', 'VelocityCoefficient2': '0.005457', 'KillCoefficient1': '0.326226', 'KillCoefficient2': '0.006374', 'Recoil': '20.9', 'RunStandAccuracy': '1120.4', 'RunCrouchAccuracy': '1515.4', 'RunProneAccuracy': '25784.5', 'WalkStandAccuracy': '288.1', 'WalkCrouchAccuracy': '363.7', 'WalkProneAccuracy': '25784.5', 'ShuffleStandAccuracy': '119.1', 'ShuffleCrouchAccuracy': '147.5', 'ShuffleProneAccuracy': '25784.5', 'StationaryStandAccuracy': '67.0', 'StationaryCrouchAccuracy': '38.1', 'StationaryProneAccuracy': '24.5', 'TurnBandVelocity1': '2.14', 'TurnBandMultiplier1': '1.99', 'TurnBandVelocity2': '3.60', 'TurnBandMultiplier2': '2.90', 'TurnBandVelocity3': '5.49', 'TurnBandMultiplier3': '4.07', 'TurnBandVelocity4': '7.84', 'TurnBandMultiplier4': '5.52', 'StabilizationTime': '0.19'},
    },
    'mp5sd6i': {
        'player': {'Weight': '3.18', 'MagazineCapacity': '30', 'MagazineWeight': '0.46', 'MaxRange': '200', 'VelocityCoefficient0': '285.0', 'VelocityCoefficient1': '-0.923', 'VelocityCoefficient2': '0.009690', 'KillCoefficient1': '0.232486', 'KillCoefficient2': '0.006374', 'Recoil': '14.6', 'RunStandAccuracy': '138.61', 'RunCrouchAccuracy': '188.55', 'RunProneAccuracy': '2597.24', 'WalkStandAccuracy': '33.59', 'WalkCrouchAccuracy': '42.77', 'WalkProneAccuracy': '2597.24', 'ShuffleStandAccuracy': '13.24', 'ShuffleCrouchAccuracy': '16.44', 'ShuffleProneAccuracy': '2597.24', 'StationaryStandAccuracy': '7.34', 'StationaryCrouchAccuracy': '4.37', 'StationaryProneAccuracy': '2.96', 'TurnBandVelocity1': '1.80', 'TurnBandMultiplier1': '1.88', 'TurnBandVelocity2': '3.14', 'TurnBandMultiplier2': '2.82', 'TurnBandVelocity3': '4.91', 'TurnBandMultiplier3': '4.07', 'TurnBandVelocity4': '7.13', 'TurnBandMultiplier4': '5.63', 'StabilizationTime': '0.21'},
        'ai': {'Weight': '3.18', 'MagazineCapacity': '30', 'MagazineWeight': '0.46', 'MaxRange': '200', 'VelocityCoefficient0': '285.0', 'VelocityCoefficient1': '-0.923', 'VelocityCoefficient2': '0.009690', 'KillCoefficient1': '0.232486', 'KillCoefficient2': '0.006374', 'Recoil': '14.6', 'RunStandAccuracy': '1386.1', 'RunCrouchAccuracy': '1885.5', 'RunProneAccuracy': '25972.4', 'WalkStandAccuracy': '335.9', 'WalkCrouchAccuracy': '427.7', 'WalkProneAccuracy': '25972.4', 'ShuffleStandAccuracy': '132.4', 'ShuffleCrouchAccuracy': '164.4', 'ShuffleProneAccuracy': '25972.4', 'StationaryStandAccuracy': '73.4', 'StationaryCrouchAccuracy': '43.7', 'StationaryProneAccuracy': '29.6', 'TurnBandVelocity1': '1.80', 'TurnBandMultiplier1': '1.88', 'TurnBandVelocity2': '3.14', 'TurnBandMultiplier2': '2.82', 'TurnBandVelocity3': '4.91', 'TurnBandMultiplier3': '4.07', 'TurnBandVelocity4': '7.13', 'TurnBandMultiplier4': '5.63', 'StabilizationTime': '0.21'},
    },
    'oicwhe_oicwke': {
        'player': {'MagazineCapacity': '6', 'MagazineWeight': '1.10', 'MaxRange': '1000', 'Recoil': '1407.7', 'RunStandAccuracy': '194.41', 'RunCrouchAccuracy': '265.81', 'RunProneAccuracy': '2636.02', 'WalkStandAccuracy': '44.60', 'WalkCrouchAccuracy': '57.16', 'WalkProneAccuracy': '2636.02', 'ShuffleStandAccuracy': '17.04', 'ShuffleCrouchAccuracy': '21.05', 'ShuffleProneAccuracy': '2636.02', 'StationaryStandAccuracy': '9.68', 'StationaryCrouchAccuracy': '6.51', 'StationaryProneAccuracy': '4.95', 'TurnBandVelocity1': '1.32', 'TurnBandMultiplier1': '1.56', 'TurnBandVelocity2': '2.47', 'TurnBandMultiplier2': '2.50', 'TurnBandVelocity3': '4.04', 'TurnBandMultiplier3': '3.80', 'TurnBandVelocity4': '6.05', 'TurnBandMultiplier4': '5.45', 'StabilizationTime': '0.27'},
        'ai': {'MagazineCapacity': '6', 'MagazineWeight': '1.10', 'MaxRange': '1000', 'Recoil': '1407.7', 'RunStandAccuracy': '1944.1', 'RunCrouchAccuracy': '2658.1', 'RunProneAccuracy': '26360.2', 'WalkStandAccuracy': '446.0', 'WalkCrouchAccuracy': '571.6', 'WalkProneAccuracy': '26360.2', 'ShuffleStandAccuracy': '170.4', 'ShuffleCrouchAccuracy': '210.5', 'ShuffleProneAccuracy': '26360.2', 'StationaryStandAccuracy': '96.8', 'StationaryCrouchAccuracy': '65.1', 'StationaryProneAccuracy': '49.5', 'TurnBandVelocity1': '1.32', 'TurnBandMultiplier1': '1.56', 'TurnBandVelocity2': '2.47', 'TurnBandMultiplier2': '2.50', 'TurnBandVelocity3': '4.04', 'TurnBandMultiplier3': '3.80', 'TurnBandVelocity4': '6.05', 'TurnBandMultiplier4': '5.45', 'StabilizationTime': '0.27'},
    },
    'oicwke': {
        'player': {'Weight': '2.70', 'MagazineCapacity': '20', 'MagazineWeight': '0.32', 'MaxRange': '900', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000469', 'KillCoefficient1': '0.372603', 'KillCoefficient2': '0.003455', 'Recoil': '24.1', 'RunStandAccuracy': '225.85', 'RunCrouchAccuracy': '311.76', 'RunProneAccuracy': '2658.83', 'WalkStandAccuracy': '45.67', 'WalkCrouchAccuracy': '60.24', 'WalkProneAccuracy': '2658.83', 'ShuffleStandAccuracy': '13.73', 'ShuffleCrouchAccuracy': '17.99', 'ShuffleProneAccuracy': '2658.83', 'StationaryStandAccuracy': '5.64', 'StationaryCrouchAccuracy': '2.59', 'StationaryProneAccuracy': '1.19', 'TurnBandVelocity1': '1.74', 'TurnBandMultiplier1': '3.11', 'TurnBandVelocity2': '3.06', 'TurnBandMultiplier2': '4.71', 'TurnBandVelocity3': '4.81', 'TurnBandMultiplier3': '6.82', 'TurnBandVelocity4': '7.00', 'TurnBandMultiplier4': '9.47', 'StabilizationTime': '0.22'},
        'ai': {'Weight': '2.70', 'MagazineCapacity': '20', 'MagazineWeight': '0.32', 'MaxRange': '900', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000469', 'KillCoefficient1': '0.372603', 'KillCoefficient2': '0.003455', 'Recoil': '24.1', 'RunStandAccuracy': '2258.5', 'RunCrouchAccuracy': '3117.6', 'RunProneAccuracy': '26588.3', 'WalkStandAccuracy': '456.7', 'WalkCrouchAccuracy': '602.4', 'WalkProneAccuracy': '26588.3', 'ShuffleStandAccuracy': '137.3', 'ShuffleCrouchAccuracy': '179.9', 'ShuffleProneAccuracy': '26588.3', 'StationaryStandAccuracy': '56.4', 'StationaryCrouchAccuracy': '25.9', 'StationaryProneAccuracy': '11.9', 'TurnBandVelocity1': '1.74', 'TurnBandMultiplier1': '3.11', 'TurnBandVelocity2': '3.06', 'TurnBandMultiplier2': '4.71', 'TurnBandVelocity3': '4.81', 'TurnBandMultiplier3': '6.82', 'TurnBandVelocity4': '7.00', 'TurnBandMultiplier4': '9.47', 'StabilizationTime': '0.22'},
    },
    'oicwke_oicwhe': {
        'player': {'Weight': '5.70', 'MagazineCapacity': '20', 'MagazineWeight': '0.32', 'MaxRange': '900', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000469', 'KillCoefficient1': '0.372603', 'KillCoefficient2': '0.003455', 'Recoil': '19.4', 'RunStandAccuracy': '343.79', 'RunCrouchAccuracy': '477.14', 'RunProneAccuracy': '2739.32', 'WalkStandAccuracy': '64.52', 'WalkCrouchAccuracy': '86.33', 'WalkProneAccuracy': '2739.32', 'ShuffleStandAccuracy': '17.08', 'ShuffleCrouchAccuracy': '22.88', 'ShuffleProneAccuracy': '2739.32', 'StationaryStandAccuracy': '5.99', 'StationaryCrouchAccuracy': '2.71', 'StationaryProneAccuracy': '1.20', 'TurnBandVelocity1': '1.40', 'TurnBandMultiplier1': '3.29', 'TurnBandVelocity2': '2.58', 'TurnBandMultiplier2': '5.22', 'TurnBandVelocity3': '4.19', 'TurnBandMultiplier3': '7.84', 'TurnBandVelocity4': '6.24', 'TurnBandMultiplier4': '11.18', 'StabilizationTime': '0.25'},
        'ai': {'Weight': '5.70', 'MagazineCapacity': '20', 'MagazineWeight': '0.32', 'MaxRange': '900', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.000469', 'KillCoefficient1': '0.372603', 'KillCoefficient2': '0.003455', 'Recoil': '19.4', 'RunStandAccuracy': '3437.9', 'RunCrouchAccuracy': '4771.4', 'RunProneAccuracy': '27393.2', 'WalkStandAccuracy': '645.2', 'WalkCrouchAccuracy': '863.3', 'WalkProneAccuracy': '27393.2', 'ShuffleStandAccuracy': '170.8', 'ShuffleCrouchAccuracy': '228.8', 'ShuffleProneAccuracy': '27393.2', 'StationaryStandAccuracy': '59.9', 'StationaryCrouchAccuracy': '27.1', 'StationaryProneAccuracy': '12.0', 'TurnBandVelocity1': '1.40', 'TurnBandMultiplier1': '3.29', 'TurnBandVelocity2': '2.58', 'TurnBandMultiplier2': '5.22', 'TurnBandVelocity3': '4.19', 'TurnBandMultiplier3': '7.84', 'TurnBandVelocity4': '6.24', 'TurnBandMultiplier4': '11.18', 'StabilizationTime': '0.25'},
    },
    'pkmi': {
        'player': {'Weight': '7.45', 'MagazineCapacity': '100', 'MagazineWeight': '3.60', 'MaxRange': '1000', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001399', 'KillCoefficient1': '0.889439', 'KillCoefficient2': '0.008344', 'Recoil': '38.7', 'RunStandAccuracy': '1200.88', 'RunCrouchAccuracy': '1679.26', 'RunProneAccuracy': '3265.30', 'WalkStandAccuracy': '201.08', 'WalkCrouchAccuracy': '275.49', 'WalkProneAccuracy': '3265.30', 'ShuffleStandAccuracy': '40.97', 'ShuffleCrouchAccuracy': '57.94', 'ShuffleProneAccuracy': '3265.30', 'StationaryStandAccuracy': '8.05', 'StationaryCrouchAccuracy': '3.11', 'StationaryProneAccuracy': '0.87', 'TurnBandVelocity1': '0.87', 'TurnBandMultiplier1': '4.93', 'TurnBandVelocity2': '1.80', 'TurnBandMultiplier2': '8.83', 'TurnBandVelocity3': '3.14', 'TurnBandMultiplier3': '14.44', 'TurnBandVelocity4': '4.91', 'TurnBandMultiplier4': '21.87', 'StabilizationTime': '0.36'},
        'ai': {'Weight': '7.45', 'MagazineCapacity': '100', 'MagazineWeight': '3.60', 'MaxRange': '1000', 'VelocityCoefficient0': '825.1', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001399', 'KillCoefficient1': '0.889439', 'KillCoefficient2': '0.008344', 'Recoil': '38.7', 'RunStandAccuracy': '12008.8', 'RunCrouchAccuracy': '16792.6', 'RunProneAccuracy': '32653.0', 'WalkStandAccuracy': '2010.8', 'WalkCrouchAccuracy': '2754.9', 'WalkProneAccuracy': '32653.0', 'ShuffleStandAccuracy': '409.7', 'ShuffleCrouchAccuracy': '579.4', 'ShuffleProneAccuracy': '32653.0', 'StationaryStandAccuracy': '80.5', 'StationaryCrouchAccuracy': '31.1', 'StationaryProneAccuracy': '8.7', 'TurnBandVelocity1': '0.87', 'TurnBandMultiplier1': '4.93', 'TurnBandVelocity2': '1.80', 'TurnBandMultiplier2': '8.83', 'TurnBandVelocity3': '3.14', 'TurnBandMultiplier3': '14.44', 'TurnBandVelocity4': '4.91', 'TurnBandMultiplier4': '21.87', 'StabilizationTime': '0.36'},
    },
    'psg1a1': {
        'player': {'Weight': '8.55', 'MagazineCapacity': '5', 'MagazineWeight': '0.20', 'MaxRange': '1000', 'VelocityCoefficient0': '868.1', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001352', 'KillCoefficient1': '1.106482', 'KillCoefficient2': '0.009873', 'Recoil': '55.7', 'RunStandAccuracy': '1138.43', 'RunCrouchAccuracy': '1591.73', 'RunProneAccuracy': '3229.90', 'WalkStandAccuracy': '191.00', 'WalkCrouchAccuracy': '261.58', 'WalkProneAccuracy': '3229.90', 'ShuffleStandAccuracy': '39.09', 'ShuffleCrouchAccuracy': '55.24', 'ShuffleProneAccuracy': '3229.90', 'StationaryStandAccuracy': '7.77', 'StationaryCrouchAccuracy': '2.95', 'StationaryProneAccuracy': '0.77', 'TurnBandVelocity1': '0.92', 'TurnBandMultiplier1': '5.21', 'TurnBandVelocity2': '1.88', 'TurnBandMultiplier2': '9.19', 'TurnBandVelocity3': '3.25', 'TurnBandMultiplier3': '14.87', 'TurnBandVelocity4': '5.05', 'TurnBandMultiplier4': '22.35', 'StabilizationTime': '0.34'},
        'ai': {'Weight': '8.55', 'MagazineCapacity': '5', 'MagazineWeight': '0.20', 'MaxRange': '1000', 'VelocityCoefficient0': '868.1', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001352', 'KillCoefficient1': '1.106482', 'KillCoefficient2': '0.009873', 'Recoil': '55.7', 'RunStandAccuracy': '11384.3', 'RunCrouchAccuracy': '15917.3', 'RunProneAccuracy': '32299.0', 'WalkStandAccuracy': '1910.0', 'WalkCrouchAccuracy': '2615.8', 'WalkProneAccuracy': '32299.0', 'ShuffleStandAccuracy': '390.9', 'ShuffleCrouchAccuracy': '552.4', 'ShuffleProneAccuracy': '32299.0', 'StationaryStandAccuracy': '77.7', 'StationaryCrouchAccuracy': '29.5', 'StationaryProneAccuracy': '7.7', 'TurnBandVelocity1': '0.92', 'TurnBandMultiplier1': '5.21', 'TurnBandVelocity2': '1.88', 'TurnBandMultiplier2': '9.19', 'TurnBandVelocity3': '3.25', 'TurnBandMultiplier3': '14.87', 'TurnBandVelocity4': '5.05', 'TurnBandMultiplier4': '22.35', 'StabilizationTime': '0.34'},
    },
    'rp46': {
        'player': {'Weight': '13.00', 'MagazineCapacity': '100', 'MagazineWeight': '3.50', 'MaxRange': '900', 'VelocityCoefficient0': '839.7', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001340', 'KillCoefficient1': '0.905210', 'KillCoefficient2': '0.008344', 'Recoil': '35.5', 'RunStandAccuracy': '2115.90', 'RunCrouchAccuracy': '2962.40', 'RunProneAccuracy': '3746.12', 'WalkStandAccuracy': '347.35', 'WalkCrouchAccuracy': '477.91', 'WalkProneAccuracy': '3746.12', 'ShuffleStandAccuracy': '66.99', 'ShuffleCrouchAccuracy': '95.89', 'ShuffleProneAccuracy': '3746.12', 'StationaryStandAccuracy': '10.76', 'StationaryCrouchAccuracy': '4.02', 'StationaryProneAccuracy': '0.97', 'TurnBandVelocity1': '0.67', 'TurnBandMultiplier1': '5.36', 'TurnBandVelocity2': '1.48', 'TurnBandMultiplier2': '10.36', 'TurnBandVelocity3': '2.70', 'TurnBandMultiplier3': '17.81', 'TurnBandVelocity4': '4.35', 'TurnBandMultiplier4': '27.87', 'StabilizationTime': '0.44'},
        'ai': {'Weight': '13.00', 'MagazineCapacity': '100', 'MagazineWeight': '3.50', 'MaxRange': '900', 'VelocityCoefficient0': '839.7', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.001340', 'KillCoefficient1': '0.905210', 'KillCoefficient2': '0.008344', 'Recoil': '35.5', 'RunStandAccuracy': '21159.0', 'RunCrouchAccuracy': '29624.0', 'RunProneAccuracy': '37461.2', 'WalkStandAccuracy': '3473.5', 'WalkCrouchAccuracy': '4779.1', 'WalkProneAccuracy': '37461.2', 'ShuffleStandAccuracy': '669.9', 'ShuffleCrouchAccuracy': '958.9', 'ShuffleProneAccuracy': '37461.2', 'StationaryStandAccuracy': '107.6', 'StationaryCrouchAccuracy': '40.2', 'StationaryProneAccuracy': '9.7', 'TurnBandVelocity1': '0.67', 'TurnBandMultiplier1': '5.36', 'TurnBandVelocity2': '1.48', 'TurnBandMultiplier2': '10.36', 'TurnBandVelocity3': '2.70', 'TurnBandMultiplier3': '17.81', 'TurnBandVelocity4': '4.35', 'TurnBandMultiplier4': '27.87', 'StabilizationTime': '0.44'},
    },
    'rpg7': {
        'player': {'Weight': '7.90', 'MagazineCapacity': '1', 'MagazineWeight': '2.60', 'MaxRange': '300', 'Recoil': '132.9', 'RunStandAccuracy': '336.64', 'RunCrouchAccuracy': '465.94', 'RunProneAccuracy': '2733.94', 'WalkStandAccuracy': '65.88', 'WalkCrouchAccuracy': '87.19', 'WalkProneAccuracy': '2733.94', 'ShuffleStandAccuracy': '19.53', 'ShuffleCrouchAccuracy': '25.34', 'ShuffleProneAccuracy': '2733.94', 'StationaryStandAccuracy': '8.58', 'StationaryCrouchAccuracy': '5.19', 'StationaryProneAccuracy': '3.58', 'TurnBandVelocity1': '1.07', 'TurnBandMultiplier1': '1.96', 'TurnBandVelocity2': '2.11', 'TurnBandMultiplier2': '3.32', 'TurnBandVelocity3': '3.56', 'TurnBandMultiplier3': '5.22', 'TurnBandVelocity4': '5.45', 'TurnBandMultiplier4': '7.69', 'StabilizationTime': '0.31'},
        'ai': {'Weight': '7.90', 'MagazineCapacity': '1', 'MagazineWeight': '2.60', 'MaxRange': '300', 'Recoil': '132.9', 'RunStandAccuracy': '3366.4', 'RunCrouchAccuracy': '4659.4', 'RunProneAccuracy': '27339.4', 'WalkStandAccuracy': '658.8', 'WalkCrouchAccuracy': '871.9', 'WalkProneAccuracy': '27339.4', 'ShuffleStandAccuracy': '195.3', 'ShuffleCrouchAccuracy': '253.4', 'ShuffleProneAccuracy': '27339.4', 'StationaryStandAccuracy': '85.8', 'StationaryCrouchAccuracy': '51.9', 'StationaryProneAccuracy': '35.8', 'TurnBandVelocity1': '1.07', 'TurnBandMultiplier1': '1.96', 'TurnBandVelocity2': '2.11', 'TurnBandMultiplier2': '3.32', 'TurnBandVelocity3': '3.56', 'TurnBandMultiplier3': '5.22', 'TurnBandVelocity4': '5.45', 'TurnBandMultiplier4': '7.69', 'StabilizationTime': '0.31'},
    },
    'rpk74i': {
        'player': {'Weight': '4.70', 'MagazineCapacity': '45', 'MagazineWeight': '0.70', 'MaxRange': '800', 'VelocityCoefficient0': '960.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.001094', 'KillCoefficient1': '0.370640', 'KillCoefficient2': '0.002957', 'Recoil': '19.5', 'RunStandAccuracy': '475.75', 'RunCrouchAccuracy': '662.27', 'RunProneAccuracy': '2826.71', 'WalkStandAccuracy': '85.45', 'WalkCrouchAccuracy': '115.36', 'WalkProneAccuracy': '2826.71', 'ShuffleStandAccuracy': '20.66', 'ShuffleCrouchAccuracy': '28.18', 'ShuffleProneAccuracy': '2826.71', 'StationaryStandAccuracy': '6.21', 'StationaryCrouchAccuracy': '2.68', 'StationaryProneAccuracy': '1.06', 'TurnBandVelocity1': '1.24', 'TurnBandMultiplier1': '3.68', 'TurnBandVelocity2': '2.35', 'TurnBandMultiplier2': '6.02', 'TurnBandVelocity3': '3.88', 'TurnBandMultiplier3': '9.24', 'TurnBandVelocity4': '5.85', 'TurnBandMultiplier4': '13.37', 'StabilizationTime': '0.28'},
        'ai': {'Weight': '4.70', 'MagazineCapacity': '45', 'MagazineWeight': '0.70', 'MaxRange': '800', 'VelocityCoefficient0': '960.1', 'VelocityCoefficient1': '-0.808', 'VelocityCoefficient2': '-0.001094', 'KillCoefficient1': '0.370640', 'KillCoefficient2': '0.002957', 'Recoil': '19.5', 'RunStandAccuracy': '4757.5', 'RunCrouchAccuracy': '6622.7', 'RunProneAccuracy': '28267.1', 'WalkStandAccuracy': '854.5', 'WalkCrouchAccuracy': '1153.6', 'WalkProneAccuracy': '28267.1', 'ShuffleStandAccuracy': '206.6', 'ShuffleCrouchAccuracy': '281.8', 'ShuffleProneAccuracy': '28267.1', 'StationaryStandAccuracy': '62.1', 'StationaryCrouchAccuracy': '26.8', 'StationaryProneAccuracy': '10.6', 'TurnBandVelocity1': '1.24', 'TurnBandMultiplier1': '3.68', 'TurnBandVelocity2': '2.35', 'TurnBandMultiplier2': '6.02', 'TurnBandVelocity3': '3.88', 'TurnBandMultiplier3': '9.24', 'TurnBandVelocity4': '5.85', 'TurnBandMultiplier4': '13.37', 'StabilizationTime': '0.28'},
    },
    'sa25': {
        'player': {'Weight': '3.27', 'MagazineCapacity': '40', 'MagazineWeight': '0.60', 'MaxRange': '250', 'VelocityCoefficient0': '381.0', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.003308', 'KillCoefficient1': '0.310810', 'KillCoefficient2': '0.006314', 'Recoil': '17.8', 'RunStandAccuracy': '75.33', 'RunCrouchAccuracy': '100.23', 'RunProneAccuracy': '2552.18', 'WalkStandAccuracy': '22.55', 'WalkCrouchAccuracy': '27.86', 'WalkProneAccuracy': '2552.18', 'ShuffleStandAccuracy': '10.45', 'ShuffleCrouchAccuracy': '12.79', 'ShuffleProneAccuracy': '2552.18', 'StationaryStandAccuracy': '6.18', 'StationaryCrouchAccuracy': '3.38', 'StationaryProneAccuracy': '2.07', 'TurnBandVelocity1': '2.88', 'TurnBandMultiplier1': '2.05', 'TurnBandVelocity2': '4.57', 'TurnBandMultiplier2': '2.83', 'TurnBandVelocity3': '6.71', 'TurnBandMultiplier3': '3.81', 'TurnBandVelocity4': '9.30', 'TurnBandMultiplier4': '4.99', 'StabilizationTime': '0.16'},
        'ai': {'Weight': '3.27', 'MagazineCapacity': '40', 'MagazineWeight': '0.60', 'MaxRange': '250', 'VelocityCoefficient0': '381.0', 'VelocityCoefficient1': '-0.865', 'VelocityCoefficient2': '0.003308', 'KillCoefficient1': '0.310810', 'KillCoefficient2': '0.006314', 'Recoil': '17.8', 'RunStandAccuracy': '753.3', 'RunCrouchAccuracy': '1002.3', 'RunProneAccuracy': '25521.8', 'WalkStandAccuracy': '225.5', 'WalkCrouchAccuracy': '278.6', 'WalkProneAccuracy': '25521.8', 'ShuffleStandAccuracy': '104.5', 'ShuffleCrouchAccuracy': '127.9', 'ShuffleProneAccuracy': '25521.8', 'StationaryStandAccuracy': '61.8', 'StationaryCrouchAccuracy': '33.8', 'StationaryProneAccuracy': '20.7', 'TurnBandVelocity1': '2.88', 'TurnBandMultiplier1': '2.05', 'TurnBandVelocity2': '4.57', 'TurnBandMultiplier2': '2.83', 'TurnBandVelocity3': '6.71', 'TurnBandMultiplier3': '3.81', 'TurnBandVelocity4': '9.30', 'TurnBandMultiplier4': '4.99', 'StabilizationTime': '0.16'},
    },
    'sa80l85': {
        'player': {'Weight': '4.60', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '940.0', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001146', 'KillCoefficient1': '0.424495', 'KillCoefficient2': '0.003455', 'Recoil': '23.1', 'RunStandAccuracy': '250.90', 'RunCrouchAccuracy': '346.91', 'RunProneAccuracy': '2676.14', 'WalkStandAccuracy': '49.64', 'WalkCrouchAccuracy': '65.75', 'WalkProneAccuracy': '2676.14', 'ShuffleStandAccuracy': '14.40', 'ShuffleCrouchAccuracy': '19.00', 'ShuffleProneAccuracy': '2676.14', 'StationaryStandAccuracy': '5.68', 'StationaryCrouchAccuracy': '2.58', 'StationaryProneAccuracy': '1.16', 'TurnBandVelocity1': '1.66', 'TurnBandMultiplier1': '3.20', 'TurnBandVelocity2': '2.95', 'TurnBandMultiplier2': '4.89', 'TurnBandVelocity3': '4.66', 'TurnBandMultiplier3': '7.14', 'TurnBandVelocity4': '6.82', 'TurnBandMultiplier4': '9.97', 'StabilizationTime': '0.23'},
        'ai': {'Weight': '4.60', 'MagazineCapacity': '30', 'MagazineWeight': '0.48', 'MaxRange': '800', 'VelocityCoefficient0': '940.0', 'VelocityCoefficient1': '-0.803', 'VelocityCoefficient2': '-0.001146', 'KillCoefficient1': '0.424495', 'KillCoefficient2': '0.003455', 'Recoil': '23.1', 'RunStandAccuracy': '2509.0', 'RunCrouchAccuracy': '3469.1', 'RunProneAccuracy': '26761.4', 'WalkStandAccuracy': '496.4', 'WalkCrouchAccuracy': '657.5', 'WalkProneAccuracy': '26761.4', 'ShuffleStandAccuracy': '144.0', 'ShuffleCrouchAccuracy': '190.0', 'ShuffleProneAccuracy': '26761.4', 'StationaryStandAccuracy': '56.8', 'StationaryCrouchAccuracy': '25.8', 'StationaryProneAccuracy': '11.6', 'TurnBandVelocity1': '1.66', 'TurnBandMultiplier1': '3.20', 'TurnBandVelocity2': '2.95', 'TurnBandMultiplier2': '4.89', 'TurnBandVelocity3': '4.66', 'TurnBandMultiplier3': '7.14', 'TurnBandVelocity4': '6.82', 'TurnBandMultiplier4': '9.97', 'StabilizationTime': '0.23'},
    },
    'sr25m': {
        'player': {'Weight': '5.10', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '790.0', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001657', 'KillCoefficient1': '1.007023', 'KillCoefficient2': '0.009873', 'Recoil': '59.2', 'RunStandAccuracy': '705.53', 'RunCrouchAccuracy': '984.66', 'RunProneAccuracy': '2972.76', 'WalkStandAccuracy': '121.82', 'WalkCrouchAccuracy': '165.84', 'WalkProneAccuracy': '2972.76', 'ShuffleStandAccuracy': '26.81', 'ShuffleCrouchAccuracy': '37.31', 'ShuffleProneAccuracy': '2972.76', 'StationaryStandAccuracy': '6.51', 'StationaryCrouchAccuracy': '2.54', 'StationaryProneAccuracy': '0.75', 'TurnBandVelocity1': '1.14', 'TurnBandMultiplier1': '4.80', 'TurnBandVelocity2': '2.21', 'TurnBandMultiplier2': '7.99', 'TurnBandVelocity3': '3.70', 'TurnBandMultiplier3': '12.43', 'TurnBandVelocity4': '5.62', 'TurnBandMultiplier4': '18.17', 'StabilizationTime': '0.29'},
        'ai': {'Weight': '5.10', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '790.0', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001657', 'KillCoefficient1': '1.007023', 'KillCoefficient2': '0.009873', 'Recoil': '59.2', 'RunStandAccuracy': '7055.3', 'RunCrouchAccuracy': '9846.6', 'RunProneAccuracy': '29727.6', 'WalkStandAccuracy': '1218.2', 'WalkCrouchAccuracy': '1658.4', 'WalkProneAccuracy': '29727.6', 'ShuffleStandAccuracy': '268.1', 'ShuffleCrouchAccuracy': '373.1', 'ShuffleProneAccuracy': '29727.6', 'StationaryStandAccuracy': '65.1', 'StationaryCrouchAccuracy': '25.4', 'StationaryProneAccuracy': '7.5', 'TurnBandVelocity1': '1.14', 'TurnBandMultiplier1': '4.80', 'TurnBandVelocity2': '2.21', 'TurnBandMultiplier2': '7.99', 'TurnBandVelocity3': '3.70', 'TurnBandMultiplier3': '12.43', 'TurnBandVelocity4': '5.62', 'TurnBandMultiplier4': '18.17', 'StabilizationTime': '0.29'},
    },
    'sr25msd': {
        'player': {'Weight': '5.80', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '800.1', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001618', 'KillCoefficient1': '1.019844', 'KillCoefficient2': '0.009873', 'Recoil': '56.7', 'RunStandAccuracy': '1001.80', 'RunCrouchAccuracy': '1400.13', 'RunProneAccuracy': '3151.01', 'WalkStandAccuracy': '169.17', 'WalkCrouchAccuracy': '231.36', 'WalkProneAccuracy': '3151.01', 'ShuffleStandAccuracy': '35.22', 'ShuffleCrouchAccuracy': '49.58', 'ShuffleProneAccuracy': '3151.01', 'StationaryStandAccuracy': '7.37', 'StationaryCrouchAccuracy': '2.82', 'StationaryProneAccuracy': '0.76', 'TurnBandVelocity1': '0.97', 'TurnBandMultiplier1': '5.09', 'TurnBandVelocity2': '1.96', 'TurnBandMultiplier2': '8.84', 'TurnBandVelocity3': '3.36', 'TurnBandMultiplier3': '14.16', 'TurnBandVelocity4': '5.19', 'TurnBandMultiplier4': '21.13', 'StabilizationTime': '0.33'},
        'ai': {'Weight': '5.80', 'MagazineCapacity': '20', 'MagazineWeight': '0.75', 'MaxRange': '800', 'VelocityCoefficient0': '800.1', 'VelocityCoefficient1': '-0.869', 'VelocityCoefficient2': '0.001618', 'KillCoefficient1': '1.019844', 'KillCoefficient2': '0.009873', 'Recoil': '56.7', 'RunStandAccuracy': '10018.0', 'RunCrouchAccuracy': '14001.3', 'RunProneAccuracy': '31510.1', 'WalkStandAccuracy': '1691.7', 'WalkCrouchAccuracy': '2313.6', 'WalkProneAccuracy': '31510.1', 'ShuffleStandAccuracy': '352.2', 'ShuffleCrouchAccuracy': '495.8', 'ShuffleProneAccuracy': '31510.1', 'StationaryStandAccuracy': '73.7', 'StationaryCrouchAccuracy': '28.2', 'StationaryProneAccuracy': '7.6', 'TurnBandVelocity1': '0.97', 'TurnBandMultiplier1': '5.09', 'TurnBandVelocity2': '1.96', 'TurnBandMultiplier2': '8.84', 'TurnBandVelocity3': '3.36', 'TurnBandMultiplier3': '14.16', 'TurnBandVelocity4': '5.19', 'TurnBandMultiplier4': '21.13', 'StabilizationTime': '0.33'},
    },
    'vz58': {
        'player': {'Weight': '2.91', 'MagazineCapacity': '30', 'MagazineWeight': '0.58', 'MaxRange': '425', 'VelocityCoefficient0': '705.0', 'VelocityCoefficient1': '-0.785', 'VelocityCoefficient2': '-0.000240', 'KillCoefficient1': '0.631607', 'KillCoefficient2': '0.006829', 'Recoil': '42.6', 'RunStandAccuracy': '217.55', 'RunCrouchAccuracy': '300.08', 'RunProneAccuracy': '2653.05', 'WalkStandAccuracy': '44.42', 'WalkCrouchAccuracy': '58.48', 'WalkProneAccuracy': '2653.05', 'ShuffleStandAccuracy': '13.58', 'ShuffleCrouchAccuracy': '17.74', 'ShuffleProneAccuracy': '2653.05', 'StationaryStandAccuracy': '5.70', 'StationaryCrouchAccuracy': '2.66', 'StationaryProneAccuracy': '1.27', 'TurnBandVelocity1': '1.75', 'TurnBandMultiplier1': '3.00', 'TurnBandVelocity2': '3.07', 'TurnBandMultiplier2': '4.53', 'TurnBandVelocity3': '4.82', 'TurnBandMultiplier3': '6.57', 'TurnBandVelocity4': '7.01', 'TurnBandMultiplier4': '9.12', 'StabilizationTime': '0.22'},
        'ai': {'Weight': '2.91', 'MagazineCapacity': '30', 'MagazineWeight': '0.58', 'MaxRange': '425', 'VelocityCoefficient0': '705.0', 'VelocityCoefficient1': '-0.785', 'VelocityCoefficient2': '-0.000240', 'KillCoefficient1': '0.631607', 'KillCoefficient2': '0.006829', 'Recoil': '42.6', 'RunStandAccuracy': '2175.5', 'RunCrouchAccuracy': '3000.8', 'RunProneAccuracy': '26530.5', 'WalkStandAccuracy': '444.2', 'WalkCrouchAccuracy': '584.8', 'WalkProneAccuracy': '26530.5', 'ShuffleStandAccuracy': '135.8', 'ShuffleCrouchAccuracy': '177.4', 'ShuffleProneAccuracy': '26530.5', 'StationaryStandAccuracy': '57.0', 'StationaryCrouchAccuracy': '26.6', 'StationaryProneAccuracy': '12.7', 'TurnBandVelocity1': '1.75', 'TurnBandMultiplier1': '3.00', 'TurnBandVelocity2': '3.07', 'TurnBandMultiplier2': '4.53', 'TurnBandVelocity3': '4.82', 'TurnBandMultiplier3': '6.57', 'TurnBandVelocity4': '7.01', 'TurnBandMultiplier4': '9.12', 'StabilizationTime': '0.22'},
    },
}

#: PS2 gun file -> the Heroes Unleashed gun it takes (its player file; the AI's is <name>_npc)
HU_GUN_MAP = {
    'AK47': 'ak47wi',
    'AK74': 'ak74i30',
    'AK74GL': 'ak74i30_gp25',
    'AKS74U': 'aks74uw30',
    'AN94': 'an94',
    'AN94-GP25': 'an94_gp25',
    'AT4': 'at4',
    'BIZON': 'bizon9x18',
    'DEGTYAREV': 'dpm',
    'DRAGUNOV': 'dragunov',
    'FN-FAL': 'fal5000i',
    'G36': 'g36k',
    'G3A3': 'g3a3',
    'GLFOROICW': 'oicwhe_oicwke',
    'GP25': 'gp25_ak74i30',
    'GP25_FOR_AN94': 'gp25_an94',
    'GP25_FOR_GROZA': 'gp25_groza',
    'GROZA': 'groza',
    'HK4': 'hk4380acp',
    'L96A1': 'l96a1',
    'M16': 'm16a4rfx',
    'M16GL': 'm16a4rfx_m203',
    'M1911': 'm1911',
    'M203': 'm203_m16a4rfx',
    'M24': 'm24sws',
    'M240': 'm240b',
    'M249': 'm249saw',
    'M4': 'm4a1i',
    'M60': 'm60',
    'M82BARRET': 'm82a1',
    'M9': 'm9pistol',
    'M98': 'm98',
    'M9SD': 'm9pistolsd',
    'MAKAROV': 'makarov',
    'MG3': 'mg3gpmg',
    'MM1': 'mm1',
    'MP5': 'mp5a4i',
    'MP5SD': 'mp5sd6i',
    'OICW': 'oicwke',
    'OICWGL': 'oicwke_oicwhe',
    'PKM': 'pkmi',
    'PLAYER_AK47': 'ak47wi',
    'PLAYER_AK74': 'ak74i30',
    'PLAYER_AK74GL': 'ak74i30_gp25',
    'PLAYER_GP25': 'gp25_ak74i30',
    'PSG1': 'psg1a1',
    'RP46': 'rp46',
    'RPG7': 'rpg7',
    'RPK74': 'rpk74i',
    'SA25': 'sa25',
    'SA80': 'sa80l85',
    'SOPMODM4': 'm4a1m68',
    'SR25': 'sr25m',
    'SR25SD': 'sr25msd',
    'VZ58': 'vz58',
}
#: the mapped guns each disc actually has
HU_GAME_GUNS = {
    'gr': ['AK47', 'AK74', 'AK74GL', 'AKS74U', 'AN94', 'AN94-GP25', 'AT4', 'BIZON', 'DRAGUNOV', 'FN-FAL', 'G36', 'G3A3', 'GLFOROICW', 'GP25', 'GP25_FOR_AN94', 'GP25_FOR_GROZA', 'GROZA', 'L96A1', 'M16', 'M16GL', 'M1911', 'M203', 'M24', 'M249', 'M4', 'M60', 'M82BARRET', 'M9', 'M98', 'M9SD', 'MG3', 'MP5', 'MP5SD', 'OICW', 'OICWGL', 'PKM', 'PSG1', 'RPG7', 'RPK74', 'SA80'],
    'js': ['AK47', 'AK74', 'AK74GL', 'AKS74U', 'AN94', 'AN94-GP25', 'AT4', 'BIZON', 'DEGTYAREV', 'DRAGUNOV', 'FN-FAL', 'G36', 'G3A3', 'GLFOROICW', 'GP25', 'GP25_FOR_AN94', 'GP25_FOR_GROZA', 'GROZA', 'HK4', 'L96A1', 'M16', 'M16GL', 'M1911', 'M203', 'M24', 'M240', 'M249', 'M4', 'M60', 'M82BARRET', 'M9', 'M98', 'M9SD', 'MAKAROV', 'MG3', 'MM1', 'MP5', 'MP5SD', 'OICW', 'OICWGL', 'PKM', 'PLAYER_AK47', 'PLAYER_AK74', 'PLAYER_AK74GL', 'PLAYER_GP25', 'PSG1', 'RP46', 'RPG7', 'RPK74', 'SA25', 'SA80', 'SOPMODM4', 'SR25', 'SR25SD', 'VZ58'],
}
#: files only the AI carries: always the AI numbers
HU_AI_ONLY = {'gr': [], 'js': ['AK47', 'AK74', 'AK74GL', 'GP25']}


def _round_text(text: str, sig) -> str:
    """HU's number rounded to `sig` significant digits, plain decimal (no exponent); as-is for None."""
    if sig is None:
        return text
    x = float(text)
    if x == 0:
        return "0"
    from math import floor, log10
    decimals = max(0, sig - 1 - int(floor(log10(abs(x)))))
    s = "%.*f" % (decimals, x)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fitted_values(base: str, flavour: str, sig=None, dropped=()) -> dict:
    """HU's values for one gun, rounded and thinned as a slot fit requires."""
    return {k: _round_text(v, sig) for k, v in HU_GUNS[base][flavour].items() if k not in dropped}


def weapons_choice(prefix: str, v: dict) -> str:
    """'off', 'you' or 'ai': whose HU numbers the shared guns take."""
    w = v.get(prefix + "hu_weapons", "off")
    if w == "off" and v.get(prefix + "hu_all"):
        w = "you"
    return w


def data_edits(prefix: str, v: dict) -> list:
    out = []
    game = prefix[:2]
    w = weapons_choice(prefix, v)
    if w != "off":
        for name in HU_GAME_GUNS[game]:
            base = HU_GUN_MAP[name]
            flavour = "ai" if name in HU_AI_ONLY.get(game, ()) else ("player" if w == "you" else "ai")
            if game == "js" and name.startswith("PLAYER_"):
                flavour = "player"
            # Jungle Storm loads the compiled .XBG, never the .GUN (see xbg_fields)
            op, ext = ("hu_xbg", "XBG") if game == "js" else ("hu_values", "GUN")
            out.append(FileEdit(op, r"/%s\.%s$" % (re.escape(name), ext), "GR.IMG",
                                {"values": HU_GUNS[base][flavour]},
                                "Heroes Unleashed %s (%s numbers)" % (base, "AI" if flavour == "ai" else "player")))
    if on(prefix, v, "damage"):
        # not pinned to one archive: Ghost Recon ships CMBTMODL.XML twice and both copies must agree
        out.append(FileEdit("xml_values", r"/CMBTMODL\.XML$", "", {"values": HU_COMBAT_MODEL},
                            "Heroes Unleashed damage model"))
    if on(prefix, v, "skills"):
        out.append(FileEdit("bump_stats", r"\.ATR$", "GR.IMG", {"steps": -2, "stats": ["Weapon"]},
                            "Heroes Unleashed: hostile marksmanship -2", scope="enemy_templates"))
    return out
