"""Ghost Recon's level ambience, on the Jungle Storm slots.

Two halves, both keyed by NAME and never by index:

  A. the EMITTERS. A mission's `<SoundList>` is the positioned wildlife bed --
     30 entries on a stock Jungle Storm level, 38 on Ghost Recon's M01. The
     port strips all of them because a clip the level's bank cannot resolve
     hangs the load. Put Ghost Recon's back, keeping only the entries whose
     file the SLOT's own bank actually holds.

  B. the SAMPLES. Where both banks carry the same name, write Ghost Recon's
     recording into the slot's entry. No name is added, so nothing can dangle.

The bank a level loads is computed from its NAME by `PS2LoadSoundData`, with
no table anywhere: first letter (and a second 'p') picks a constant, the two
digits are added to it. Confirmed against the data for all 28 pairs.
"""
import os
import re
import struct

JS_RULE = [("tac", None), ("mp", 15), ("dp", 60), ("cp", 73), ("c", 65), ("u", 55), ("g", 89)]
GR_RULE = [("tac", None), ("dp", 60), ("d", 21), ("m", 0)]
TAC = {1: 16, 2: 18, 3: 20, 4: 17, 5: 19}


def bank_of(level_name, rules):
    n = level_name.lower()
    for pre, off in rules:
        if n.startswith(pre):
            if off is None:
                return TAC.get(int(n[3]))
            d = re.match(r"(\d\d)", n[len(pre):])
            return off + int(d.group(1)) if d else None
    return None


def idc_table(blob):
    """{NAME: (bank, index)} out of a 128-bucket, 56-byte-record .IDC."""
    out, body = {}, blob[512:]
    for i in range(len(body) // 56):
        r = body[i * 56:(i + 1) * 56]
        nm = r[:0x2C].split(b"\0")[0].decode("latin-1", "replace").upper()
        _ln, sid, _nx = struct.unpack_from("<III", r, 0x2C)
        if nm:
            out.setdefault(nm, (sid >> 16, sid & 0xFFFF))
    return out


def bank_names(idc, counts, bank):
    """{NAME: index} for the entries of `bank` that the .SH actually has."""
    return {nm: ix for nm, (bk, ix) in idc.items()
            if bk == bank and ix < counts.get(bank, 0)}


def filter_sound_list(mission_text, keep):
    """The mission with `<SoundList>` holding only emitters `keep` resolves.

    Returns (text, kept, dropped). An emitter is a `<Sound ...>` element with
    `<Point>` children; it is kept whole or removed whole.
    """
    m = re.search(r"<SoundList>(.*?)</SoundList>", mission_text, re.S)
    if not m:
        return mission_text, 0, 0
    body, kept, dropped, out, i = m.group(1), 0, 0, [], 0
    while True:
        s = body.find("<Sound", i)
        if s < 0:
            out.append(body[i:])
            break
        out.append(body[i:s])
        close = body.find(">", s)
        if close != -1 and body[close - 1] == "/":
            end = close + 1
        else:
            e = body.find("</Sound>", close)
            end = (e + len("</Sound>")) if e != -1 else close + 1
        chunk = body[s:end]
        f = re.search(r'File\s*=\s*"([^"]*)"', chunk)
        if f and os.path.basename(f.group(1)).upper() in keep:
            out.append(chunk)
            kept += 1
        else:
            dropped += 1
        i = end
        while i < len(body) and body[i] in "\r\n\t ":
            i += 1
        out.append("\n\t\t")
    return (mission_text[:m.start(1)] + "".join(out) + mission_text[m.end(1):],
            kept, dropped)
