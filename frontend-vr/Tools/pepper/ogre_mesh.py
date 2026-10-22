"""Minimal reader for Ogre3D binary meshes ([MeshSerializer_v1.8]).

Pepper's official 3D model ships in the SoftBank Robotics SDK
(alrobotmodel/meshes/juliette/*.mesh) in this format. This reads just what's needed to
rebuild it elsewhere: positions, normals, UVs, triangle indices and material names per submesh.

Pure Python (struct only) so it runs both standalone and inside Blender's bundled Python.
"""
import struct

# Chunk ids
M_HEADER = 0x1000
M_MESH = 0x3000
M_SUBMESH = 0x4000
M_SUBMESH_OPERATION = 0x4010
M_SUBMESH_BONE_ASSIGNMENT = 0x4100
M_SUBMESH_TEXTURE_ALIAS = 0x4200
M_GEOMETRY = 0x5000
M_GEOMETRY_VERTEX_DECLARATION = 0x5100
M_GEOMETRY_VERTEX_ELEMENT = 0x5110
M_GEOMETRY_VERTEX_BUFFER = 0x5200
M_GEOMETRY_VERTEX_BUFFER_DATA = 0x5210
M_MESH_BOUNDS = 0x9000
M_SUBMESH_NAME_TABLE = 0xA000
M_SUBMESH_NAME_TABLE_ELEMENT = 0xA100

# Vertex element semantics
VES_POSITION, VES_BLEND_WEIGHTS, VES_BLEND_INDICES, VES_NORMAL = 1, 2, 3, 4
VES_DIFFUSE, VES_SPECULAR, VES_TEXTURE_COORDINATES = 5, 6, 7

# Vertex element types -> (struct format, size in bytes)
VET_FORMATS = {
    0: ("f", 4), 1: ("2f", 8), 2: ("3f", 12), 3: ("4f", 16),
    4: ("I", 4),  # packed colour
    5: ("h", 2), 6: ("2h", 4), 7: ("3h", 6), 8: ("4h", 8),
    9: ("4B", 4), 10: ("I", 4), 11: ("I", 4),
}

CHUNK_HEADER = 6  # ushort id + uint length


class Geometry:
    def __init__(self):
        self.vertex_count = 0
        self.elements = []  # (source, type, semantic, offset, index)
        self.buffers = {}   # bind index -> (vertex size, bytes)

    def attribute(self, semantic, index=0):
        """Returns a list of tuples for one vertex attribute, or None if absent."""
        for source, vtype, sem, offset, idx in self.elements:
            if sem != semantic or idx != index:
                continue
            size, data = self.buffers[source]
            fmt, _ = VET_FORMATS[vtype]
            unpack = struct.Struct("<" + fmt).unpack_from
            return [unpack(data, v * size + offset) for v in range(self.vertex_count)]
        return None


class SubMesh:
    def __init__(self):
        self.material = ""
        self.use_shared = True
        self.indices = []
        self.operation = 4  # triangle list
        self.geometry = None
        self.name = ""


class Mesh:
    def __init__(self):
        self.shared = None
        self.submeshes = []
        self.bounds = None  # (min xyz, max xyz, radius)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, fmt):
        s = struct.Struct("<" + fmt)
        values = s.unpack_from(self.data, self.pos)
        self.pos += s.size
        return values if len(values) > 1 else values[0]

    def string(self):
        end = self.data.index(b"\n", self.pos)
        value = self.data[self.pos:end].decode("utf-8", "replace")
        self.pos = end + 1
        return value

    def chunk(self):
        if self.pos + CHUNK_HEADER > len(self.data):
            return None, 0
        cid, length = struct.unpack_from("<HI", self.data, self.pos)
        self.pos += CHUNK_HEADER
        return cid, length

    def back(self):
        self.pos -= CHUNK_HEADER

    def eof(self):
        return self.pos >= len(self.data)


def _read_geometry(r, end):
    g = Geometry()
    g.vertex_count = r.read("I")
    while r.pos < end:
        cid, length = r.chunk()
        chunk_end = r.pos - CHUNK_HEADER + length
        if cid == M_GEOMETRY_VERTEX_DECLARATION:
            while r.pos < chunk_end:
                eid, elen = r.chunk()
                if eid != M_GEOMETRY_VERTEX_ELEMENT:
                    r.back()
                    break
                g.elements.append(r.read("5H"))
        elif cid == M_GEOMETRY_VERTEX_BUFFER:
            bind, vsize = r.read("2H")
            did, dlen = r.chunk()
            assert did == M_GEOMETRY_VERTEX_BUFFER_DATA
            nbytes = vsize * g.vertex_count
            g.buffers[bind] = (vsize, r.data[r.pos:r.pos + nbytes])
            r.pos += nbytes
        else:
            r.back()
            break
        r.pos = max(r.pos, chunk_end) if cid != M_GEOMETRY_VERTEX_DECLARATION else r.pos
    return g


def _read_submesh(r, end):
    sm = SubMesh()
    sm.material = r.string()
    sm.use_shared = bool(r.read("B"))
    index_count = r.read("I")
    is32 = bool(r.read("B"))
    if index_count:
        sm.indices = list(r.read(f"{index_count}{'I' if is32 else 'H'}")) if index_count > 1 \
            else [r.read("I" if is32 else "H")]
    if not sm.use_shared:
        cid, length = r.chunk()
        assert cid == M_GEOMETRY, hex(cid)
        sm.geometry = _read_geometry(r, r.pos - CHUNK_HEADER + length)
    while r.pos < end:
        cid, length = r.chunk()
        chunk_end = r.pos - CHUNK_HEADER + length
        if cid == M_SUBMESH_OPERATION:
            sm.operation = r.read("H")
        elif cid in (M_SUBMESH_BONE_ASSIGNMENT, M_SUBMESH_TEXTURE_ALIAS):
            r.pos = chunk_end
        else:
            r.back()
            break
    return sm


def read_mesh(path):
    with open(path, "rb") as f:
        data = f.read()
    r = _Reader(data)
    assert r.read("H") == M_HEADER
    version = r.string()
    if not any(v in version for v in ("v1.8", "v1.41", "v1.4]")):
        raise ValueError(f"Unsupported Ogre mesh version: {version}")

    mesh = Mesh()
    cid, length = r.chunk()
    assert cid == M_MESH
    r.read("B")  # skeletally animated
    while not r.eof():
        cid, length = r.chunk()
        if cid is None:
            break
        chunk_end = r.pos - CHUNK_HEADER + length
        if cid == M_GEOMETRY:
            mesh.shared = _read_geometry(r, chunk_end)
        elif cid == M_SUBMESH:
            mesh.submeshes.append(_read_submesh(r, chunk_end))
            continue  # submesh length covers only its header; children were consumed above
        elif cid == M_MESH_BOUNDS:
            mesh.bounds = (r.read("3f"), r.read("3f"), r.read("f"))
        elif cid == M_SUBMESH_NAME_TABLE:
            while r.pos < chunk_end:
                eid, elen = r.chunk()
                index = r.read("H")
                if index < len(mesh.submeshes):
                    mesh.submeshes[index].name = r.string()
                else:
                    r.string()
        r.pos = chunk_end
    return mesh


def triangles(mesh, submesh):
    """Yields (positions, normals, uvs, faces) for a submesh, faces as index triples."""
    geom = submesh.geometry if not submesh.use_shared else mesh.shared
    positions = geom.attribute(VES_POSITION)
    normals = geom.attribute(VES_NORMAL)
    uvs = geom.attribute(VES_TEXTURE_COORDINATES)
    idx = submesh.indices
    if submesh.operation == 4:  # triangle list
        faces = [tuple(idx[i:i + 3]) for i in range(0, len(idx) - 2, 3)]
    elif submesh.operation == 5:  # triangle strip
        faces = [(idx[i], idx[i + 1], idx[i + 2]) if i % 2 == 0 else (idx[i + 1], idx[i], idx[i + 2])
                 for i in range(len(idx) - 2)]
    else:
        raise ValueError(f"Unsupported operation type {submesh.operation}")
    return positions, normals, uvs, faces
