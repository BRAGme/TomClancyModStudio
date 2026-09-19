"""Red Storm's pseudo-XML, edited one value at a time without reformatting.

Every data file in Ghost Recon, Sum of All Fears and Lockdown is angle-bracket
text, in two dialects:

  *element* -- Ghost Recon and Sum of All Fears. The value is the element's
  text::

      <ActorFile>
          <ArmorLevel>2</ArmorLevel>
          <Stealth>3</Stealth>
          <FolderName/>
      </ActorFile>

  *attribute* -- Lockdown. The value is an attribute, and the attributes are
  laid out one per line with spaces around the ``=``::

      <GunFile
          version = "4">
          <Common
              name = "WPN_AN-94"
              isPrimary = "1">

It looks like XML and it very nearly is, but it is not read by an XML parser at
the other end -- Red Storm's loader is hand-rolled -- so this module does NOT
round-trip through `ElementTree`. Doing that would re-quote, re-indent and
re-order the whole file to satisfy a standard nothing here follows, turning a
one-number change into a total rewrite that cannot be reviewed and might not
load. Instead the document is held as its original text and an edit replaces
exactly the span of the value, leaving every other byte, the CRLF endings and
the tab indentation untouched.

Paths are matched by SUFFIX: ``"Common/UIData"`` finds
``GunFile/Common/UIData``, so a profile does not have to spell out the levels
above the one it cares about. A bare name matches at any depth.
"""

from __future__ import annotations

import os
import fnmatch
import re

ENCODINGS = ("utf-8-sig", "cp1252")

#: an opening, closing or self-closing tag. The body is captured whole so the
#: attributes can be picked out of it without a second pass over the file.
TAG_RX = re.compile(r"<(?P<close>/?)(?P<name>[A-Za-z_][\w.\-]*)(?P<body>(?:[^>\"]|\"[^\"]*\")*)>",
                    re.S)
ATTR_RX = re.compile(r"(?P<name>[A-Za-z_][\w.\-]*)(?P<pad>\s*=\s*)\"(?P<value>[^\"]*)\"")
COMMENT_RX = re.compile(r"<!--.*?-->", re.S)


class RseXmlError(Exception):
    pass


class Node:
    __slots__ = ("name", "path", "attrs", "text_span", "self_closing", "tag_span")

    def __init__(self, name, path, attrs, tag_span, self_closing):
        self.name = name
        self.path = path
        #: name -> (value, start, end) of the value INSIDE the quotes
        self.attrs = attrs
        self.tag_span = tag_span
        self.self_closing = self_closing
        #: (start, end) of the element's text, or None for a self-closing one
        self.text_span = None

    def __repr__(self):                                   # pragma: no cover
        return "<Node %s>" % self.path


class Doc:
    """One Red Storm data file."""

    def __init__(self, text, newline="\r\n", encoding="cp1252", bom=False,
                 path=""):
        self.newline = newline
        self.encoding = encoding
        self.bom = bom
        self.path = str(path)
        self._text = text
        self._nodes = None

    # -- loading and saving ------------------------------------------------

    @classmethod
    def load(cls, path) -> "Doc":
        with open(path, "rb") as fh:
            raw = fh.read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text, encoding = None, "cp1252"
        for enc in ENCODINGS:
            try:
                text = raw.decode(enc)
                encoding = "utf-8" if enc == "utf-8-sig" else enc
                break
            except UnicodeDecodeError:
                continue
        if text is None:                                  # pragma: no cover
            raise RseXmlError("Could not decode %s" % path)
        newline = "\r\n" if "\r\n" in text else "\n"
        return cls(text, newline=newline, encoding=encoding, bom=bom, path=path)

    @property
    def text(self):
        return self._text

    def to_bytes(self) -> bytes:
        raw = self._text.encode(self.encoding, errors="replace")
        return (b"\xef\xbb\xbf" + raw) if self.bom else raw

    def save(self, path=None):
        path = str(path or self.path)
        if not path:
            raise RseXmlError("No path to save to")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tcms-tmp"
        with open(tmp, "wb") as fh:
            fh.write(self.to_bytes())
        os.replace(tmp, path)

    # -- parsing -----------------------------------------------------------

    @property
    def nodes(self) -> list:
        if self._nodes is None:
            self._nodes = self._parse()
        return self._nodes

    def _parse(self) -> list:
        text = self._text
        blanked = COMMENT_RX.sub(lambda m: " " * (m.end() - m.start()), text)
        out, stack = [], []
        # An open tag whose element has text needs to know where that text
        # ends, which is only known when the matching close tag turns up. So
        # open nodes are parked on a stack and finished on the way back out.
        open_nodes = {}
        for m in TAG_RX.finditer(blanked):
            name, body = m.group("name"), m.group("body")
            if m.group("close"):
                # Tolerate a stray close tag rather than raising: these files
                # are hand-authored and one bad one must not stop an apply.
                if stack and stack[-1].lower() == name.lower():
                    stack.pop()
                    node = open_nodes.pop(len(stack), None)
                    if node is not None:
                        node.text_span = (node.tag_span[1], m.start())
                continue
            self_closing = body.rstrip().endswith("/")
            path = "/".join(stack + [name])
            attrs = {}
            for a in ATTR_RX.finditer(body):
                # offsets are relative to the whole document
                base = m.start() + len("<") + len(m.group("close")) + len(name)
                attrs[a.group("name")] = (a.group("value"),
                                          base + a.start("value"),
                                          base + a.end("value"))
            node = Node(name, path, attrs, (m.start(), m.end()), self_closing)
            out.append(node)
            if not self_closing:
                open_nodes[len(stack)] = node
                stack.append(name)
        return out

    # -- finding -----------------------------------------------------------

    def find(self, path) -> list:
        """Every node whose path ends with `path`, case-insensitively.

        ANY segment may carry a predicate, `tag[attr=value]`, which is what
        makes Advanced Warfighter addressable at all. Its weapon files do not
        name their fields with elements; they are a flat list of
        ``<var name="spread_normal" value="1.87"/>``, so "the normal spread"
        is not an element path -- it is the element whose `name` attribute
        says so. `weapon_data/var[name=spread_normal]` picks that one out.

        A predicate on an EARLIER segment is what lets one side of a game be
        addressed without the other. Advanced Warfighter declares every weapon
        twice in the same file -- `scar_light` for the human and
        `scar_light_3rd` for everything the AI carries -- so the player's
        spread and the AI's are two elements with the same name, in the same
        file, told apart only by which `<unit>` they sit inside.
        `unit[name=*_3rd]/var[name=spread_normal]` is that question.

        A predicate value may use `*` as a wildcard, which is the only way to
        say "every AI weapon" without listing all twenty-one of them.
        """
        want = [p for p in str(path).replace("\\", "/").split("/") if p]
        if not want:
            return []
        parsed = [_predicate(w) for w in want]
        tail = "/".join(tag.lower() for tag, _k, _v in parsed)
        hits = [(i, n) for i, n in enumerate(self.nodes)
                if n.path.lower() == tail or n.path.lower().endswith("/" + tail)]
        if all(k is None for _t, k, _v in parsed):
            return [n for _i, n in hits]
        out = []
        for index, node in hits:
            chain = self._ancestors(index, len(parsed) - 1) + [node]
            if len(chain) != len(parsed):
                continue
            if all(_matches(c, k, v) for c, (_t, k, v) in zip(chain, parsed)):
                out.append(node)
        return out

    def _ancestors(self, index, count):
        """The `count` enclosing elements of `self.nodes[index]`, outermost
        first.

        Node order is document order and `path` carries the depth, so the
        parent of a node is the nearest PRECEDING node whose path is its
        path minus the last segment. Siblings share a path string, which is
        why this walks backwards from the node rather than searching by path.
        """
        if count <= 0:
            return []
        node = self.nodes[index]
        parts = node.path.split("/")
        out = []
        depth = len(parts) - 1
        i = index - 1
        while i >= 0 and len(out) < count and depth >= 1:
            want = "/".join(parts[:depth])
            if self.nodes[i].path == want:
                out.append(self.nodes[i])
                depth -= 1
            i -= 1
        out.reverse()
        return out

    def first(self, path):
        hits = self.find(path)
        return hits[0] if hits else None

    # -- reading -----------------------------------------------------------

    def get_attr(self, path, attr, default=None):
        """The attribute's value on the FIRST matching element.

        See `any_attr` for why the first is not always the right question.
        """
        node = self.first(path)
        if node is None:
            return default
        hit = _attr_ci(node, attr)
        return hit[0] if hit else default

    def any_attr(self, path, attr, default=None):
        """The value on the first matching element that HAS the attribute.

        Not the same question as `get_attr`, and the difference is not
        academic. Ghost Recon's `m07_river.mis` holds seventeen `<Alertness>`
        elements of which three declare no `State` at all -- and one of those
        three comes first. Asking only the first element whether the attribute
        exists said "no" and skipped an edit that had fourteen elements to
        write.
        """
        for node in self.find(path):
            hit = _attr_ci(node, attr)
            if hit:
                return hit[0]
        return default

    def get_text(self, path, default=None):
        node = self.first(path)
        if node is None or node.text_span is None:
            return default
        return self._text[node.text_span[0]:node.text_span[1]]

    # -- writing -----------------------------------------------------------

    def set_attr(self, path, attr, value) -> str:
        """Replace this attribute's value in EVERY element the path matches.

        Every, not the first, and that is the whole point. A Lockdown weapon
        file carries the same `<WeaponData>` block once per attachment --
        `Default`, `RedDot`, `Scope`, `HiCapMag`, `Suppressor` -- so writing
        only the first one changes the gun's damage until the player fits a red
        dot sight, at which point it silently reverts. "Damage" means the
        weapon's damage, so it is written to all five.

        Returns "changed", "same" or "absent".
        """
        spans = []
        for node in self.find(path):
            hit = _attr_ci(node, attr)
            if hit is not None:
                spans.append(hit)
        return self._splice_all(spans, str(value))

    def set_text(self, path, value) -> str:
        """Replace the text of every element the path matches.

        A self-closing element (``<FolderName/>``) has no text to replace and
        is skipped rather than silently expanded: expanding it changes the
        shape of the file for no gain, since the loader reads an empty element
        and an absent one the same way.
        """
        spans = []
        for node in self.find(path):
            if node.text_span is None:
                continue
            start, end = node.text_span
            old = self._text[start:end]
            # Only a leaf's text is a value. An element that contains other
            # elements has children in that span, and overwriting it would
            # delete them -- so refuse rather than destroy.
            if "<" in old:
                raise RseXmlError("%s is not a leaf element" % node.path)
            spans.append((old, start, end))
        return self._splice_all(spans, str(value))

    def scale_attr(self, path, attr, factor, offset=None, minimum=None,
                   maximum=None):
        """Multiply this attribute by `factor` in every element it appears in,
        each one starting from ITS OWN value.

        Not the same as reading one value, scaling it, and writing it
        everywhere -- which is what a plain `set_attr` would do and which would
        be wrong here. A rifle's `clipSize` is 30 on the Default variant and
        100 on the HiCapMag one; "half magazines" has to mean 15 and 50, not 15
        and 15, or the option quietly deletes the extended magazine.

        Returns ("changed" | "same" | "absent", how many were written).
        """
        return self._scale(
            [(_attr_ci(n, attr)) for n in self.find(path)], factor, offset,
            minimum, maximum)

    def scale_text(self, path, factor, offset=None, minimum=None,
                   maximum=None):
        """As `scale_attr`, for element text."""
        spans = []
        for node in self.find(path):
            if node.text_span is None:
                continue
            start, end = node.text_span
            old = self._text[start:end]
            if "<" in old:
                raise RseXmlError("%s is not a leaf element" % node.path)
            spans.append((old, start, end))
        return self._scale(spans, factor, offset, minimum, maximum)

    def remap_attr(self, path, attr, table):
        """Rewrite this attribute wherever its current value is in `table`.

        Not a scale and not a constant: each element gets the value its own
        current value maps to, and an element whose value is not in the table
        is left alone. That last part is the point -- it is what keeps a
        blanket edit off the values it was not meant for.
        """
        spans = []
        for node in self.find(path):
            hit = _attr_ci(node, attr)
            if hit is None:
                continue
            old, start, end = hit
            new = table.get(old.strip())
            if new is not None and str(new) != old:
                spans.append((start, end, str(new)))
        if not spans:
            return "same", 0
        for start, end, new in sorted(spans, reverse=True):
            self._text = self._text[:start] + new + self._text[end:]
        self._nodes = None
        return "changed", len(spans)

    def remap_text(self, path, table):
        """As `remap_attr`, for element text."""
        spans = []
        for node in self.find(path):
            if node.text_span is None:
                continue
            start, end = node.text_span
            old = self._text[start:end]
            if "<" in old:
                raise RseXmlError("%s is not a leaf element" % node.path)
            new = table.get(old.strip())
            if new is not None and str(new) != old:
                spans.append((start, end, str(new)))
        if not spans:
            return "same", 0
        for start, end, new in sorted(spans, reverse=True):
            self._text = self._text[:start] + new + self._text[end:]
        self._nodes = None
        return "changed", len(spans)

    def _scale(self, spans, factor, offset, minimum, maximum):
        todo = []
        for hit in spans:
            if hit is None:
                continue
            old, start, end = hit
            num = parse_number(old)
            if num is None:
                continue
            out = num * (1.0 if factor is None else factor)
            if offset is not None:
                out += offset
            if minimum is not None:
                out = max(minimum, out)
            if maximum is not None:
                out = min(maximum, out)
            new = format_number(out, old)
            if new != old:
                todo.append((start, end, new))
        if not spans:
            return "absent", 0
        if not todo:
            return "same", 0
        for start, end, new in sorted(todo, reverse=True):
            self._text = self._text[:start] + new + self._text[end:]
        self._nodes = None
        return "changed", len(todo)

    def _splice_all(self, spans, new):
        """Rewrite every span to `new`, working backwards.

        Backwards because each replacement of a different length moves
        everything after it; taking the highest offset first means the ones
        still to do are all in front of the edit and their offsets still hold.
        """
        if not spans:
            return "absent"
        todo = [(start, end) for old, start, end in spans if old != new]
        if not todo:
            return "same"
        for start, end in sorted(todo, reverse=True):
            self._text = self._text[:start] + new + self._text[end:]
        self._nodes = None       # offsets moved; re-index on next access
        return "changed"

    def _splice(self, start, end, new):
        self._text = self._text[:start] + new + self._text[end:]
        self._nodes = None


PREDICATE_RX = re.compile(
    r"^(?P<tag>[^\[]+)\[(?P<key>[^=!\]]+)(?P<op>!?=)(?P<value>[^\]]*)\]$")


def _matches(node, key, value):
    """Whether `node` satisfies one predicate. `value` may contain `*`.

    A key prefixed `!` is a negation, which `_predicate` encodes that way so
    the parsed triple stays a triple.
    """
    if key is None:
        return True
    negate = key.startswith("!")
    got = (_attr_ci(node, key[1:] if negate else key) or ("",))[0].lower()
    hit = fnmatch.fnmatchcase(got, value.lower())
    return not hit if negate else hit


def _predicate(segment):
    """Split `tag[attr=value]` into its parts, or pass a plain tag.

    `!=` negates, and a value may use `*` as a wildcard. Both exist for one
    job: Advanced Warfighter declares each weapon twice in a file, once for
    the human and once (suffixed `_3rd`) for every AI, so "the player's
    weapons" is `unit[name!=*_3rd]` and there is no other way to say it.
    """
    m = PREDICATE_RX.match(segment.strip())
    if not m:
        return segment, None, None
    key = m.group("key")
    if m.group("op") == "!=":
        key = "!" + key
    return m.group("tag"), key, m.group("value")


def _attr_ci(node, attr):
    want = str(attr).lower()
    for name, hit in node.attrs.items():
        if name.lower() == want:
            return hit
    return None


# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------

def parse_number(text):
    """A float from a Red Storm value, or None if it is not a number."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def format_number(value, like) -> str:
    """`value` spelled the way `like` was spelled.

    These files are inconsistent on purpose-looking grounds -- ``<Stamina>3``
    is bare, ``<VersionNumber>1.000000`` has six places, Lockdown's combat
    model uses three -- and the loader is happy with any of them. Matching the
    stock spelling keeps a diff to the digits that actually changed.

    As in the ini writer, an integer-spelled stock value is taken as evidence
    that the field is an integer, so a scaled value is ROUNDED rather than
    given a decimal part: Ghost Recon's skill stats are 1-5 rungs, and
    ``<Stamina>3.5`` is not a rung.
    """
    like = str(like).strip()
    if re.fullmatch(r"[+-]?\d+", like):
        return str(int(round(float(value))))
    m = re.fullmatch(r"[+-]?\d*\.(\d+)", like)
    if m:
        return "%.*f" % (len(m.group(1)), float(value))
    out = ("%.6f" % float(value)).rstrip("0").rstrip(".")
    return out or "0"
