"""Unreal-style `.ini` editing that gives the file back the way it found it.

Both Unreal games here configure through `.ini`, and `configparser` is the
wrong tool for them three times over:

* **Duplicate keys are meaningful.** Unreal reads a repeated key as an array
  (`Paths=`, `EditPackages=`, `ServerActors=`). `configparser` keeps the last
  one and silently deletes the rest of the list.
* **The formatting is data.** These files carry comments, blank-line grouping
  and a fixed key order that a person reads. `configparser` rewrites the whole
  file in its own shape, so a one-key change comes back as a total rewrite and
  a diff nobody can review.
* **Vegas writes floats with a decimal COMMA** -- ``m_fSuppressorDamageModifier=0,8``
  is eight tenths, not a two-element list. Anything that parses it as a number
  and prints it back will write ``0.8`` and change the meaning.

So this is a line-oriented editor. The file is held as its original lines; a
write replaces the one line it is changing and leaves every other byte alone.

Line endings, the byte encoding and any BOM are recorded on load and restored
on save, so a file that arrived as CRLF/cp1252 leaves as CRLF/cp1252.
"""

from __future__ import annotations

import os
import re

#: Unreal ships these as 8-bit text. cp1252 round-trips every byte 0x00-0xFF
#: to a character and back, so even a stray byte survives an edit untouched;
#: utf-8 would raise on it and latin-1 would mangle the 0x80-0x9F range that
#: the localisation files really do use.
ENCODINGS = ("utf-8-sig", "cp1252")

#: Byte-order marks, longest first so UTF-32 is not mistaken for UTF-16.
#:
#: A UTF-16 file has to be recognised BEFORE the 8-bit fallback gets a look at
#: it, because cp1252 will decode it perfectly happily -- every byte maps to
#: some character -- and the result is a string full of NULs whose line
#: structure is nonsense. Advanced Warfighter 2 ships one, under
#: `Support\Detection\`, and it was the round-trip check that found it.
BOMS = {
    "utf-32-le": b"\xff\xfe\x00\x00",
    "utf-32-be": b"\x00\x00\xfe\xff",
    "utf-8": b"\xef\xbb\xbf",
    "utf-16-le": b"\xff\xfe",
    "utf-16-be": b"\xfe\xff",
}

#: line terminators, longest first (used by `_split`)
ENDINGS = ("\r\n", "\n", "\r")


def decode(raw: bytes, path=""):
    """(text, encoding, bom) for a file of unknown flavour."""
    for enc, mark in BOMS.items():
        if raw.startswith(mark):
            try:
                return raw[len(mark):].decode(enc), enc, mark
            except UnicodeDecodeError:            # pragma: no cover
                break
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), ("utf-8" if enc == "utf-8-sig" else enc), b""
        except UnicodeDecodeError:
            continue
    raise IniError("Could not decode %s" % (path or "the file"))


def _split(text):
    """(lines without terminators, the terminator that followed each).

    The last entry's terminator is empty when the file did not end with one,
    so joining the two lists back together reproduces the input exactly.
    """
    lines, ends, start, i = [], [], 0, 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\r":
            end = "\r\n" if text[i + 1:i + 2] == "\n" else "\r"
        elif ch == "\n":
            end = "\n"
        else:
            i += 1
            continue
        lines.append(text[start:i])
        ends.append(end)
        i += len(end)
        start = i
    if start < n or not lines:
        lines.append(text[start:])
        ends.append("")
    return lines, ends


SECTION_RX = re.compile(r"^\s*\[(?P<name>[^\]]*)\]\s*$")
# A key line. Unreal also accepts +Key=, -Key=, .Key= and !Key= prefixes for
# array manipulation, so the prefix is captured rather than treated as part of
# the name.
KEY_RX = re.compile(r"^(?P<lead>\s*)(?P<prefix>[+\-.!]?)(?P<key>[^=;\[\]]+?)"
                    r"(?P<pad>\s*)=(?P<value>.*)$")


class IniError(Exception):
    pass


class Ini:
    """One `.ini`, held as lines, edited in place."""

    def __init__(self, text: str, newline: str = "\r\n", encoding: str = "cp1252",
                 bom: bytes = b"", path: str = ""):
        self.newline = newline
        self.encoding = encoding
        #: the byte-order mark the file arrived with, replayed verbatim
        self.bom = bom if isinstance(bom, bytes) else (BOMS["utf-8"] if bom else b"")
        self.path = path
        #: Each line WITHOUT its terminator, with the terminators kept beside
        #: them in `ends`. Not normalised to "\n" and rejoined on save, which
        #: is the obvious approach and is wrong: it silently rewrites a lone
        #: carriage return as a line feed. One of these installs really does
        #: ship such a file, and the round-trip check caught it.
        self.lines, self.ends = _split(text)

    # -- loading and saving ------------------------------------------------

    @classmethod
    def load(cls, path) -> "Ini":
        with open(path, "rb") as fh:
            raw = fh.read()
        text, encoding, bom = decode(raw, path)
        # Which ending dominates decides what a NEW line gets. A file that is
        # already mixed stays mixed for the lines we do not touch, because only
        # the changed line is rewritten.
        crlf = text.count("\r\n")
        newline = "\r\n" if crlf >= text.count("\n") - crlf else "\n"
        return cls(text, newline=newline, encoding=encoding, bom=bom,
                   path=str(path))

    def text(self) -> str:
        return "".join(line + end for line, end in zip(self.lines, self.ends))

    def to_bytes(self) -> bytes:
        return self.bom + self.text().encode(self.encoding, errors="replace")

    @property
    def trailing_newline(self) -> bool:
        """Did the file end with a line terminator?"""
        return bool(self.ends) and bool(self.ends[-1])

    def save(self, path=None):
        path = str(path or self.path)
        if not path:
            raise IniError("No path to save to")
        tmp = path + ".tcms-tmp"
        with open(tmp, "wb") as fh:
            fh.write(self.to_bytes())
        os.replace(tmp, path)

    # -- reading -----------------------------------------------------------

    def sections(self) -> list:
        out = []
        for line in self.lines:
            m = SECTION_RX.match(line)
            if m:
                out.append(m.group("name"))
        return out

    def _section_span(self, section):
        """(first line index inside the section, index just past its last line).

        Returns None when the section is not there. A section runs to the next
        `[header]` or to end of file. Unreal tolerates the same section
        appearing twice; the FIRST one wins on read, so that is the one used.

        An EMPTY section name means the keys before the first `[header]`, which
        is how Raven Shield's AI templates are written -- `template\\*.tpt` is
        224 files of bare `Assault=80` with no section line anywhere in them.
        They are otherwise exactly this format, so they are read and written by
        this class rather than by a second parser that would have to make all
        the same decisions about whitespace and line endings again.
        """
        if not str(section).strip():
            for i, line in enumerate(self.lines):
                if SECTION_RX.match(line):
                    return 0, i
            return 0, len(self.lines)
        want = section.strip().lower()
        start = None
        for i, line in enumerate(self.lines):
            m = SECTION_RX.match(line)
            if not m:
                continue
            if start is not None:
                return start, i
            if m.group("name").strip().lower() == want:
                start = i + 1
        if start is None:
            return None
        return start, len(self.lines)

    def _key_lines(self, section, key) -> list:
        """Every line index in `section` that assigns `key`, in file order."""
        span = self._section_span(section)
        if span is None:
            return []
        want = key.strip().lower()
        hits = []
        for i in range(span[0], span[1]):
            m = KEY_RX.match(self.lines[i])
            if m and m.group("key").strip().lower() == want:
                hits.append(i)
        return hits

    def get(self, section, key, default=None):
        """The value of `key` as the game would read it -- the LAST assignment.

        Unreal applies a config file top to bottom, so a key written twice ends
        up holding the second value. Reading the first would report a number
        the game never uses.
        """
        hits = self._key_lines(section, key)
        if not hits:
            return default
        return KEY_RX.match(self.lines[hits[-1]]).group("value").strip()

    def get_all(self, section, key) -> list:
        """Every assignment of `key`, for the keys Unreal treats as arrays."""
        return [KEY_RX.match(self.lines[i]).group("value").strip()
                for i in self._key_lines(section, key)]

    def has(self, section, key) -> bool:
        return bool(self._key_lines(section, key))

    # -- writing -----------------------------------------------------------

    def set(self, section, key, value, absent="add") -> str:
        """Write `key`. Returns "changed", "same", "added" or "absent".

        Only the assignment line is touched; its leading whitespace and the
        padding around the `=` are kept, so a file that aligns its values stays
        aligned. When the key appears more than once the LAST one is rewritten
        and the earlier ones are left, matching what the game reads.
        """
        text = _fmt(value)
        hits = self._key_lines(section, key)
        if hits:
            i = hits[-1]
            m = KEY_RX.match(self.lines[i])
            if m.group("value").strip() == text:
                return "same"
            self.lines[i] = "%s%s%s%s=%s" % (m.group("lead"), m.group("prefix"),
                                             m.group("key"), m.group("pad"), text)
            return "changed"
        if absent == "error":
            raise IniError("[%s] %s is not in %s"
                           % (section, key, os.path.basename(self.path)))
        if absent != "add":
            return "absent"
        span = self._section_span(section)
        if span is None:
            # A brand new section goes at the end, preceded by a blank line
            # unless the file already ends with one.
            if self.lines and self.lines[-1].strip():
                self._append("")
            self._append("[%s]" % section)
            self._append("%s=%s" % (key, text))
            return "added"
        # Insert after the section's last non-blank line rather than at its
        # very end, so the new key joins the block instead of drifting below
        # the blank line that separates this section from the next.
        at = span[1]
        while at > span[0] and not self.lines[at - 1].strip():
            at -= 1
        self._insert(at, "%s=%s" % (key, text))
        return "added"

    def get_field(self, section, key, field, default=None):
        """One field out of an Unreal struct literal.

        Raven Shield's whole AI hearing model is five of these::

            m_Rainbow=(fStandSlow=300.000000,fStandFast=800.000000,...)

        so "how far the AI hears you walking" is not a key, it is a field
        inside one. Treating the value as opaque would mean rewriting all five
        numbers to change one of them.
        """
        raw = self.get(section, key)
        if raw is None:
            return default
        m = _field_rx(field).search(raw)
        return m.group("value") if m else default

    def set_field(self, section, key, field, value) -> str:
        """Rewrite one field of a struct literal, leaving the others alone."""
        hits = self._key_lines(section, key)
        if not hits:
            return "absent"
        i = hits[-1]
        m = KEY_RX.match(self.lines[i])
        raw = m.group("value")
        fm = _field_rx(field).search(raw)
        if fm is None:
            return "absent"
        new = str(value)
        if fm.group("value") == new:
            return "same"
        raw = raw[:fm.start("value")] + new + raw[fm.end("value"):]
        self.lines[i] = "%s%s%s%s=%s" % (m.group("lead"), m.group("prefix"),
                                         m.group("key"), m.group("pad"), raw)
        return "changed"

    def _append(self, line):
        """Add a line at the end, giving the file a terminator if it lacked one.

        A file that did not end with a newline gets one now, because the line
        being appended has to start on a line of its own -- that is the single
        place where this class changes a byte it was not asked to.
        """
        if self.ends and not self.ends[-1]:
            self.ends[-1] = self.newline
        self.lines.append(line)
        self.ends.append(self.newline)

    def _insert(self, at, line):
        self.lines.insert(at, line)
        self.ends.insert(at, self.newline)

    def rename_section(self, old, new) -> str:
        """Rewrite a section header, keeping everything under it in place.

        Only needed for a shipped typo: Vegas names the Raging Bull's damage
        type `R6DmgTypePistoRagingBull` where the class in `R6Game.uppc` is
        `R6DmgTypePistolRagingBull`, so that whole section is read by nothing.
        """
        want = str(old).strip().lower()
        for i, line in enumerate(self.lines):
            m = SECTION_RX.match(line)
            if m and m.group("name").strip().lower() == want:
                self.lines[i] = line[:m.start("name")] + new                     + line[m.end("name"):]
                return "changed"
        return "absent"

    def remove(self, section, key) -> int:
        """Delete every assignment of `key`. Returns how many went."""
        hits = self._key_lines(section, key)
        for i in reversed(hits):
            del self.lines[i]
            del self.ends[i]
        return len(hits)

    # -- array keys --------------------------------------------------------
    #
    # Unreal reads some keys as a LIST, by assigning them once per element:
    #
    #     m_szGameTypes="RGM_StoryMode"
    #     m_szGameTypes="RGM_PracticeMode"
    #
    # `set` is wrong for those -- it rewrites the last line, which changes one
    # element instead of adding one. These three work on the list as a whole.
    # All of them are idempotent, which matters because every apply rebuilds
    # from pristine and then runs the same edits again.

    def add_line(self, section, key, value) -> str:
        """Ensure one `key=value` line exists, comparing ignoring case.

        Added immediately after the last existing element so the list stays
        together, rather than at the end of the section where it would be
        separated from its own kind by whatever sits between.
        """
        value = _fmt(value)
        hits = self._key_lines(section, key)
        want = value.strip().lower()
        for i in hits:
            if KEY_RX.match(self.lines[i]).group("value").strip().lower() == want:
                return "same"
        line = "%s=%s" % (key, value)
        if hits:
            self._insert(hits[-1] + 1, line)
            return "added"
        span = self._section_span(section)
        if span is None:
            self._append("[%s]" % section)
            self._append(line)
            return "added"
        self._insert(span[1], line)
        return "added"

    def remove_line(self, section, key, value) -> str:
        """Delete the `key=value` lines whose value matches, ignoring case."""
        want = _fmt(value).strip().lower()
        hits = [i for i in self._key_lines(section, key)
                if KEY_RX.match(self.lines[i]).group("value").strip().lower()
                == want]
        for i in reversed(hits):
            del self.lines[i]
            del self.ends[i]
        return "changed" if hits else "same"

    def substitute(self, section, key, old, new) -> int:
        """Replace the literal text `old` inside every `key=` line's VALUE.

        For an element that is a struct with many fields, where only one field
        is wrong and the rest differ from line to line -- a map's
        `SkinsPerGameTypes=(package=...,type=...,green=...,red=...)` names the
        game class alongside four character classes that are different on every
        map, so there is no whole value to match on. Returns how many lines
        changed.
        """
        n = 0
        for i in self._key_lines(section, key):
            m = KEY_RX.match(self.lines[i])
            value = m.group("value")
            if old not in value:
                continue
            self.lines[i] = (self.lines[i][:m.start("value")]
                             + value.replace(old, new)
                             + self.lines[i][m.end("value"):])
            n += 1
        return n

    def replace_line(self, section, key, old, new) -> str:
        """Rewrite the element equal to `old` as `new`, keeping its position.

        Position matters here: Raven Shield's map files list the game modes in
        menu order, so removing and re-adding would silently reorder the menu.
        """
        want = _fmt(old).strip().lower()
        done = False
        for i in self._key_lines(section, key):
            m = KEY_RX.match(self.lines[i])
            if m.group("value").strip().lower() != want:
                continue
            self.lines[i] = self.lines[i][:m.start("value")] + _fmt(new) \
                + self.lines[i][m.end("value"):]
            done = True
        return "changed" if done else "same"


_FIELD_CACHE = {}


def _field_rx(field):
    """Matches `name=value` inside a struct literal, up to the next comma
    or the closing bracket.

    The lookbehind matters: these field names nest inside one another --
    `(fStandSlow=300,fCrouchSlow=200,...)` -- so a bare search for "Slow"
    would match inside both, and a search for one that happens to be a
    suffix of another would find the wrong number.
    """
    rx = _FIELD_CACHE.get(field)
    if rx is None:
        rx = _FIELD_CACHE[field] = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(str(field))
            + r"\s*=\s*(?P<value>[^,)]*)", re.I)
    return rx


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # Enough digits to round-trip a single-precision float, without the
        # trailing zeroes that make a one-key diff look like a rewrite.
        return ("%.6f" % value).rstrip("0").rstrip(".") or "0"
    return str(value)


# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------

def parse_number(text):
    """A float from an Unreal ini value, decimal point OR decimal comma.

    Vegas's config was written by a build running under a European locale and
    every float in it is spelled `0,8`. Nothing else in the file uses a comma
    as a separator -- the array-valued keys use `(A=1,B=2)` parenthesised
    syntax -- so a bare `digits,digits` is unambiguous.

    Returns None for anything that is not a number, which is how a caller tells
    `m_fAccuracyMultiplier=1,5` from `m_bAllowAutoAim=true`.
    """
    s = str(text).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    if re.fullmatch(r"[+-]?\d+,\d+", s):
        try:
            return float(s.replace(",", "."))
        except ValueError:                                # pragma: no cover
            return None
    return None


def format_number(value, like: str) -> str:
    """`value` spelled the way `like` was spelled.

    Feed it the stock value off the disc and the edit keeps that file's own
    convention: a comma file stays a comma file, and an integer-looking key
    such as `m_iDamageAt0M=35` does not acquire a `.0`.

    An integer-spelled stock value is taken as evidence that the engine field
    behind it IS an integer -- Vegas names them for it, `m_iDamageAt0M` beside
    `m_fAccuracyMultiplier` -- so a scaled value is ROUNDED rather than written
    with a decimal part the field cannot hold. Halving a damage of 35 gives 18,
    not `17.5`, because `17.5` is at best truncated and at worst rejected.
    """
    like = str(like).strip()
    if re.fullmatch(r"[+-]?\d+", like):
        return str(int(round(float(value))))

    # Keep the number of decimal places the file itself used. Unreal writes its
    # floats to six places -- `fSndDist=1100.000000` -- and would read `550`
    # perfectly well, but a file that comes back with its own convention
    # changed is a file nobody can diff against the original. `550.000000` is
    # the same number spelled the way the rest of the line is.
    sep = "," if re.fullmatch(r"[+-]?\d+,\d+", like) else "."
    places = len(like.rsplit(sep, 1)[1]) if sep in like else None
    if places is not None:
        out = "%.*f" % (places, float(value))
    else:
        out = ("%.6f" % float(value)).rstrip("0").rstrip(".") or "0"
    if sep == ",":
        out = out.replace(".", ",")
        if "," not in out:                # keep the file's float-ness visible
            out += ",0"
    return out
