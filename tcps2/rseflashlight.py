"""A dead terrorist's weapon light stays on his gun.

Reported 2026-09-24: a terrorist with a flashlight on his gun dies, and the
flashlight vanishes from the gun.

Why
---

The flashlight is not part of the gun's mesh. `R6Terrorist.CommonInit` calls
`SpawnFlashlight()`, which spawns a separate gadget actor (the body, a static
mesh) and stores it in the gun's `m_FlashlightGadget`; the level's own
`ActivateGadget` pins the body and a glow flare to the gun's gadget tag.

When the terrorist dies, `R6Died` -> `InitDeathAnim` queues pending action 9,
"drop weapon", which `PlaySpecialPendingAction` runs as
`R6Terrorist.DropWeaponToGround` -> `R6Weapons.StartFalling`. And
`StartFalling` opens with::

    if (m_FlashlightGadget != None)       07 1e 00 77 01 ed 01 2a 16
    {
        m_FlashlightGadget.Destroy();     19 01 ed 01 03 00 04 61 17 16
        m_FlashlightGadget = None;        0f 01 ed 01 2a
    }

So it is stock design, the same in single player, split screen and online
(the functions are byte-identical in all three COMMON files). Measured in five
savestates: every living terrorist's gun holds its flashlight, and every dead
one's has `m_FlashlightGadget = None` alongside the death location only
`StartFalling` writes.

What this does
--------------

Two choices, both in `R6Weapons.StartFalling` (disk 382 / ScriptSize 514,
unchanged):

* On: the test's `JumpIfNot` (07) becomes a `Jump` (06) over the destroy. The
  old condition and statements stay behind as unreachable bytecode, so the
  loader reads the same bytes into the same memory layout.
* Off: the destroy becomes `m_FlashlightGadget.ActivateGadget(Self, False)`
  -- `SpawnFlashlight`'s own call with True turned to False -- and two
  `EX_Nothing`. Its "off" branch removes the glow and leaves the body on.

`m_FlashlightGadget` is an import (`R6Abstract.R6AbstractWeapon`) and
`ActivateGadget` a name the package already has, so the package's own objects
are created in exactly the shipped order. The body should ride on the dropped
gun: both gadget actors are drawn from their base, and a dropped gun is still a
static-mesh base. That part is inferred -- stock always destroyed the
flashlight, so nobody has seen it.

Written to the offline and split-screen packages. Online hides the dropped gun
anyway, and its glow is a replicated light.
"""

from __future__ import annotations

import struct

#: The opening of `R6Weapons.StartFalling`, after its ScriptSize word.
ANCHOR = bytes.fromhex("071e007701ed012a16" "1901ed01030004611716" "0f01ed012a")
SIZE_WORD = struct.pack("<I", 514)
EX_JUMP = 0x06
EX_JUMP_IF_NOT = 0x07
#: the destroy and the clear, and what "off" puts there
DESTROY = bytes.fromhex("1901ed01030004611716" "0f01ed012a")
LIGHT_OFF = bytes.fromhex("1901ed010800001b4303172816" "0b0b")
KNOWN_OFFSET = 0x1DB611

MODES = ("stock", "on", "off")


class FlashlightError(Exception):
    pass


def _variants():
    on = bytes([EX_JUMP]) + ANCHOR[1:]
    off = ANCHOR[:9] + LIGHT_OFF
    return {"stock": ANCHOR, "on": on, "off": off}


def find(plain: bytes):
    """(offset, mode) of `StartFalling`'s opening, in whichever state."""
    hits = []
    for mode, body in _variants().items():
        at = plain.find(SIZE_WORD + body)
        while at >= 0:
            hits.append((at + 4, mode))
            at = plain.find(SIZE_WORD + body, at + 1)
    if len(hits) != 1:
        raise FlashlightError("expected one StartFalling, found %d" % len(hits))
    return hits[0]


def reads(plain: bytes) -> str:
    try:
        return find(plain)[1]
    except FlashlightError:
        return "unknown"


def apply(plain: bytes, mode: str = "on"):
    """Returns (plain, changed). The length never moves."""
    if mode not in MODES:
        raise FlashlightError("unknown mode %r" % mode)
    at, now = find(plain)
    if now == mode:
        return plain, 0
    body = _variants()[mode]
    out = bytearray(plain)
    out[at:at + len(body)] = body
    return bytes(out), 1


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "dead_flashlight", "A dead terrorist's weapon light",
        CHOICE, "stock", group,
        choices=[
            Choice("stock", "Stock (it vanishes)",
                   "The gun drops and its flashlight is destroyed with it."),
            Choice("on", "Stays on the gun, lit",
                   "The flashlight and its glow stay on the dropped gun."),
            Choice("off", "Stays on the gun, switched off",
                   "The flashlight stays on the dropped gun; its glow goes."),
        ],
        confidence="experimental", touches="data",
        help="When a terrorist with a weapon light dies, his gun drops and the "
             "game destroys the light first -- the flashlight vanishes from "
             "the gun. This keeps it on the gun, lit or switched off. It is "
             "the first statement of the function that drops the gun, so it "
             "applies in single player and split screen alike.",
        caution="Not yet played. Stock always destroyed the light, so how a "
                "kept one looks on a dropped gun has never been seen. It "
                "should ride on the gun, because the gadget is drawn from its "
                "base, but that is reasoned from the renderer, not watched.")
