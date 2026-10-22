"""Models the VR pharmacy interior in Blender and exports it for Unity.

Run headless (after make_textures.py has written the label/sign textures):
    /Applications/Blender.app/Contents/MacOS/Blender -b -P build_pharmacy.py -- <textures_dir> <out_dir> [pepper.blend]

Everything is authored in **Unity coordinates** (metres, Y up, participant seated at the origin facing
+Z) through U(); the FBX export maps them back so the model lands in Unity exactly as laid out here.

Layout (Unity):
  room       x -3.5..3.5, z -2..6, 3.0 m ceiling
  Pepper     (0, 0, 1.5) - placed by Unity, not part of this model
  counter    centred at z 4.4, 3.4 m wide
  back wall  dispensary shelving (5 bays) under an illuminated PHARMACY sign
  side walls 3 bays of category shelving each, with header boards

Output: Pharmacy.fbx (+ Pharmacy.blend and Pharmacy_preview.png for checking).
Material names (Env_*) are matched by name in Unity, where the real URP materials are built.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TEX_DIR = argv[0] if len(argv) > 0 else "."
OUT_DIR = argv[1] if len(argv) > 1 else "out"
PEPPER_BLEND = argv[2] if len(argv) > 2 else None

random.seed(7)

# Room bounds (Unity)
X0, X1 = -3.5, 3.5
Z0, Z1 = -2.0, 6.0
HEIGHT = 3.0
WALL_T = 0.15

ATLAS_COLS = 4
CATEGORY_ROWS = 8
CAT = {"pain": 0, "vitamins": 1, "allergy": 2, "cold": 3, "first_aid": 4, "digestive": 5,
       "prescriptions": 6, "ask": 7}
# Product tiles (index into make_textures.PRODUCTS) per category.
PRODUCTS = {
    "pain": [0, 2, 6], "vitamins": [1, 3, 8, 9, 10], "allergy": [4, 5, 14],
    "cold": [11, 15, 3], "first_aid": [12, 13], "digestive": [7],
    "mixed": list(range(16)),
}


def U(x, y, z):
    """Unity position -> Blender position (FBX export -Z forward / Y up, plus Unity's X mirror)."""
    return Vector((-x, -z, y))


def U_dir(x, y, z):
    return Vector((-x, -z, y))


def U_size(sx, sy, sz):
    return Vector((sx, sz, sy))


# --- geometry groups ----------------------------------------------------------------------------

class Group:
    """One exported object: a bmesh accumulating boxes, with per-face material slots."""

    def __init__(self, name, bevel=0.0, bevel_segments=2):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.materials = []
        self.bevel = bevel
        self.bevel_segments = bevel_segments

    def slot(self, material):
        if material not in self.materials:
            self.materials.append(material)
        return self.materials.index(material)


GROUPS = {}


def group(name, **kw):
    if name not in GROUPS:
        GROUPS[name] = Group(name, **kw)
    return GROUPS[name]


# metres per texture repeat for world-projected materials
UV_REPEAT = {"Env_Floor": 1.6, "Env_Wall": 2.5, "Env_WallGreen": 2.5, "Env_Oak": 1.2}


def add_box(grp, center, size, material, uv="world", **uvargs):
    """Adds an axis-aligned box given in Unity coordinates."""
    bm = grp.bm
    c, s = U(*center), U_size(*size)
    m = Matrix.Translation(c) @ Matrix.Diagonal((s.x, s.y, s.z, 1.0))
    result = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    verts = set(result["verts"])
    faces = {f for v in verts for f in v.link_faces}
    slot = grp.slot(material)
    lo = Vector((c.x - s.x / 2, c.y - s.y / 2, c.z - s.z / 2))
    hi = Vector((c.x + s.x / 2, c.y + s.y / 2, c.z + s.z / 2))
    for f in faces:
        f.material_index = slot
        f.smooth = False
        if uv == "world":
            _uv_world(f, grp.uv, UV_REPEAT.get(material, 1.0))
        elif uv == "atlas":
            _uv_atlas(f, grp.uv, lo, hi, **uvargs)
        elif uv == "row":
            _uv_row(f, grp.uv, lo, hi, **uvargs)
        elif uv == "full":
            _uv_full(f, grp.uv, lo, hi, **uvargs)
        else:
            for loop in f.loops:
                loop[grp.uv].uv = (0.5, 0.5)
    return faces


def _uv_world(face, layer, repeat):
    n = face.normal
    a = max(range(3), key=lambda i: abs(n[i]))
    for loop in face.loops:
        p = loop.vert.co
        if a == 2:
            u, v = p.x, p.y
        elif a == 0:
            u, v = p.y, p.z
        else:
            u, v = p.x, p.z
        loop[layer].uv = (u / repeat, v / repeat)


def _front_frame(front_u):
    """For a face whose outward normal is the Unity direction front_u, returns (normal, right, up) in
    Blender space, where right is the viewer's right when looking at the face."""
    n = U_dir(*front_u).normalized()
    up = Vector((0, 0, 1))
    right = (-n).cross(up)
    return n, right, up


def _project(face, layer, lo, hi, right, up, u0, u1, v0, v1):
    # Extents of the box along right/up, for normalising.
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    rs = [c.dot(right) for c in corners]
    us = [c.dot(up) for c in corners]
    rmin, rmax, umin, umax = min(rs), max(rs), min(us), max(us)
    for loop in face.loops:
        p = loop.vert.co
        fu = (p.dot(right) - rmin) / max(rmax - rmin, 1e-6)
        fv = (p.dot(up) - umin) / max(umax - umin, 1e-6)
        loop[layer].uv = (u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)


def _uv_atlas(face, layer, lo, hi, tile, front):
    """Medicine box: front/back faces get the label, the rest the side colour of the tile."""
    col, row = tile % ATLAS_COLS, tile // ATLAS_COLS
    u0, u1 = col / 4, (col + 1) / 4
    tile_top = 1 - row / 4
    front_v0, front_v1 = tile_top - 320 / 2048, tile_top
    side_v0, side_v1 = tile_top - 512 / 2048, tile_top - 320 / 2048
    n, right, up = _front_frame(front)
    if abs(face.normal.dot(n)) > 0.9:
        _project(face, layer, lo, hi, right, up, u0, u1, front_v0, front_v1)
    else:
        for loop in face.loops:
            loop[layer].uv = ((u0 + u1) / 2, (side_v0 + side_v1) / 2)


def _uv_row(face, layer, lo, hi, row, front):
    """Header board: front face shows one row of category_atlas, other faces the row colour."""
    v1 = 1 - row / CATEGORY_ROWS
    v0 = v1 - 1 / CATEGORY_ROWS
    n, right, up = _front_frame(front)
    if face.normal.dot(n) > 0.9:
        _project(face, layer, lo, hi, right, up, 0.0, 1.0, v0 + 0.01, v1)
    else:
        for loop in face.loops:
            loop[layer].uv = (0.02, (v0 + v1) / 2)


def _uv_full(face, layer, lo, hi, front):
    """Whole texture on the front face (the PHARMACY sign); edges take a border pixel."""
    n, right, up = _front_frame(front)
    if face.normal.dot(n) > 0.9:
        _project(face, layer, lo, hi, right, up, 0.0, 1.0, 0.0, 1.0)
    else:
        for loop in face.loops:
            loop[layer].uv = (0.5, 0.02)


# --- room ---------------------------------------------------------------------------------------

def build_architecture():
    g = group("Architecture")
    cx, cz = (X0 + X1) / 2, (Z0 + Z1) / 2
    w, d = X1 - X0, Z1 - Z0
    add_box(g, (cx, -0.05, cz), (w + 2 * WALL_T, 0.1, d + 2 * WALL_T), "Env_Floor")
    add_box(g, (cx, HEIGHT + 0.05, cz), (w + 2 * WALL_T, 0.1, d + 2 * WALL_T), "Env_Ceiling", uv=None)

    add_box(g, (X0 - WALL_T / 2, HEIGHT / 2, cz), (WALL_T, HEIGHT, d), "Env_Wall")
    add_box(g, (X1 + WALL_T / 2, HEIGHT / 2, cz), (WALL_T, HEIGHT, d), "Env_Wall")
    add_box(g, (cx, HEIGHT / 2, Z0 - WALL_T / 2), (w + 2 * WALL_T, HEIGHT, WALL_T), "Env_Wall")
    # Back wall in pharmacy green behind the dispensary.
    add_box(g, (cx, HEIGHT / 2, Z1 + WALL_T / 2), (w + 2 * WALL_T, HEIGHT, WALL_T), "Env_WallGreen")

    # Skirting boards.
    trim = group("Trim", bevel=0.004)
    sk_h, sk_t = 0.09, 0.015
    add_box(trim, (X0 + sk_t / 2, sk_h / 2, cz), (sk_t, sk_h, d), "Env_GlossWhite", uv=None)
    add_box(trim, (X1 - sk_t / 2, sk_h / 2, cz), (sk_t, sk_h, d), "Env_GlossWhite", uv=None)
    add_box(trim, (cx, sk_h / 2, Z0 + sk_t / 2), (w, sk_h, sk_t), "Env_GlossWhite", uv=None)

    # Entrance door behind the participant.
    door = group("Door", bevel=0.005)
    add_box(door, (2.2, 1.05, Z0 + 0.02), (1.1, 2.1, 0.04), "Env_DoorFrame", uv=None)
    add_box(door, (2.2, 1.03, Z0 + 0.045), (0.96, 2.0, 0.02), "Env_DoorGlass", uv=None)
    add_box(door, (2.62, 1.0, Z0 + 0.07), (0.03, 0.3, 0.03), "Env_Metal", uv=None)


def build_ceiling_lights():
    g = group("CeilingLights", bevel=0.003)
    for x in (-2.0, 0.0, 2.0):
        for z in (-0.6, 1.4, 3.4, 5.2):
            add_box(g, (x, HEIGHT - 0.005, z), (0.64, 0.012, 0.64), "Env_Metal", uv=None)
            add_box(g, (x, HEIGHT - 0.012, z), (0.58, 0.004, 0.58), "Env_LightPanel", uv=None)


# --- shelving -----------------------------------------------------------------------------------

def to_world(origin, right, back, lx, ly, lz):
    return tuple(origin[i] + right[i] * lx + back[i] * lz + (ly if i == 1 else 0.0) for i in range(3))


def world_size(right, back, sx, sy, sz):
    return tuple(abs(right[i]) * sx + abs(back[i]) * sz + (sy if i == 1 else 0.0) for i in range(3))


def shelf_bay(origin, right, back, width, height, depth, shelf_heights, products, category=None):
    """One shelving bay. origin = front-left-bottom corner (Unity); right/back are unit Unity axes."""
    front = tuple(-b for b in back)
    carcass = group("Shelving", bevel=0.004)
    stock = group("Products", bevel=0.002, bevel_segments=1)
    t = 0.02

    def box(grp, lx, ly, lz, sx, sy, sz, mat, **uv):
        add_box(grp, to_world(origin, right, back, lx + sx / 2, ly + sy / 2, lz + sz / 2),
                world_size(right, back, sx, sy, sz), mat, **uv)

    # Sides, back, plinth, top.
    box(carcass, 0, 0, 0, t, height, depth, "Env_Melamine", uv=None)
    box(carcass, width - t, 0, 0, t, height, depth, "Env_Melamine", uv=None)
    box(carcass, t, 0, depth - t, width - 2 * t, height, t, "Env_Melamine", uv=None)
    box(carcass, t, 0, 0.03, width - 2 * t, 0.1, depth - 0.03, "Env_Plinth", uv=None)
    box(carcass, 0, height - 0.03, 0, width, 0.03, depth, "Env_Melamine", uv=None)

    for sh in shelf_heights:
        box(carcass, t, sh, 0.0, width - 2 * t, 0.022, depth - t, "Env_Melamine", uv=None)
        box(carcass, t, sh - 0.012, -0.004, width - 2 * t, 0.04, 0.012, "Env_Oak")  # oak price-strip lip

        # Boxes standing on the shelf, labels facing out.
        x = t + 0.03
        while True:
            tile = random.choice(products)
            bw = random.choice((0.085, 0.095, 0.11))
            bh = random.choice((0.12, 0.14, 0.16))
            bd = min(depth - 0.08, random.choice((0.05, 0.07, 0.09)))
            if x + bw > width - t - 0.02:
                break
            # Front-most box of a short facing; a second box behind fills the depth.
            for row in range(2):
                box(stock, x, sh + 0.022, 0.03 + row * (bd + 0.005), bw, bh, bd, "Env_Products",
                    uv="atlas", tile=tile, front=front)
            x += bw + random.uniform(0.006, 0.014)

    if category is not None:
        board = group("Headers", bevel=0.003)
        box(board, 0, height, 0.0, width, 0.22, 0.03, "Env_Category", uv="row", row=CAT[category], front=front)


def build_back_wall():
    depth = 0.38
    origin_z = Z1 - depth
    shelves = (0.12 + 0.1, 0.62, 1.02, 1.42, 1.82)
    for i in range(5):
        x = -2.5 + i * 1.0
        shelf_bay((x, 0.0, origin_z), (1, 0, 0), (0, 0, 1), 1.0, 2.2, depth, shelves, PRODUCTS["mixed"])

    # Green bulkhead with the illuminated sign above the dispensary.
    arch = group("Architecture")
    add_box(arch, (0, 2.62, Z1 - 0.2), (5.4, 0.76, 0.4), "Env_WallGreen")
    sign = group("Sign", bevel=0.004)
    add_box(sign, (0, 2.62, Z1 - 0.42), (2.8, 0.525, 0.04), "Env_Sign", uv="full", front=(0, 0, -1))


def build_side_walls():
    depth = 0.4
    shelves = (0.22, 0.6, 0.98, 1.36)
    left = [("pain", 0.4), ("vitamins", 1.4), ("allergy", 2.4)]
    right = [("cold", 2.4), ("first_aid", 1.4), ("digestive", 0.4)]
    # Left wall: units face +X; viewer's right is +Z.
    for cat, z in left:
        shelf_bay((X0 + depth, 0.0, z), (0, 0, 1), (-1, 0, 0), 1.0, 1.75, depth, shelves, PRODUCTS[cat], cat)
    # Right wall: units face -X; viewer's right is -Z, so the bay starts at its +Z end.
    for cat, z in right:
        shelf_bay((X1 - depth, 0.0, z + 1.0), (0, 0, -1), (1, 0, 0), 1.0, 1.75, depth, shelves, PRODUCTS[cat], cat)


def build_counter():
    g = group("Counter", bevel=0.006)
    cz, w, h, d = 4.4, 3.4, 1.0, 0.65
    add_box(g, (0, 0.05, cz + 0.03), (w - 0.06, 0.1, d - 0.08), "Env_Plinth", uv=None)
    add_box(g, (0, 0.1 + (h - 0.14) / 2, cz), (w, h - 0.14, d), "Env_GlossWhite", uv=None)
    add_box(g, (0, 0.78, cz - d / 2 - 0.004), (w - 0.1, 0.07, 0.01), "Env_Accent", uv=None)
    add_box(g, (0, h - 0.02, cz), (w + 0.06, 0.04, d + 0.06), "Env_Oak")

    # Counter-top items.
    items = group("CounterItems", bevel=0.004)
    add_box(items, (1.1, h + 0.02, cz - 0.05), (0.09, 0.04, 0.16), "Env_BlackPlastic", uv=None)  # card terminal
    add_box(items, (1.1, h + 0.045, cz - 0.07), (0.07, 0.006, 0.05), "Env_Screen", uv=None)
    # Leaflet stand.
    add_box(items, (-1.15, h + 0.13, cz + 0.05), (0.3, 0.26, 0.02), "Env_Acrylic", uv=None)
    add_box(items, (-1.15, h + 0.01, cz - 0.02), (0.3, 0.02, 0.14), "Env_Acrylic", uv=None)
    # The two study products on display.
    stock = group("Products", bevel=0.002, bevel_segments=1)
    for i, tile in enumerate((0, 1, 0, 1)):
        add_box(stock, (-0.35 + i * 0.13, h + 0.07, cz - 0.12), (0.1, 0.14, 0.05), "Env_Products",
                uv="atlas", tile=tile, front=(0, 0, -1))

    # "Ask our pharmacist" board on the counter front.
    board = group("Headers", bevel=0.003)
    add_box(board, (0, 0.5, cz - d / 2 - 0.012), (1.6, 0.2, 0.012), "Env_Category", uv="row",
            row=CAT["ask"], front=(0, 0, -1))


# --- materials, export, preview -----------------------------------------------------------------

MAT_COLORS = {
    "Env_Floor": (0.82, 0.8, 0.76), "Env_Wall": (0.93, 0.93, 0.91), "Env_WallGreen": (0.0, 0.33, 0.25),
    "Env_Ceiling": (0.95, 0.95, 0.95), "Env_GlossWhite": (0.95, 0.95, 0.95),
    "Env_Melamine": (0.92, 0.92, 0.9), "Env_Plinth": (0.12, 0.12, 0.12), "Env_Oak": (0.6, 0.42, 0.26),
    "Env_Accent": (0.0, 0.5, 0.36), "Env_Metal": (0.7, 0.71, 0.72), "Env_BlackPlastic": (0.03, 0.03, 0.03),
    "Env_Screen": (0.05, 0.15, 0.25), "Env_Acrylic": (0.85, 0.9, 0.92), "Env_LightPanel": (1, 1, 1),
    "Env_DoorFrame": (0.25, 0.26, 0.27), "Env_DoorGlass": (0.35, 0.45, 0.5),
    "Env_Products": (1, 1, 1), "Env_Category": (1, 1, 1), "Env_Sign": (1, 1, 1),
}
MAT_TEXTURES = {
    "Env_Floor": "interior_tiles_diff.jpg", "Env_Wall": "painted_plaster_wall_diff.jpg",
    "Env_Oak": "oak_veneer_01_diff.jpg", "Env_Products": "medicine_atlas.png",
    "Env_Category": "category_atlas.png", "Env_Sign": "pharmacy_sign.png",
}
MAT_EMISSIVE = {"Env_LightPanel": 6.0, "Env_Sign": 1.2, "Env_Screen": 0.6}
MAT_ROUGHNESS = {"Env_GlossWhite": 0.2, "Env_Floor": 0.35, "Env_Metal": 0.3, "Env_Acrylic": 0.05,
                 "Env_DoorGlass": 0.05}


def make_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    color = MAT_COLORS.get(name, (0.8, 0.8, 0.8))
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = MAT_ROUGHNESS.get(name, 0.6)
    tex_node = None
    if name in MAT_TEXTURES:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = bpy.data.images.load(os.path.join(TEX_DIR, MAT_TEXTURES[name]))
        if name in ("Env_Floor", "Env_Wall", "Env_Oak"):
            mix = nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            # The Mix node has float/vector/colour sockets sharing names; pick the colour ones.
            a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
            b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
            result = next(o for o in mix.outputs if o.type == "RGBA")
            links.new(tex_node.outputs["Color"], a)
            b.default_value = (*[min(1.0, c * 1.15) for c in color], 1)
            links.new(result, bsdf.inputs["Base Color"])
        else:
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    if name in MAT_EMISSIVE:
        if tex_node is not None:
            links.new(tex_node.outputs["Color"], bsdf.inputs["Emission Color"])
        else:
            bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = MAT_EMISSIVE[name]
    mat.diffuse_color = (*color, 1)
    return mat


def realize_groups():
    mats = {}
    objects = []
    for g in GROUPS.values():
        me = bpy.data.meshes.new(g.name)
        g.bm.to_mesh(me)
        g.bm.free()
        for name in g.materials:
            if name not in mats:
                mats[name] = make_material(name)
            me.materials.append(mats[name])
        obj = bpy.data.objects.new(g.name, me)
        bpy.context.collection.objects.link(obj)
        if g.bevel > 0:
            mod = obj.modifiers.new("Bevel", "BEVEL")
            mod.width = g.bevel
            mod.segments = g.bevel_segments
            mod.limit_method = "ANGLE"
            mod.harden_normals = True
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
        objects.append(obj)
    return objects


def add_preview_pepper():
    """Appends the assembled Pepper (from build_pepper.py) for the preview render only."""
    if not PEPPER_BLEND or not os.path.exists(PEPPER_BLEND):
        return []
    with bpy.data.libraries.load(PEPPER_BLEND, link=False) as (src, dst):
        dst.objects = list(src.objects)
    added = [o for o in dst.objects if o is not None]
    for o in added:
        bpy.context.collection.objects.link(o)
    root = next((o for o in added if o.name.startswith("Pepper") and o.parent is None), None)
    if root:
        # Pepper.blend faces Blender -Y; turn it to face the participant (Unity -Z = Blender +Y).
        root.location = U(0, 0, 1.5)
        root.rotation_euler = (0, 0, math.radians(90))
    return added


def render_preview(path):
    scene = bpy.context.scene
    temp = add_preview_pepper()

    cam_data = bpy.data.cameras.new("Eye")
    cam_data.lens = 16  # wide, close to a VR field of view
    cam = bpy.data.objects.new("Eye", cam_data)
    scene.collection.objects.link(cam)
    cam.location = U(0, 1.2, 0)
    cam.rotation_euler = (U_dir(0, -0.08, 1)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    temp.append(cam)

    for x in (-2.0, 0.0, 2.0):
        for z in (-0.6, 1.4, 3.4, 5.2):
            ld = bpy.data.lights.new(f"Panel_{x}_{z}", "AREA")
            ld.shape = "SQUARE"
            ld.size = 0.6
            ld.energy = 120
            lo = bpy.data.objects.new(ld.name, ld)
            lo.location = U(x, HEIGHT - 0.03, z)  # area lights point down -Z (Blender) by default
            scene.collection.objects.link(lo)
            temp.append(lo)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.82, 0.85, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    scene.world = world

    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.view_settings.view_transform = "AgX" if "AgX" in [
        v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return temp


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)

    build_architecture()
    build_ceiling_lights()
    build_back_wall()
    build_side_walls()
    build_counter()
    objects = realize_groups()

    # Export the environment only (before preview-only objects are added).
    for o in bpy.context.scene.objects:
        o.select_set(o in objects)
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT_DIR, "Pharmacy.fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y",
        mesh_smooth_type="FACE",
        path_mode="STRIP",
    )

    temp = render_preview(os.path.join(OUT_DIR, "Pharmacy_preview.png"))
    for o in temp:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "Pharmacy.blend"))

    tris = sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)
    print(f"[pharmacy] done -> {OUT_DIR} ({len(objects)} objects, ~{tris} triangles)")


main()
