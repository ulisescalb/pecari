"""
Renders de revision estilo arcilla para el pecari.

Se llama desde build_pecari.py, o de forma independiente sobre un .blend ya generado:
    blender -b blend/pecari_v01.blend -P src/render_views.py -- --version v01

Vistas: front, side, top (ortograficas), three_quarter, head (perspectiva),
silhouette_side (negro sobre blanco) y una hoja de contacto.
Motor: Cycles GPU (OptiX > CUDA > HIP > oneAPI > Metal) si hay dispositivo; si no,
Eevee cuando hay contexto grafico; si tampoco, Cycles CPU.
"""
import bpy
import os
import sys
import math
import json
import ctypes.util

import numpy as np
from mathutils import Vector

VIEWS = ["front", "side", "top", "three_quarter", "head", "silhouette_side"]


# ----------------------------------------------------------------------------
# Motor
# ----------------------------------------------------------------------------
def _gpu_cycles(scene):
    try:
        cp = bpy.context.preferences.addons["cycles"].preferences
    except Exception:
        return None
    for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            cp.compute_device_type = dev
        except Exception:
            continue
        try:
            if hasattr(cp, "refresh_devices"):
                cp.refresh_devices()
            else:
                cp.get_devices()
        except Exception:
            pass
        devs = [d for d in cp.devices if d.type == dev]
        if devs:
            for d in cp.devices:
                d.use = d.type == dev
            scene.render.engine = "CYCLES"
            scene.cycles.device = "GPU"
            return "Cycles GPU %s (%s)" % (dev, ", ".join(d.name for d in devs))
    return None


def _eevee_possible():
    if sys.platform.startswith("linux"):
        has_gl = ctypes.util.find_library("EGL") or ctypes.util.find_library("GL")
        has_dev = os.path.exists("/dev/dri") or os.environ.get("DISPLAY")
        return bool(has_gl and has_dev)
    return True


def _set_eevee(scene):
    for eid in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eid
            return "Eevee (%s)" % eid
        except Exception:
            continue
    return None


def setup_engine(scene, pref="auto", samples=96):
    name = None
    if pref in ("auto", "cycles_gpu"):
        name = _gpu_cycles(scene)
    if name is None and pref in ("auto", "eevee") and _eevee_possible():
        name = _set_eevee(scene)
    if name is None:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        name = "Cycles CPU"
    if scene.render.engine == "CYCLES":
        c = scene.cycles
        c.samples = samples
        try:
            c.use_adaptive_sampling = True
            c.adaptive_threshold = 0.02
        except Exception:
            pass
        c.max_bounces = 4
        c.diffuse_bounces = 3
        c.glossy_bounces = 1
        c.transmission_bounces = 0
        c.transparent_max_bounces = 2
        try:
            c.use_denoising = True
            c.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            try:
                c.use_denoising = False
            except Exception:
                pass
    else:
        try:
            scene.eevee.taa_render_samples = max(32, samples)
        except Exception:
            pass
    return name


# ----------------------------------------------------------------------------
# Materiales, mundo, luces
# ----------------------------------------------------------------------------
def principled(name, color, rough=0.6, spec=0.25):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = spec
            break
    return m


def black_emission():
    m = bpy.data.materials.get("Sil_Black") or bpy.data.materials.new("Sil_Black")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    em.inputs["Strength"].default_value = 0.0
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def set_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def setup_world(scene, bg, ambient=0.03):
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    lp = nt.nodes.new("ShaderNodeLightPath")
    b_cam = nt.nodes.new("ShaderNodeBackground")
    b_cam.inputs["Color"].default_value = (*bg, 1)
    b_cam.inputs["Strength"].default_value = 1.0
    b_amb = nt.nodes.new("ShaderNodeBackground")
    b_amb.inputs["Color"].default_value = (1, 1, 1, 1)
    b_amb.inputs["Strength"].default_value = ambient
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(b_amb.outputs[0], mix.inputs[1])
    nt.links.new(b_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def clear_lights():
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_area(name, loc, target, power, size):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = power
    ld.size = size
    o = bpy.data.objects.new("RV_" + name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


LIGHT_W = {"key": 90.0, "fill": 8.0, "rim": 70.0}


def three_point(target, cam_dir, dist=3.0, scale=1.0):
    """Luz de tres puntos relativa a la direccion de camara (vector camara->objetivo)."""
    clear_lights()
    t = Vector(target)
    f = Vector(cam_dir).normalized()            # hacia donde mira la camara
    up = Vector((0, 0, 1))
    if abs(f.dot(up)) > 0.95:
        up = Vector((0, -1, 0))
    right = f.cross(up).normalized()
    upv = right.cross(f).normalized()
    back = -f
    key = t + (back * 0.75 + (-right) * 0.8 + upv * 0.9).normalized() * dist
    fill = t + (back * 0.9 + right * 0.9 + upv * 0.2).normalized() * dist
    rim = t + (f * 0.9 + right * 0.35 + upv * 1.0).normalized() * dist
    p = (dist / 3.0) ** 2 * scale
    add_area("Key", key, t, LIGHT_W["key"] * p, 1.6)
    add_area("Fill", fill, t, LIGHT_W["fill"] * p, 2.0)
    add_area("Rim", rim, t, LIGHT_W["rim"] * p, 1.2)


def camera(name, loc, target=None, rot=None, ortho=None, lens=50.0):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    o = bpy.data.objects.get("RV_" + name)
    if o is None:
        o = bpy.data.objects.new("RV_" + name, cd)
        bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if rot is not None:
        o.rotation_euler = rot
    else:
        look_at(o, target)
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.type = "PERSP"
        cd.lens = lens
    cd.clip_start = 0.01
    cd.clip_end = 50
    bpy.context.scene.camera = o
    return o


def fit_distance(V, target, direction, lens, fill, sensor=36.0):
    """Distancia de camara (perspectiva, cuadro cuadrado) para que la nube V ocupe 'fill'
    del lado mayor del cuadro, mirando a 'target' desde 'target + direction * d'."""
    f = -Vector(direction).normalized()
    up = Vector((0, 0, 1))
    right = f.cross(up).normalized()
    upv = right.cross(f).normalized()
    t = np.array(target[:])
    Q = np.asarray(V, float) - t
    a = Q @ np.array(right[:])
    b = Q @ np.array(upv[:])
    c = Q @ np.array(f[:])
    half = (sensor / 2.0) / lens * fill
    lo_d, hi_d = 0.05, 20.0
    for _ in range(60):
        d = 0.5 * (lo_d + hi_d)
        depth = d + c
        m = np.max(np.maximum(np.abs(a), np.abs(b)) / np.maximum(depth, 1e-3))
        if m > half:
            lo_d = d
        else:
            hi_d = d
    return hi_d


def ground(color):
    me = bpy.data.meshes.new("RV_ground")
    s = 8.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new("RV_ground", me)
    bpy.context.scene.collection.objects.link(o)
    set_material(o, principled("RV_ground_mat", color, 0.9, 0.1))
    o.location.z = -0.0005
    return o


# ----------------------------------------------------------------------------
# Hoja de contacto (numpy sobre imagenes de Blender)
# ----------------------------------------------------------------------------
def contact_sheet(paths, out_path, cols=3, cell=512):
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p, check_existing=False)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        step = max(1, w // cell)
        a = a[::step, ::step][:cell, :cell]
        imgs.append(a)
        bpy.data.images.remove(im)
    rows = int(math.ceil(len(imgs) / cols))
    sheet = np.ones((rows * cell, cols * cell, 4), np.float32)
    for i, a in enumerate(imgs):
        r, c = divmod(i, cols)
        r = rows - 1 - r  # las filas de Blender van de abajo a arriba
        sheet[r * cell:r * cell + a.shape[0], c * cell:c * cell + a.shape[1]] = a
    out = bpy.data.images.new("RV_sheet", cols * cell, rows * cell, alpha=True)
    out.pixels = sheet.ravel()
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)


# ----------------------------------------------------------------------------
# Render principal
# ----------------------------------------------------------------------------
def render_all(objs, out_dir, R, args=None, info=None):
    scene = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    samples = (getattr(args, "samples", None) or R.get("samples", 96))
    res = (getattr(args, "res", None) or R.get("resolution", 1024))
    pref = getattr(args, "engine", "auto") or "auto"
    engine = setup_engine(scene, pref, samples)
    print("[render] motor:", engine, flush=True)
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except Exception:
        pass
    scene.view_settings.exposure = R.get("exposure", 0.0)
    LIGHT_W.update({"key": R.get("key_w", 90.0), "fill": R.get("fill_w", 8.0), "rim": R.get("rim_w", 70.0)})

    clay = principled("RV_clay", R["clay_color"], 0.62, 0.22)
    eye = principled("RV_eye", R["eye_color"], 0.25, 0.5)
    tooth = principled("RV_tooth", R["tooth_color"], 0.45, 0.3)
    for n, o in objs.items():
        set_material(o, eye if "Eye" in n else tooth if "Canine" in n else clay)

    V = np.vstack([np.array([v.co[:] for v in o.data.vertices]) for o in objs.values()])
    lo, hi = V.min(0), V.max(0)
    ctr = 0.5 * (lo + hi)
    zc = 0.5 * (lo[2] + hi[2])
    head_c = Vector(info["head_center"]) if info and "head_center" in info else Vector(ctr)

    gnd = ground(R["ground_color"])
    setup_world(scene, R["background"], ambient=R.get("ambient", 0.015))
    out = {}

    def shoot(name):
        path = os.path.join(out_dir, name + ".png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out[name] = path
        print("[render]", name, flush=True)

    D = 5.0
    fill = R.get("fill", 0.88)       # fraccion del cuadro que ocupa la dimension mayor del animal
    ext = hi - lo
    # frente (mira hacia +Y)
    camera("front", (0, ctr[1] - D, zc), rot=(math.radians(90), 0, 0),
           ortho=max(2 * max(abs(lo[0]), abs(hi[0])), ext[2]) / fill)
    three_point((0, ctr[1], zc), (0, 1, 0), 3.0)
    shoot("front")
    # lado izquierdo (+X mira hacia -X)
    side_scale = max(ext[1], ext[2]) / fill
    camera("side", (D, ctr[1], zc), rot=(math.radians(90), 0, math.radians(90)), ortho=side_scale)
    three_point((0, ctr[1], zc), (-1, 0, 0), 3.0)
    shoot("side")
    # arriba (cabeza hacia arriba en la imagen)
    camera("top", (0, ctr[1], D), rot=(0, 0, math.radians(180)),
           ortho=max(2 * max(abs(lo[0]), abs(hi[0])), ext[1]) / fill)
    three_point((0, ctr[1], 0.2), (0.25, 0.35, -1), 3.0)
    shoot("top")
    # 3/4 delantero izquierdo
    d34 = Vector((0.72, -0.62, 0.32)).normalized()
    tgt = Vector((0, ctr[1], zc))
    camera("three_quarter", tgt + d34 * fit_distance(V, tgt, d34, 50, fill), target=tgt, lens=50)
    three_point(tgt, -d34, 3.0)
    shoot("three_quarter")
    # primer plano de cabeza
    dh = Vector((0.62, -0.70, 0.30)).normalized()
    HV = np.vstack([np.array([v.co[:] for v in o.data.vertices]) for n, o in objs.items()
                    if any(k in n for k in ("Head", "Jaw", "Ear", "Eye", "Canine"))])
    head_c = Vector(0.5 * (HV.min(0) + HV.max(0)))
    camera("head", head_c + dh * fit_distance(HV, head_c, dh, 85, fill), target=head_c, lens=85)
    three_point(head_c, -dh, 2.0)
    shoot("head")
    # silueta lateral negro sobre blanco
    gnd.hide_render = True
    blk = black_emission()
    saved = {n: [m for m in o.data.materials] for n, o in objs.items()}
    for o in objs.values():
        set_material(o, blk)
    setup_world(scene, (1, 1, 1), ambient=0.0)
    camera("side", (D, ctr[1], zc), rot=(math.radians(90), 0, math.radians(90)), ortho=side_scale)
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 16
        try:
            scene.cycles.use_denoising = False
        except Exception:
            pass
    scene.view_settings.exposure = 0.0
    shoot("silhouette_side")
    scene.view_settings.exposure = R.get("exposure", 0.0)
    for n, o in objs.items():
        o.data.materials.clear()
        for m in saved[n]:
            o.data.materials.append(m)
    try:
        contact_sheet([out[v] for v in VIEWS], os.path.join(out_dir, "contact_sheet.png"))
    except Exception as e:
        print("[render] aviso hoja de contacto:", e)
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = min(samples, 48)
    render_vertex_groups(objs, out_dir, R)
    render_wire_head(objs, out_dir, info)
    return engine


GROUP_COLORS = {"fur_face": (0.90, 0.60, 0.50), "fur_legs": (1.0, 0.80, 0.10),
                "fur_belly": (0.10, 0.30, 1.0), "fur_mane": (1.0, 0.10, 0.10),
                "fur_collar": (0.10, 1.0, 0.10), "bare_hooves": (0.60, 0.10, 0.90),
                "bare_snout": (0.10, 0.90, 0.90)}


def render_vertex_groups(objs, out_dir, R):
    """Vista de control de los grupos de pelaje (colores mezclados por peso)."""
    scene = bpy.context.scene
    saved = {n: [m for m in o.data.materials] for n, o in objs.items()}
    for n, o in objs.items():
        me = o.data
        nv = len(me.vertices)
        C = np.full((nv, 3), 0.35)
        for g, col in GROUP_COLORS.items():
            vg = o.vertex_groups.get(g)
            if vg is None:
                continue
            for v in me.vertices:
                for ge in v.groups:
                    if ge.group == vg.index and ge.weight > 0:
                        C[v.index] = C[v.index] * (1 - ge.weight) + np.array(col) * ge.weight
        ca = me.color_attributes.new("RV_groups", "FLOAT_COLOR", "POINT")
        ca.data.foreach_set("color", np.hstack([C, np.ones((nv, 1))]).ravel())
        m = bpy.data.materials.get("RV_groups_mat")
        if m is None:
            m = bpy.data.materials.new("RV_groups_mat")
            m.use_nodes = True
            nt = m.node_tree
            a = nt.nodes.new("ShaderNodeAttribute")
            a.attribute_name = "RV_groups"
            nt.links.new(a.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        set_material(o, m)
    setup_world(scene, (0.8, 0.8, 0.8), ambient=0.4)
    t = Vector((0, 0, 0.22))
    for name, d in (("groups_three_quarter", Vector((0.72, -0.62, 0.40))),
                    ("groups_below", Vector((0.50, -0.30, -0.35)))):
        d = d.normalized()
        camera(name, t + d * 1.9, target=t, lens=50)
        three_point(t, -d, 3.0)
        scene.render.filepath = os.path.join(out_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("[render]", name, flush=True)
    for n, o in objs.items():
        o.data.materials.clear()
        for m in saved[n]:
            o.data.materials.append(m)
        ca = o.data.color_attributes.get("RV_groups")
        if ca is not None:
            o.data.color_attributes.remove(ca)


def render_wire_head(objs, out_dir, info):
    """Primer plano de la cabeza con la malla en alambre (bucles de parpados y comisura)."""
    scene = bpy.context.scene
    clay = principled("RV_wire_clay", (0.6, 0.6, 0.6), 0.6, 0.2)
    dark = principled("RV_wire_dark", (0.01, 0.01, 0.01), 0.9, 0.0)
    eye = principled("RV_eye", (0.05, 0.05, 0.05), 0.3, 0.5)
    saved = {n: [m for m in o.data.materials] for n, o in objs.items()}
    wires = []
    for n, o in objs.items():
        set_material(o, eye if "Eye" in n else clay)
        w = bpy.data.objects.new("RV_WF_" + n, o.data.copy())
        scene.collection.objects.link(w)
        md = w.modifiers.new("wf", "WIREFRAME")
        md.thickness = 0.00035
        md.use_replace = True
        set_material(w, dark)
        wires.append(w)
    setup_world(scene, (0.85, 0.85, 0.85), ambient=0.35)
    c = Vector(info["head_center"]) if info and "head_center" in info else Vector((0, -0.4, 0.3))
    d = Vector((0.85, -0.45, 0.25)).normalized()
    camera("wire_head", c + d * 0.62, target=c, lens=85)
    three_point(c, -d, 1.5)
    scene.render.filepath = os.path.join(out_dir, "wire_head.png")
    bpy.ops.render.render(write_still=True)
    print("[render] wire_head", flush=True)
    for w in wires:
        me = w.data
        bpy.data.objects.remove(w, do_unlink=True)
        bpy.data.meshes.remove(me)
    for n, o in objs.items():
        o.data.materials.clear()
        for m in saved[n]:
            o.data.materials.append(m)


def _standalone():
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="vXX")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--res", type=int, default=None)
    ap.add_argument("--params", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.json"))
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(args.params) as fh:
        P = json.load(fh)
    objs = {o.name: o for o in bpy.data.objects if o.name.startswith("Pecari_") and o.type == "MESH"}
    head = objs.get("Pecari_Head")
    hc = np.mean([v.co[:] for v in head.data.vertices], axis=0).tolist() if head else None
    render_all(objs, os.path.join(root, "renders", args.version), P["render"], args,
               info={"head_center": hc} if hc else None)


if __name__ == "__main__":
    _standalone()
