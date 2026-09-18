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
                 bom: bool = False, path: str = ""):
        self.newline = newline
        self.encoding = encoding
        self.bom = bom
        self.path = path
        #: `text` is split on "\n" after the line endings have been normalised
        #: by `load`, so an index into `lines` is a real line number.
        self.lines = text.split("\n")
        #: True when the original file ended with a newline. Kept so saving
        #: does not add or drop one.
        self.trailing_newline = bool(self.lines) and self.lines[-1] == ""
        if self.trailing_newline:
            self.lines.pop()

    # -- loading and saving ------------------------------------------------

    @classmethod
    def load(cls, path) -> "Ini":
        with open(path, "rb") as fh:
            raw = fh.read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = None
        encoding = "cp1252"
        for enc in ENCODINGS:
            try:
                text = raw.decode(enc)
                encoding = "utf-8" if enc == "utf-8-sig" else enc
                break
            except UnicodeDecodeError:
                continue
        if text is None:                                  # pragma: no cover
            raise IniError("Could not decode %s" % path)
        # Which ending dominates decides what a NEW line gets. A file that is
        # already mixed stays mixed for the lines we do not touch, because only
        # the changed line is rewritten.
        newline = "\r\n" if text.count("\r\n") >= text.count("\n") - text.count("\r\n") \
            else "\n"
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return cls(text, newline=newline, encoding=encoding, bom=bom,
                   path=str(path))

    def text(self) -> str:
        body = self.newline.join(self.lines)
        if self.trailing_newline:
            body += self.newline
        return body

    def to_bytes(self) -> bytes:
        raw = self.text().encode(self.encoding, errors="replace")
        return (b"\xef\xbb\xbf" + raw) if self.bom else raw

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
                self.lines.append("")
            self.lines.append("[%s]" % section)
            self.lines.append("%s=%s" % (key, text))
            return "added"
        # Insert after the section's last non-blank line rather than at its
        # very end, so the new key joins the block instead of drifting below
        # the blank line that separates this section from the next.
        at = span[1]
        while at > span[0] and not self.lines[at - 1].strip():
            at -= 1
        self.lines.insert(at, "%s=%s" % (key, text))
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

    def remove(self, section, key) -> int:
        """Delete every assignment of `key`. Returns how many went."""
        hits = self._key_lines(section, key)
        for i in reversed(hits):
            del self.lines[i]
        return len(hits)


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
