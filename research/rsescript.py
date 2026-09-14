#!/usr/bin/env python3
"""
rsescript.py - the <ScriptSource> / <ScriptCompiled> payload inside Ghost Recon
PS2 and Ghost Recon Jungle Storm PS2 .MIS and .GTF files.

TRANSPORT: an "A..P" nibble encoding, NOT base64.
  Every payload byte becomes two ASCII characters in 'A'..'P'.
  LOW nibble first:
      byte = (c0 - 'A') | ((c1 - 'A') << 4)
  So "PDEFIGFGACAFJGMGPGEHACEEJGFGEG" -> "?The Pilot Died".
  The encoding is fixed-width, so an edit that keeps the payload byte length
  keeps the XML text length too.

VARIABLE TABLE: the payload opens with the script's variable table, which is
where the designer-named tuning numbers live.

      u32   variableCount
      u32   (1 on every file seen)
      u32   (2 on every file seen)
      then variableCount records, each:
          u32   nameLen
          char  name[nameLen]        (no NUL terminator)
          u32   value                <-- the editable number. It is a UNION:
                                     read it as an int for counts, as an IEEE
                                     float for durations/ranges. e.g.
                                     1133903872 == 0x43960000 == 300.0f
                                     ("Proximity start time"), while
                                     30 is a plain int ("Recruit enemy count").
                                     Rule of thumb: any value above ~1e8 is a
                                     float bit pattern.
          u32   id                   (script node reference id, ascending)
          u32   0

  Worked example, (SP) DEFEND.GTF from Jungle Storm:
      0D 00 00 00   13 variables
      01 00 00 00
      02 00 00 00
      09 00 00 00 "Lose Text"            value 8    id 2
      13 00 00 00 "Recruit enemy count"  value 20   id 3
      13 00 00 00 "Veteran enemy count"  value 25   id 4
      11 00 00 00 "Elite enemy count"    value 35   id 7
      15 00 00 00 "Proximity shrink rate" value 10  id 8
      0C 00 00 00 "Capture time"         value 11   id 9

  The same file in (COOP) DEFEND.GTF carries 30 / 40 / 50 instead.

WHAT COMES AFTER the variable table is the compiled node graph. This module
does NOT decode the node graph; it only reads the variable table and harvests
printable strings (which include every designer node comment, e.g.
"01a: Spawn enemies (recruit)"). See FORMATS.md for what is and is not known.
"""

import re
import struct

_APONLY = re.compile(r'[^A-P]')


def ap_decode(text):
    """A..P nibble text -> bytes."""
    s = _APONLY.sub('', text)
    out = bytearray()
    for i in range(0, len(s) - 1, 2):
        out.append((ord(s[i]) - 65) | ((ord(s[i + 1]) - 65) << 4))
    return bytes(out)


def ap_encode(data):
    """bytes -> A..P nibble text (inverse of ap_decode)."""
    return ''.join(chr(65 + (b & 15)) + chr(65 + (b >> 4)) for b in data)


def scripts(xml_text):
    """Yield (tagName, decodedBytes) for each script blob in a .MIS/.GTF."""
    for tag in ("ScriptCompiled", "ScriptSource"):
        for m in re.finditer("<%s>(.*?)</%s>" % (tag, tag), xml_text, re.S):
            yield tag, ap_decode(m.group(1))


def variables(payload):
    """Parse the leading variable table. Returns [(name, value, id), ...].
    Returns [] if the table does not parse cleanly."""
    if len(payload) < 12:
        return []
    count, _one, _two = struct.unpack_from("<III", payload, 0)
    if not (0 < count < 4096):
        return []
    out, o = [], 12
    for _ in range(count):
        if o + 4 > len(payload):
            return out
        (ln,) = struct.unpack_from("<I", payload, o); o += 4
        if ln > 512 or o + ln + 12 > len(payload):
            return out
        name = payload[o:o + ln].decode("latin1"); o += ln
        val, vid, _z = struct.unpack_from("<III", payload, o); o += 12
        out.append((name, val, vid))
    return out


def as_float(value):
    """Reinterpret a variable's u32 value as an IEEE float."""
    return struct.unpack("<f", struct.pack("<I", value))[0]


def pretty(value):
    """Render a variable value the way it is most likely meant."""
    if value > 100000000:
        return "%g (float)" % as_float(value)
    return str(value)


def comments(payload, minlen=5):
    """Every printable run in the payload. These are the designer's node names
    and comments; they are the fastest way to find the spawn/wave logic."""
    return [m.group(0).decode("latin1")
            for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, payload)]


if __name__ == "__main__":
    import sys
    txt = open(sys.argv[1], encoding="latin1").read()
    for tag, pay in scripts(txt):
        print("== %s (%d bytes)" % (tag, len(pay)))
        for name, val, vid in variables(pay):
            print("   %-42s = %-14s (id %d)" % (name, pretty(val), vid))
