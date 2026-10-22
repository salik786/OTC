"""Rebuilds Pepper's official 3D model in Blender and exports it for Unity.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender -b -P build_pepper.py -- <sdk_meshes_dir> <out_dir>

Sources:
  - Meshes + textures: SoftBank Robotics SDK, alrobotmodel/meshes/juliette (Ogre3D .mesh). Aldebaran
    meshes, CC BY-NC-ND 4.0 - non-commercial use with attribution.
  - Kinematics: ros-naoqi/pepper_robot pepper_description URDF (Apache 2.0), saved as pepper.urdf.
  - Pose: NAOqi "StandInit" posture (robot_posture/postures_juliette.xml).

Output (in <out_dir>):
  Pepper.fbx        - jointed model for Unity. Each joint is a pair of transforms:
                      "<Joint>_origin" (fixed URDF origin) -> "<Joint>" (rotates about the joint axis),
                      so joint angles can be driven at runtime using NAOqi joint names.
  Textures/*.png    - copied SDK textures
  Pepper.blend      - the assembled scene, for inspection in Blender
  Pepper_preview.png - a quick render to sanity-check the result
"""
import math
import os
import shutil
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ogre_mesh import read_mesh, triangles  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MESH_DIR = argv[0] if len(argv) > 0 else os.path.expanduser(
    "~/Library/Application Support/Softbank Robotics/RobotSDK/API 7/tools/share/alrobotmodel/meshes")
OUT_DIR = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "out")
URDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pepper.urdf")

# URDF link -> SDK mesh file (juliette/<name>.mesh)
LINK_MESH = {
    "torso": "Torso", "Neck": "HeadYaw", "Head": "HeadPitch",
    "Hip": "HipRoll", "Pelvis": "HipPitch", "Tibia": "KneePitch",
    "LShoulder": "LShoulderPitch", "LBicep": "LShoulderRoll", "LElbow": "LElbowYaw",
    "LForeArm": "LElbowRoll", "l_wrist": "LWristYaw",
    "RShoulder": "RShoulderPitch", "RBicep": "RShoulderRoll", "RElbow": "RElbowYaw",
    "RForeArm": "RElbowRoll", "r_wrist": "RWristYaw",
    "WheelFL_link": "Wheel", "WheelFR_link": "Wheel", "WheelB_link": "Wheel",
}
for side in "LR":
    for f in range(1, 5):
        LINK_MESH[f"{side}Finger{f}1_link"] = "Phalax"
        LINK_MESH[f"{side}Finger{f}2_link"] = "Phalax"
        LINK_MESH[f"{side}Finger{f}3_link"] = "PhalaxEnd"
    LINK_MESH[f"{side}Thumb1_link"] = "Phalax"
    LINK_MESH[f"{side}Thumb2_link"] = "PhalaxEnd"

# NAOqi StandInit posture (order as in postures_juliette.xml).
STAND_INIT = {
    "HeadYaw": 0.0, "HeadPitch": -0.2,
    "LShoulderPitch": 1.57, "LShoulderRoll": 0.12, "LElbowYaw": -1.2217, "LElbowRoll": -0.5235,
    "LWristYaw": 0.0, "LHand": 0.6,
    "HipRoll": 0.0, "HipPitch": -0.04, "KneePitch": -0.01,
    "RShoulderPitch": 1.57, "RShoulderRoll": -0.12, "RElbowYaw": 1.2217, "RElbowRoll": 0.5235,
    "RWristYaw": 0.0, "RHand": 0.6,
}

TEXTURES = {
    "face_tex": "juliette_face.png",
    "ear_tex": "juliette_ear.png",
    "head_speaker_tex": "juliette_head_speaker.png",
    "transparent": "juliette_tab.jpg",  # the tablet screen
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def make_materials(tex_dir):
    """Principled-BSDF approximations of juliette.material, named to match the Ogre materials."""
    mats = {}

    def principled(name, color, roughness, metallic=0.0, emission=None, texture=None):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 1.0
        if texture:
            img = bpy.data.images.load(os.path.join(tex_dir, texture))
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.diffuse_color = (*color, 1.0)  # viewport/workbench colour
        mats[name] = mat
        return mat

    principled("shiny_white", (0.92, 0.92, 0.92), 0.18)
    principled("milky_white", (0.85, 0.85, 0.84), 0.45)
    principled("black", (0.02, 0.02, 0.02), 0.35)
    principled("blue_led", (0.05, 0.38, 0.64), 0.3, emission=(0.05, 0.45, 0.9))
    principled("transparent", (0.3, 0.3, 0.3), 0.08, texture=TEXTURES["transparent"])
    principled("face_tex", (1.0, 1.0, 1.0), 0.4, texture=TEXTURES["face_tex"])
    principled("ear_tex", (0.6, 0.6, 0.6), 0.5, texture=TEXTURES["ear_tex"])
    principled("head_speaker_tex", (0.64, 0.64, 0.64), 0.5, texture=TEXTURES["head_speaker_tex"])
    principled("_missing_material_", (0.8, 0.8, 0.8), 0.5)
    return mats


_mesh_cache = {}


def build_mesh_data(mesh_name, mats):
    """Converts one Ogre mesh into Blender mesh data (shared between links that reuse it)."""
    if mesh_name in _mesh_cache:
        return _mesh_cache[mesh_name]

    ogre = read_mesh(os.path.join(MESH_DIR, "juliette", mesh_name + ".mesh"))
    verts, faces, loop_uvs, loop_normals, face_mat = [], [], [], [], []
    slot_names = []

    for sm in ogre.submeshes:
        positions, normals, uvs, tris = triangles(ogre, sm)
        material = sm.material if sm.material in mats else "_missing_material_"
        if material not in slot_names:
            slot_names.append(material)
        slot = slot_names.index(material)

        base = len(verts)
        verts.extend(positions)
        for a, b, c in tris:
            faces.append((base + a, base + b, base + c))
            face_mat.append(slot)
            for i in (a, b, c):
                u, v = uvs[i] if uvs else (0.0, 0.0)
                loop_uvs.append((u, 1.0 - v))  # Ogre UV origin is top-left
                loop_normals.append(normals[i] if normals else (0.0, 0.0, 1.0))

    me = bpy.data.meshes.new(mesh_name)
    me.from_pydata(verts, [], faces)
    me.update()

    uv_layer = me.uv_layers.new(name="UVMap")
    for i, loop in enumerate(me.loops):
        uv_layer.data[i].uv = loop_uvs[i]

    for name in slot_names:
        me.materials.append(mats[name])
    for poly, slot in zip(me.polygons, face_mat):
        poly.material_index = slot
        poly.use_smooth = True

    # from_pydata can drop degenerate faces; only apply custom normals when loops still line up.
    if len(me.loops) == len(loop_normals):
        me.normals_split_custom_set([Vector(n).normalized() for n in loop_normals])

    _mesh_cache[mesh_name] = me
    return me


def parse_xyz(text):
    return Vector([float(x) for x in text.split()]) if text else Vector((0, 0, 0))


def build_robot(mats):
    urdf = ET.parse(URDF).getroot()

    root = bpy.data.objects.new("Pepper", None)
    bpy.context.collection.objects.link(root)
    # URDF forward is +X; turn it to face Blender's front (-Y), which the FBX export below maps to
    # Unity's forward (+Z).
    root.rotation_euler = Euler((0, 0, math.radians(-90)), "XYZ")

    # Torso is the URDF root link; place it under the root and fix the height afterwards.
    link_objects = {"torso": bpy.data.objects.new("Torso", None)}
    bpy.context.collection.objects.link(link_objects["torso"])
    link_objects["torso"].parent = root

    joints = [j for j in urdf.findall("joint") if j.find("child").get("link") in LINK_MESH
              or j.find("child").get("link") == "base_footprint"]

    # Process joints parent-first.
    pending = list(joints)
    while pending:
        progressed = False
        for j in list(pending):
            parent_link = j.find("parent").get("link")
            if parent_link not in link_objects:
                continue
            child_link = j.find("child").get("link")
            name = j.get("name")
            origin = j.find("origin")
            xyz = parse_xyz(origin.get("xyz") if origin is not None else None)
            rpy = parse_xyz(origin.get("rpy") if origin is not None else None)

            # Fixed URDF origin (URDF rpy == Blender XYZ Euler).
            origin_obj = bpy.data.objects.new(f"{name}_origin", None)
            bpy.context.collection.objects.link(origin_obj)
            origin_obj.parent = link_objects[parent_link]
            origin_obj.location = xyz
            origin_obj.rotation_euler = Euler(rpy, "XYZ")

            # Rotating joint frame: posed around the joint axis.
            joint_obj = bpy.data.objects.new(name, None)
            bpy.context.collection.objects.link(joint_obj)
            joint_obj.parent = origin_obj
            axis_el = j.find("axis")
            if axis_el is not None and name in STAND_INIT:
                axis = parse_xyz(axis_el.get("xyz")).normalized()
                joint_obj.rotation_mode = "QUATERNION"
                joint_obj.rotation_quaternion = Matrix.Rotation(STAND_INIT[name], 4, axis).to_quaternion()
            joint_obj["urdf_axis"] = axis_el.get("xyz") if axis_el is not None else ""

            link_objects[child_link] = joint_obj
            pending.remove(j)
            progressed = True
        if not progressed:
            break

    # Attach meshes to their links.
    for link, mesh_name in LINK_MESH.items():
        if link not in link_objects:
            print(f"[pepper] warning: link {link} not built")
            continue
        # Each object gets its own copy: FBX export mis-assigns material slots on shared mesh data.
        obj = bpy.data.objects.new(f"{mesh_name}_mesh" if link == "torso" else f"{link}_mesh",
                                   build_mesh_data(mesh_name, mats).copy())
        bpy.context.collection.objects.link(obj)
        obj.parent = link_objects[link]

    # Stand on the ground: move the torso so base_footprint ends at z = 0.
    bpy.context.view_layer.update()
    link_objects["torso"].location = (0, 0, 0)
    bpy.context.view_layer.update()
    footprint = link_objects.get("base_footprint")
    lift = -footprint.matrix_world.translation.z if footprint else 0.82
    link_objects["torso"].location = (0, 0, lift)
    bpy.context.view_layer.update()
    return root


def render_preview(path):
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    # Robot faces -Y; view from the front-right, slightly above.
    cam.location = (1.2, -2.4, 1.15)
    direction = Vector((0, 0, 0.62)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 50
    scene.camera = cam

    light_data = bpy.data.lights.new("Key", "SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("Key", light_data)
    light.rotation_euler = Euler((math.radians(50), 0, math.radians(30)))
    scene.collection.objects.link(light)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.58, 0.62, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    scene.world = world

    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in \
        [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1100
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

    # Keep preview-only objects out of the exported model.
    for obj in (cam, light):
        bpy.data.objects.remove(obj, do_unlink=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tex_out = os.path.join(OUT_DIR, "Textures")
    os.makedirs(tex_out, exist_ok=True)
    for tex in TEXTURES.values():
        shutil.copy2(os.path.join(MESH_DIR, tex), os.path.join(tex_out, tex))

    reset_scene()
    mats = make_materials(tex_out)
    build_robot(mats)

    render_preview(os.path.join(OUT_DIR, "Pepper_preview.png"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "Pepper.blend"))

    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT_DIR, "Pepper.fbx"),
        object_types={"EMPTY", "MESH"},
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y",
        add_leaf_bones=False,
        mesh_smooth_type="OFF",
        path_mode="RELATIVE",
        use_custom_props=True,
    )
    print(f"[pepper] done -> {OUT_DIR}")


main()
