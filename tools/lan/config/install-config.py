"""Put the Jungle Storm LAN co-op config where ModStudio's "Last applied" button looks.

    python install-config.py "D:\\path\\to\\Jungle Storm.iso"

Then open ModStudio, pick that disc, press LAST APPLIED, choose the entry, and press APPLY TO DISC.
Standard library only. It writes one small file next to the disc and never touches the disc itself.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERIAL = b"SLUS_208.20"


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    iso = os.path.abspath(argv[1])
    if not os.path.isfile(iso):
        print("no such file: %s" % iso)
        return 1
    with open(iso, "rb") as fh:
        head = fh.read(4 << 20)
    if SERIAL not in head:
        print("%s does not look like Ghost Recon: Jungle Storm (no %s in it)."
              % (os.path.basename(iso), SERIAL.decode()))
        print("Use the USA disc, SLUS-20820.")
        return 1
    folder = os.path.join(os.path.dirname(iso), ".tcms-backup",
                          os.path.splitext(os.path.basename(iso))[0])
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, "applied-settings.json")
    src = os.path.join(HERE, "applied-settings.json")
    record = json.load(open(src, encoding="utf-8"))
    if os.path.isfile(dest):                       # keep whatever is already remembered
        try:
            old = json.load(open(dest, encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        if old.get("profile") == record["profile"]:
            mine = record["history"][0]
            keep = [e for e in (old.get("history") or []) if e.get("when") != mine.get("when")]
            record["history"] = [mine] + keep[:4]
            record["on_disc"] = old.get("on_disc")
            print("kept %d earlier entr%s" % (len(keep), "y" if len(keep) == 1 else "ies"))
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
    print("installed for %s" % os.path.basename(iso))
    print("  %s" % dest)
    print()
    print("Now: open ModStudio, choose that disc, press LAST APPLIED, pick")
    print("\"%s\", press Load, then APPLY TO DISC." % record["history"][0]["when"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
