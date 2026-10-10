#!/usr/bin/env python3
"""molcheck.py -- read a .MOL exactly the way Ghost Recon PS2's loader does.

MAPLoader::LoadFromMol (0x0047C340) reads each model chunk's header, then, for
a model it has not seen before, lets the model read ITSELF off the file stream
and goes straight on to the next header. It never seeks to the end of the
chunk, so a single field of drift corrupts every chunk after it. The readers:

  RSModel::ReadCollisionBinary       0x004B86D0
    RSDrawObject::ReadCollisionBinary  0x004B6BF0   name ["version" u32 name], u32 id,
                                                    2 x bounding sphere (16)
    Read(RSVertexPool)                 0x004CED00   u32 n, n x vec3
    u32 meshes; per mesh:
      RSModelMesh::ReadCollisionBinary 0x004BA460   draw object, u32 n,
                                                    n x (plane 10 + 3 x u16 vertex)
    i32 helpers; per helper: name, vec3, quat
    mSimModelReadBinaryCallback -> RSSimModel::ReadBinary 0x004EB2C0
      u32 n, n x vec3; u32 n, n x plane (10); u32 n, n x 3 x u16;
      u32 groups; per group (Read(RSCollisionGroup) 0x004E37E0):
        name, u32 +18, i32 mesh(+1C, -1 = sim faces), u32 +24, i32 surface,
        u32 n, n x (u16 face, u16 unused, u16 group)   file order -> +2, +0, +4

The sim model exists because ROBLoader::LoadGeometryChunk is called with
version 9, which makes RSSimModel::LoadSimModel build an empty one without
reading anything.

A collision face does not hold vertices. RSCollisionFace::GetVertexIndex
(0x004E2C30) follows it to `model.meshes[group.mesh].faces[face]` or, for mesh
-1, to the sim model's own faces; ReconnectCollisionFaces then WRITES vertex
positions back through that chain, so a bad index corrupts memory rather than
failing cleanly. `check` validates every link.

Usage:  molcheck.py FILE.MOL [...]      (plain or LZO-packed)
"""
import struct
import sys

ROOT = r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio"
sys.path.insert(0, ROOT)


class Reader:
    def __init__(self, d, p):
        self.d, self.p = d, p

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def skip(self, n):
        if n < 0 or self.p + n > len(self.d):
            raise ValueError("skip %d past end at %d" % (n, self.p))
        self.p += n

    def name(self):                                  # Read(istream&, RSString&)
        n = self.u32()
        if n > 4096:
            raise ValueError("string length %d at %d" % (n, self.p - 4))
        b = self.d[self.p:self.p + n]; self.p += n
        return b.rstrip(b"\0").decode("latin1")


def draw_object(r):
    s = r.name()
    ver = None
    if s == "version":
        ver = r.u32(); s = r.name()
    oid = r.u32()
    r.skip(32)
    return s, ver, oid


def model(r):
    name, ver, oid = draw_object(r)
    nv = r.u32(); r.skip(12 * nv)
    meshes = []
    for _ in range(r.u32()):
        draw_object(r)
        faces = []
        for _ in range(r.u32()):
            r.skip(10)
            faces.append((r.u16(), r.u16(), r.u16()))
        meshes.append(faces)
    helpers = []
    for _ in range(max(r.i32(), 0)):
        helpers.append(r.name()); r.skip(28)
    sv = r.u32(); r.skip(12 * sv)
    r.skip(10 * r.u32())
    sfaces = [(r.u16(), r.u16(), r.u16()) for _ in range(r.u32())]
    groups = []
    for _ in range(r.u32()):
        gname = r.name(); a = r.u32(); mesh = r.i32(); c = r.u32(); surf = r.i32()
        cf = [(r.u16(), r.u16(), r.u16()) for _ in range(r.u32())]
        groups.append(dict(name=gname, a=a, mesh=mesh, c=c, surface=surf, faces=cf))
    return dict(name=name, ver=ver, id=oid, nv=nv, meshes=meshes, helpers=helpers,
                sv=sv, sfaces=sfaces, groups=groups)


def header(d, p):                                    # RSQOBLoader::ReadChunkHeader
    size, typ = struct.unpack_from("<II", d, p)
    r = Reader(d, p + 8)
    name = r.name(); ver = None
    if name == "Version":
        ver = r.u32(); name = r.name()
    return size, typ, name, ver, r.p


def walk(d):
    """Top chunk (type 7) then its models. Each model is parsed from where its
    header ends, and `used` is how many bytes the game's reader would consume."""
    size, typ, name, ver, q = header(d, 8)
    count = struct.unpack_from("<I", d, q)[0]
    p = q + 4
    out = []
    for i in range(count):
        cs, ct, cn, cv, cq = header(d, p)
        r = Reader(d, cq); err = m = None
        try:
            m = model(r)
        except (ValueError, struct.error) as e:
            err = str(e)
        out.append(dict(index=i, offset=p, size=cs, type=ct, name=cn, version=cv,
                        used=r.p - cq, error=err, model=m))
        p = cq + cs
    return dict(type=typ, name=name, version=ver, count=count), out


def check(chunks):
    """Every problem the game would trip over, as (index, name, text)."""
    bad = []
    for c in chunks:
        if c["error"] or c["used"] != c["size"]:
            bad.append((c["index"], c["name"], "read %d of %d bytes%s" % (
                c["used"], c["size"], ", " + c["error"] if c["error"] else "")))
            continue
        m = c["model"]
        for mi, faces in enumerate(m["meshes"]):
            for f in faces:
                if max(f) >= m["nv"]:
                    bad.append((c["index"], c["name"], "mesh %d vertex %d >= %d" % (mi, max(f), m["nv"])))
        for gi, g in enumerate(m["groups"]):
            for fi, _unused, grp in g["faces"]:
                if grp >= len(m["groups"]):
                    bad.append((c["index"], c["name"], "group %d face names group %d" % (gi, grp)))
                    continue
                mesh = m["groups"][grp]["mesh"]
                if mesh == -1:
                    if fi >= len(m["sfaces"]) or max(m["sfaces"][fi]) >= m["sv"]:
                        bad.append((c["index"], c["name"], "group %d sim face %d out of range" % (gi, fi)))
                elif not 0 <= mesh < len(m["meshes"]) or fi >= len(m["meshes"][mesh]):
                    bad.append((c["index"], c["name"], "group %d mesh %d face %d out of range" % (gi, mesh, fi)))
    return bad


def main(paths):
    from tcps2 import rselzo
    for path in paths:
        d = rselzo.unpack(open(path, "rb").read())
        top, chunks = walk(d)
        bad = check(chunks)
        print("%s: %d bytes, top %s, %d models, %d problems"
              % (path, len(d), top, len(chunks), len(bad)))
        for b in bad[:20]:
            print("   #%d %r: %s" % b)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
