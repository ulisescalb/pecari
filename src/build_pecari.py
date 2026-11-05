"""
Pecari de collar (Pecari tajacu) - Etapa 1: malla base.

Uso (desde la carpeta pecari):
    blender -b -P src/build_pecari.py -- --version v01 [--params src/params.json]
                                          [--no-render] [--samples N] [--engine auto|cycles_gpu|cycles_cpu|eevee]

Metodo: para cada pieza se construye una "jaula" de quads con la topologia deseada
(anillos en articulaciones, tapas en rejilla), se subdivide con Catmull-Clark y los
vertices se proyectan sobre un campo de distancia con signo (SDF) definido en
params.json (barridos de secciones superelipticas + conos redondeados + elipsoides
con uniones suaves). Una relajacion tangencial reparte los vertices sobre la
superficie. No se usa Remesh: la topologia sale de la jaula.
"""
import bpy
import bmesh
import sys
import os
import json
import math
import time
import argparse

import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from pecari_sdf import *  # noqa: F401,F403  (modelo numerico compartido)
from pecari_sdf import (smoothstep, normalize, num_grad, smin, smax, Sweep, BodyField, HeadField,
                        JawField, project, project_normal, relax, field_laplacian, surface_along,
                        field_normal, MeshBuilder, mirror_k, head_transform, to_world, to_can)

T0 = time.time()


def log(*a):
    print("[pecari %6.1fs]" % (time.time() - T0), *a, flush=True)


# ----------------------------------------------------------------------------
# Argumentos
# ----------------------------------------------------------------------------
def parse_args():
    if "--" in sys.argv:                       # blender -b -P build_pecari.py -- ...
        argv = sys.argv[sys.argv.index("--") + 1:]
    elif sys.argv and sys.argv[0].endswith(".py"):   # python build_pecari.py ... (bpy de PyPI)
        argv = sys.argv[1:]
    else:
        argv = []
    ap = argparse.ArgumentParser(prog="build_pecari.py")
    ap.add_argument("--version", default="v01")
    ap.add_argument("--params", default=os.path.join(SRC, "params.json"))
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--res", type=int, default=None)
    return ap.parse_args(argv)



# ----------------------------------------------------------------------------
# Objetos Blender
# ----------------------------------------------------------------------------
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                 bpy.data.images, bpy.data.worlds):
        for d in list(coll):
            try:
                coll.remove(d)
            except Exception:
                pass
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def make_object(name, verts, faces, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    me.update()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    fix_normals(obj)
    return obj


def fix_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def subdivide(obj, levels):
    if levels <= 0:
        return
    mod = obj.modifiers.new("cc", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    mod.quality = 3
    try:
        mod.uv_smooth = "NONE"
        mod.use_limit_surface = True
    except Exception:
        pass
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    obj.modifiers.remove(mod)
    old = obj.data
    obj.data = me
    me.name = obj.name
    bpy.data.meshes.remove(old)


def get_V(obj):
    me = obj.data
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def get_E(obj):
    me = obj.data
    E = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", E)
    return E.reshape(-1, 2)


def set_V(obj, V):
    obj.data.vertices.foreach_set("co", np.asarray(V, float).ravel())
    obj.data.update()


def get_N(obj):
    me = obj.data
    me.update()
    N = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", N)
    return N.reshape(-1, 3)


def shade_smooth(obj):
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()


def grid_patch(bm, target, rings):
    """Parche de caras alrededor del vertice mas cercano a 'target'."""
    bm.verts.ensure_lookup_table()
    best = min(bm.verts, key=lambda v: (v.co - Vector(target)).length)
    faces = set(best.link_faces)
    for _ in range(rings):
        vs = {v for f in faces for v in f.verts}
        faces |= {f for v in vs for f in v.link_faces}
    return list(faces), best


def inset_loops(obj, target, rings, thicknesses):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    faces, _ = grid_patch(bm, target, rings)
    nf0 = len(faces)
    for t in thicknesses:
        bmesh.ops.inset_region(bm, faces=faces, thickness=t, depth=0.0,
                               use_even_offset=True, use_boundary=False)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return nf0



def build_tube_object(name, sweep, rings_y, nring, inflate, capf, capb, axis_front, coll,
                      skip=None, extra=None):
    mb = MeshBuilder()
    rings = [mb.add_verts(sweep.ring(y, nring, inflate)) for y in rings_y]
    for i in range(len(rings) - 1):
        mb.bridge(rings[i], rings[i + 1], skip=(skip or {}).get(i, ()))
    mb.cap(rings[0], capf["a"], capf["b"], axis_front, capf["dome"])
    mb.cap(rings[-1], capb["a"], capb["b"], -np.asarray(axis_front), capb["dome"])
    if extra:
        extra(mb, rings)
    return make_object(name, mb.verts, mb.faces, coll), rings


def build_body(P, coll):
    B = P["body"]
    legs = [P["legs"]["front"], P["legs"]["hind"]]
    field = BodyField(B, legs)
    C = B["cage"]
    n = C["nring"]
    kout, kin = n // 3, n // 3 + 1         # 4, 5 para n=12 (cara inferior-lateral)
    skip = {}
    for L in legs:
        i = L["root_ring"]
        skip.setdefault(i, set()).update({kout, mirror_k(kin, n)})  # caras k=4 (4-5) y k=7 (7-8)

    def add_legs(mb, rings):
        for L in legs:
            i = L["root_ring"]
            for side in (1, -1):
                if side == 1:
                    root = [rings[i][kout], rings[i][kin], rings[i + 1][kin], rings[i + 1][kout]]
                else:
                    ko, ki = mirror_k(kout, n), mirror_k(kin, n)
                    root = [rings[i][ko], rings[i][ki], rings[i + 1][ki], rings[i + 1][ko]]
                prev = root
                # centros de la cadena (lado izquierdo) para orientar cada anillo
                # perpendicular al eje local de la pata; la suela queda horizontal
                rc = np.mean([mb.verts[k] for k in root], axis=0) * np.array([side, 1, 1])
                cen = [rc] + [np.array(c[:3], float) for c in L["cage"]]
                ncage = len(L["cage"])
                for j, (cx, cy, cz, hx, hy) in enumerate(L["cage"]):
                    c = cen[j + 1]
                    if j == ncage - 1:
                        t = np.array([0.0, 0.0, -1.0])
                    else:
                        t = normalize(cen[j + 2] - cen[j])
                    f0 = np.array([0.0, -1.0, 0.0])
                    f = normalize(f0 - (f0 @ t) * t)
                    lat = normalize(np.cross(f, t))
                    pts = [c + hy * f + hx * lat, c + hy * f - hx * lat,
                           c - hy * f - hx * lat, c - hy * f + hx * lat]
                    pts = [p * np.array([side, 1, 1]) for p in pts]
                    cur = mb.add_verts(pts)
                    mb.bridge(prev, cur)
                    prev = cur
                mb.faces.append(list(prev))  # suela

    obj, rings = build_tube_object("Pecari_Body", field.sweep, C["rings_y"], n, C["inflate"],
                                   C["cap_front"], C["cap_rear"], [0, -1, 0], coll,
                                   skip=skip, extra=add_legs)
    cage_faces = len(obj.data.polygons)
    subdivide(obj, B["subdiv"])
    V = get_V(obj)
    E = get_E(obj)
    mid = np.abs(V[:, 0]) < 1e-6
    V[mid, 0] = 0.0
    V = project_normal(V, get_N(obj), field, mid=mid)
    V = project(V, field, B["project_iters"], mid=mid)
    # relajacion en dos fases: suave en todo el cuerpo (conserva salientes como el
    # corvejon) y fuerte solo en pliegues concavos (axilas, ingles), donde la
    # proyeccion amontona vertices
    V = relax(V, E, field, B["relax_iters"], B["relax_lambda"], mid=mid,
              convex_damp=B.get("relax_convex_damp", 0.0))
    if B.get("crease_relax_iters", 0) > 0:
        lap = field_laplacian(field, V)
        wc = 1.0 - smoothstep(-B["crease_lap"], B["crease_lap"], lap)
        # dilatar la mascara a los vecinos
        acc = np.zeros(len(V))
        np.maximum.at(acc, E[:, 0], wc[E[:, 1]])
        np.maximum.at(acc, E[:, 1], wc[E[:, 0]])
        wc = np.maximum(wc, acc)
        V = relax(V, E, field, B["crease_relax_iters"], 0.45, mid=mid, weight=wc)
    V = project(V, field, 4, mid=mid)
    set_V(obj, V)
    fix_normals(obj)
    log("Body: jaula %d caras -> %d caras" % (cage_faces, len(obj.data.polygons)))
    return obj, field


def build_head(P, coll):
    H = P["head"]
    EYE = P["eye"]
    base = HeadField(H)
    C = H["cage"]
    obj, _ = build_tube_object("Pecari_Head", base.sweep, C["rings_u"], C["nring"], C["inflate"],
                               C["cap_front"], C["cap_back"], [0, -1, 0], coll)
    cage_faces = len(obj.data.polygons)
    subdivide(obj, H["subdiv"])
    V = get_V(obj)
    E = get_E(obj)
    mid = np.abs(V[:, 0]) < 1e-6
    V[mid, 0] = 0.0
    V = project_normal(V, get_N(obj), base, mid=mid)
    V = project(V, base, H["project_iters"], mid=mid)
    V = relax(V, E, base, H["relax_iters"], H["relax_lambda"], mid=mid)
    set_V(obj, V)

    # --- ojo: punto de superficie, centro hundido, cuenca ---
    eye_surf = surface_along(base, [0.0, EYE["u"], EYE["z"]], [1, 0, 0])
    nrm = field_normal(base, eye_surf)
    eye_c = eye_surf - nrm * EYE["depth"]
    rs = (EYE["radius"] + EYE["socket_gap"]) * np.asarray(EYE["socket_scale"], float)
    rs = np.maximum(rs, EYE["radius"] + EYE["socket_gap"])
    field = HeadField(H, socket=(eye_c, rs, EYE["socket_k"]))

    # --- comisura: punto de superficie ---
    MC = H["mouth_corner"]
    mouth_surf = surface_along(base, [0.0, MC["u"], MC["z"]], [1, 0, 0])

    # bucles concentricos (parpados y comisura) en ambos lados
    for side in (1, -1):
        es = eye_surf * np.array([side, 1, 1])
        inset_loops(obj, es, 1, H["inset_eye"])
        ms = mouth_surf * np.array([side, 1, 1])
        inset_loops(obj, ms, 0, H["inset_mouth"])
    V = get_V(obj)
    E = get_E(obj)
    mid = np.abs(V[:, 0]) < 1e-6
    V[mid, 0] = 0.0
    V = project(V, field, 8, mid=mid)
    V = relax(V, E, field, 8, 0.4, mid=mid)
    V = project(V, field, 4, mid=mid)
    set_V(obj, V)
    fix_normals(obj)
    log("Head: jaula %d caras -> %d caras" % (cage_faces, len(obj.data.polygons)))
    info = {"eye_c": eye_c, "eye_surf": eye_surf, "mouth_surf": mouth_surf}
    return obj, field, base, info


def build_jaw(P, coll):
    J = P["jaw"]
    field = JawField(J)
    C = J["cage"]
    obj, _ = build_tube_object("Pecari_LowerJaw", field.sweep, C["rings_u"], C["nring"],
                               C["inflate"], C["cap_front"], C["cap_back"], [0, -1, 0], coll)
    cage_faces = len(obj.data.polygons)
    subdivide(obj, J["subdiv"])
    V = get_V(obj)
    E = get_E(obj)
    mid = np.abs(V[:, 0]) < 1e-6
    V[mid, 0] = 0.0
    V = project_normal(V, get_N(obj), field, mid=mid)
    V = project(V, field, J["project_iters"], mid=mid)
    V = relax(V, E, field, J["relax_iters"], J["relax_lambda"], mid=mid)
    set_V(obj, V)
    # comisura en la mandibula
    MC = P["head"]["mouth_corner"]
    try:
        ms = surface_along(field, [0.0, MC["u"], MC["z"] - 0.004], [1, 0, 0])
        for side in (1, -1):
            inset_loops(obj, ms * np.array([side, 1, 1]), 0, P["head"]["inset_mouth"])
        V = get_V(obj)
        E = get_E(obj)
        mid = np.abs(V[:, 0]) < 1e-6
        V = project(V, field, 6, mid=mid)
        V = relax(V, E, field, 6, 0.4, mid=mid)
        V = project(V, field, 3, mid=mid)
        set_V(obj, V)
    except RuntimeError as e:
        log("aviso comisura mandibula:", e)
    fix_normals(obj)
    log("Jaw: jaula %d caras -> %d caras" % (cage_faces, len(obj.data.polygons)))
    return obj, field


def build_eye(name, center_w, radius, cuts, coll):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized() * radius + Vector(center_w)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    fix_normals(obj)
    return obj


def build_ear(name, side, base_w, P_ear, coll):
    A = P_ear
    L = A["length"]
    e3 = normalize(np.array(A["dir_world"]) * np.array([side, 1, 1]))
    back = np.array(A["back_world"], float) * np.array([side, 1, 1])
    e2 = normalize(back - (back @ e3) * e3)          # dorso convexo
    e1 = np.cross(e2, e3)                              # ancho
    n = A["nring"]
    mb = MeshBuilder()
    rings = []
    for t, W, D, Cp in zip(A["t"], A["half_width"], A["back_bulge"], A["cup"]):
        c = base_w + e3 * (t * L) + e2 * (A["bend"] * max(t, 0) ** 2)
        pts = []
        for k in range(n):
            ph = 2 * math.pi * k / n
            cx, sy = math.cos(ph), math.sin(ph)
            if sy >= 0:
                y = D * sy
            else:
                y = (Cp - A["front_thick"]) * abs(sy)
            pts.append(c + e1 * (W * cx) + e2 * y)
        rings.append(mb.add_verts(pts))
    for i in range(len(rings) - 1):
        mb.bridge(rings[i], rings[i + 1])
    mb.cap(rings[-1], 4, 2, e3, 0.25 * A["half_width"][-1])
    mb.cap(rings[0], 4, 2, -e3, 0.004)
    obj = make_object(name, mb.verts, mb.faces, coll)
    subdivide(obj, A["subdiv"])
    fix_normals(obj)
    return obj, e3


def build_canine(name, side, root_w, dir_w, P_c, coll):
    A = P_c
    ax = normalize(dir_w)
    ref = np.array([0.0, -1.0, 0.0])
    e1 = normalize(ref - (ref @ ax) * ax)   # adelante-atras
    e2 = np.cross(ax, e1)                   # lateral
    n = A["nring"]
    mb = MeshBuilder()
    rings = []
    for t, r in zip(A["t"], A["radius"]):
        c = root_w + ax * (t * A["length"])
        pts = []
        for k in range(n):
            ph = 2 * math.pi * k / n
            pts.append(c + e1 * (r * math.cos(ph)) + e2 * (r * A["flatten"] * math.sin(ph)))
        rings.append(mb.add_verts(pts))
    for i in range(len(rings) - 1):
        mb.bridge(rings[i], rings[i + 1])
    mb.cap(rings[-1], 2, 2, ax, 0.0005)
    mb.cap(rings[0], 2, 2, -ax, 0.001)
    obj = make_object(name, mb.verts, mb.faces, coll)
    return obj, ax


# ----------------------------------------------------------------------------
# Grupos de vertices
# ----------------------------------------------------------------------------
def assign_group(obj, name, w):
    vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    w = np.clip(np.asarray(w, float), 0.0, 1.0)
    idx = np.nonzero(w > 1e-3)[0]
    for i in idx:
        vg.add([int(i)], float(w[i]), "REPLACE")
    return int((w > 0.5).sum())


def compute_groups(P, objs, body_field, R, T):
    VG = P["vertex_groups"]
    LM = P["landmarks"]
    stats = {}
    # clasificacion torso/patas en el cuerpo
    Vb = get_V(objs["Pecari_Body"])
    dt, dls = body_field.components(Vb)
    dl = np.minimum(dls[0], dls[1])
    front = Vb[:, 1] < 0
    zmax = np.where(front, LM["leg_zmax_front"], LM["leg_zmax_hind"])
    leg_w = smoothstep(-0.002, 0.004, dt - dl) * (1 - smoothstep(zmax - 0.02, zmax, Vb[:, 2]))
    leg_w = np.maximum(leg_w, (Vb[:, 2] < 0.15).astype(float))
    cache = {"Pecari_Body": {"leg": leg_w}}

    for gname, g in VG.items():
        if gname.startswith("_"):
            continue
        for oname in g["objects"]:
            obj = objs[oname]
            V = get_V(obj)
            N = get_N(obj)
            leg = cache.get(oname, {}).get("leg", np.zeros(len(V)))
            rule = g["rule"]
            if rule == "dorsal_band":
                hw_tab = np.array(g["half_width"], float)
                hw = np.interp(V[:, 1], hw_tab[:, 0], hw_tab[:, 1])
                w = 1 - smoothstep(hw - g["edge"], hw, np.abs(V[:, 0]))
                w *= smoothstep(g["nz_min"], g["nz_min"] + 0.25, N[:, 2])
                y0, y1 = g["y_range"]
                w *= smoothstep(y0, y0 + g["ramp"], V[:, 1]) * (1 - smoothstep(y1 - g["ramp"], y1, V[:, 1]))
                w *= (1 - leg)
            elif rule == "plane_band":
                p0 = np.array(g["p0"], float)
                p1 = np.array(g["p1"], float)
                dvec = normalize(p1 - p0)
                nn = np.array([-dvec[1], dvec[0]])
                q = V[:, 1:3] - p0
                dist = np.abs(q @ nn)
                w = 1 - smoothstep(g["half_width"] - g["edge"], g["half_width"], dist)
                w *= (1 - leg)
            elif rule == "ventral":
                y0, y1 = g["y_range"]
                w = smoothstep(-g["nz_max"], -g["nz_max"] + g["edge"], -N[:, 2])
                w *= smoothstep(y0, y0 + g["ramp"], V[:, 1]) * (1 - smoothstep(y1 - g["ramp"], y1, V[:, 1]))
                w *= (1 - leg)
            elif rule == "legs":
                w = leg * smoothstep(LM["hoof_top_z"], LM["hoof_top_z"] + 0.006, V[:, 2])
            elif rule == "hooves":
                w = leg * (1 - smoothstep(LM["hoof_top_z"] - g["edge"], LM["hoof_top_z"] + 0.5 * g["edge"], V[:, 2]))
            elif rule == "face":
                if oname == "Pecari_Head":
                    u = to_can(V, R, T)[:, 1]
                    sg = VG["bare_snout"]
                    w = smoothstep(sg["u_full"], sg["u_zero"], u)
                else:
                    w = np.ones(len(V))
            elif rule == "disc":
                u = to_can(V, R, T)[:, 1]
                w = 1 - smoothstep(g["u_full"], g["u_zero"], u)
            else:
                raise ValueError("regla desconocida %s" % rule)
            stats.setdefault(gname, {})[oname] = assign_group(obj, gname, w)
    return stats


# ----------------------------------------------------------------------------
# Validacion y medidas
# ----------------------------------------------------------------------------
def validate(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    res = {
        "verts": len(bm.verts), "faces": len(bm.faces),
        "quads": sum(1 for f in bm.faces if len(f.verts) == 4),
        "tris": sum(1 for f in bm.faces if len(f.verts) == 3),
        "ngons": sum(1 for f in bm.faces if len(f.verts) > 4),
        "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold),
        "boundary_edges": sum(1 for e in bm.edges if e.is_boundary),
        "non_manifold_verts": sum(1 for v in bm.verts if not v.is_manifold),
        "loose_verts": sum(1 for v in bm.verts if not v.link_faces),
        "loose_edges": sum(1 for e in bm.edges if not e.link_faces),
        "inconsistent_normals": sum(1 for e in bm.edges if e.is_manifold and not e.is_contiguous),
        "degenerate_faces": sum(1 for f in bm.faces if f.calc_area() < 1e-10),
        "volume_m3": bm.calc_volume(signed=True),
    }
    # autointersecciones (pares de triangulos que se cruzan sin compartir vertices)
    lt = bm.calc_loop_triangles()
    verts = [v.co.copy() for v in bm.verts]
    tris = [(l[0].vert.index, l[1].vert.index, l[2].vert.index) for l in lt]
    tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    pairs = tree.overlap(tree)
    bad = 0
    for i, j in pairs:
        if i < j and not (set(tris[i]) & set(tris[j])):
            bad += 1
    res["self_intersections"] = bad
    res["outward"] = res["volume_m3"] > 0
    bm.free()
    return res


def bvh_of(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def inside_mask(tree, pts):
    out = np.zeros(len(pts), bool)
    for i, p in enumerate(pts):
        loc, nrm, idx, dist = tree.find_nearest(Vector(p))
        if loc is not None:
            out[i] = (Vector(p) - loc).dot(nrm) < 0
    return out


def union_volume(objs, vol, rng):
    body = objs["Pecari_Body"]
    others = [o for n, o in objs.items() if n != "Pecari_Body"]
    allv = np.vstack([get_V(o) for o in others])
    lo, hi = allv.min(0), allv.max(0)
    box = float(np.prod(hi - lo))
    Ns = 40000
    pts = lo + rng.random((Ns, 3)) * (hi - lo)
    inside_any = np.zeros(Ns, bool)
    for o in others:
        lo_o, hi_o = get_V(o).min(0), get_V(o).max(0)
        cand = np.all((pts >= lo_o) & (pts <= hi_o), axis=1) & ~inside_any
        if cand.any():
            m = inside_mask(bvh_of(o), pts[cand])
            idx = np.nonzero(cand)[0]
            inside_any[idx[m]] = True
    idx = np.nonzero(inside_any)[0]
    in_body = inside_mask(bvh_of(body), pts[idx])
    extra = (len(idx) - in_body.sum()) / Ns * box
    return vol["Pecari_Body"] + extra


def measure(P, objs, info, R, T, off):
    LM = P["landmarks"]
    S = P["meta"]["global_scale"]
    shift = float(off[1])

    def lmw(p):
        return np.asarray(p, float) * S + off

    Vb = get_V(objs["Pecari_Body"])
    Vh = get_V(objs["Pecari_Head"])
    Vj = get_V(objs["Pecari_LowerJaw"])
    M = {}
    # punta del hocico = centro del disco
    a_w = R @ np.array([0.0, -1.0, 0.0])
    proj = Vh @ a_w
    disc = Vh[proj > proj.max() - 0.0008 * S]
    P_tip = disc.mean(0)
    nuc = lmw(info["nuchal_world"])
    midh = Vh[np.abs(Vh[:, 0]) < 1e-5]
    P_nuc = midh[np.argmin(np.linalg.norm(midh - nuc, axis=1))]
    M["head_length"] = float(np.linalg.norm(P_tip - P_nuc))
    midb = Vb[np.abs(Vb[:, 0]) < 1e-5]
    tb = lmw(LM["tail_base"])
    P_tb = midb[np.argmin(np.linalg.norm(midb - tb, axis=1))]
    M["hb_length"] = M["head_length"] + float(np.linalg.norm(P_nuc - P_tb))
    M["head_hb_ratio"] = M["head_length"] / M["hb_length"]
    wy = LM["withers_y"] * S + shift
    sel = Vb[np.abs(Vb[:, 1] - wy) < 0.02 * S]
    M["withers_height"] = float(sel[:, 2].max())
    cy = LM["croup_y"] * S + shift
    M["croup_height"] = float(Vb[np.abs(Vb[:, 1] - cy) < 0.02 * S][:, 2].max())
    selm = midb[np.abs(midb[:, 1] - wy) < 0.012 * S]
    M["chest_depth"] = float(selm[:, 2].max() - selm[:, 2].min())
    y0 = LM["front_leg_y"] * S + shift + 0.05 * S
    y1 = LM["hind_leg_y"] * S + shift - 0.05 * S
    belly = midb[(midb[:, 1] > y0) & (midb[:, 1] < y1)]
    M["belly_clearance"] = float(belly[:, 2].min())
    bw = Vb[(Vb[:, 2] > LM["body_width_zmin"] * S)]
    M["body_width"] = float(2 * np.abs(bw[:, 0]).max())
    M["head_width"] = float(2 * max(np.abs(Vh[:, 0]).max(), np.abs(Vj[:, 0]).max()))
    M["disc_width"] = float(disc[:, 0].max() - disc[:, 0].min())
    # oreja
    ear = objs["Pecari_EarL"]
    Ve = get_V(ear)
    e3 = info["ear_axis"]
    base = info["ear_base"]
    tip = Ve[np.argmax((Ve - base) @ e3)]
    tree_h = bvh_of(objs["Pecari_Head"])
    hit = None
    o = Vector(base + e3 * 0.02 * S)
    loc, nrm, idx, dist = tree_h.ray_cast(o, Vector(-e3), 0.1)
    hit = np.array(loc) if loc is not None else base
    M["ear_length"] = float(np.linalg.norm(tip - hit))
    # pie trasero: tuberosidad calcanea -> punta de la pezuna
    hy = LM["hind_leg_y"] * S + shift
    hl = Vb[(Vb[:, 0] > 0.02 * S) & (Vb[:, 1] > hy - 0.06 * S) & (Vb[:, 2] > 0.10 * S) & (Vb[:, 2] < 0.22 * S)]
    P_heel = hl[np.argmax(hl[:, 1])]
    toe = Vb[(Vb[:, 0] > 0.02 * S) & (Vb[:, 1] > 0) & (Vb[:, 2] < 0.012 * S)]
    P_toe = toe[np.argmin(toe[:, 1])]
    M["hind_foot"] = float(np.linalg.norm(P_heel - P_toe))
    # ojo
    Vey = get_V(objs["Pecari_EyeL"])
    M["eye_diameter"] = float(Vey[:, 0].max() - Vey[:, 0].min())
    # canino: punta -> superficie del labio a lo largo del eje
    Vc = get_V(objs["Pecari_CanineL"])
    cax = info["canine_axis"]
    ctip = Vc[np.argmax(Vc @ cax)]
    loc, nrm, idx, dist = tree_h.ray_cast(Vector(ctip), Vector(-cax), 0.1)
    M["canine_exposed"] = float(dist) if loc is not None else float("nan")
    # masa
    vol = {n: validate_cache[n]["volume_m3"] for n in objs}
    vu = union_volume(objs, vol, np.random.default_rng(1))
    M["volume_union_m3"] = vu
    M["volume_sum_m3"] = float(sum(vol.values()))
    M["mass_kg"] = vu * 1000.0
    M["_points"] = {"snout_tip": P_tip.tolist(), "nuchal": P_nuc.tolist(), "tail_base": P_tb.tolist(),
                    "heel": P_heel.tolist(), "toe_hind": P_toe.tolist()}
    return M


validate_cache = {}


def fur_thickness(P, obj_name, obj):
    """Grosor de pelaje por vertice a partir de los grupos de vertices (ver params.fur)."""
    FU = P["fur"]
    n = len(obj.data.vertices)

    def w(g):
        a = np.zeros(n)
        vg = obj.vertex_groups.get(g)
        if vg is None:
            return a
        for v in obj.data.vertices:
            for ge in v.groups:
                if ge.group == vg.index:
                    a[v.index] = ge.weight
        return a
    if obj_name == "Pecari_Body":
        wl, wh = w("fur_legs"), w("bare_hooves")
        t = FU["body"] * np.clip(1 - wl - wh, 0, 1) + FU["legs"] * wl
        t += (FU["mane"] - FU["body"]) * w("fur_mane")
        t += (FU["belly"] - FU["body"]) * w("fur_belly")
        return np.maximum(t, 0.0)
    if obj_name == "Pecari_Head":
        return FU["face"] * w("fur_face") + (FU["crown"] - FU["face"]) * w("fur_mane")
    if obj_name == "Pecari_LowerJaw":
        return FU["face"] * w("fur_face")
    if obj_name.startswith("Pecari_Ear"):
        return np.full(n, FU["ears"])
    return np.zeros(n)


def export_arrays(P, objs, path, landmarks):
    """Vertices, triangulos, normales y grosor de pelaje por pieza -> .npz para silhouette.py."""
    data = {}
    for n, o in objs.items():
        me = o.data
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        data[n + "/V"] = get_V(o)
        data[n + "/N"] = get_N(o)
        data[n + "/F"] = tri.reshape(-1, 3)
        data[n + "/T"] = fur_thickness(P, n, o)
    data["landmarks_json"] = np.array(json.dumps(landmarks))
    np.savez_compressed(path, **data)


def write_report(path_md, path_json, version, P, M, VAL, groups, timings, engine):
    tg = P["targets"]
    rows = []
    ok_all = True
    for key, t in tg.items():
        if key.startswith("_"):
            continue
        v = M.get(key)
        if v is None:
            continue
        err = (v - t["value"]) / t["value"]
        ok = abs(err) <= t["tol"]
        ok_all &= ok
        rows.append((key, t["value"], v, err, t["tol"], t["source"], ok))
    tot = {k: sum(r[k] for r in VAL.values()) for k in ("quads", "tris", "ngons", "verts", "faces")}
    lines = ["# Informe %s" % version, "",
             "Generado por src/build_pecari.py (%s). Render: %s." % (time.strftime("%Y-%m-%d %H:%M"), engine), "",
             "## Medidas calculadas desde la malla", "",
             "| medida | objetivo | malla | error | tol | fuente | ok |",
             "|---|---:|---:|---:|---:|---|:-:|"]
    for key, tv, v, err, tol, src, ok in rows:
        unit = "kg" if key == "mass_kg" else ("" if key == "head_hb_ratio" else "m")
        lines.append("| %s | %.3f %s | %.3f %s | %+.1f %% | ±%d %% | %s | %s |"
                     % (key, tv, unit, v, unit, 100 * err, round(100 * tol), src, "si" if ok else "NO"))
    lines += ["", "Volumen union = %.5f m3 (suma de piezas %.5f m3; la diferencia es el solape cabeza/cuello/mandibula)."
              % (M["volume_union_m3"], M["volume_sum_m3"]), "",
              "## Validacion de malla", "",
              "| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n, r in VAL.items():
        lines.append("| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %.5f |" % (
            n, r["verts"], r["quads"], r["tris"], r["ngons"], r["non_manifold_edges"], r["boundary_edges"],
            r["loose_verts"] + r["loose_edges"], r["inconsistent_normals"], r["self_intersections"], r["volume_m3"]))
    lines.append("| **total** | %d | %d | %d | %d | | | | | | |" % (tot["verts"], tot["quads"], tot["tris"], tot["ngons"]))
    lines += ["", "## Grupos de vertices (vertices con peso > 0.5)", ""]
    for g, d in groups.items():
        lines.append("- %s: %s" % (g, ", ".join("%s=%d" % (k.replace("Pecari_", ""), v) for k, v in d.items())))
    lines += ["", "## Tiempos", ""] + ["- %s: %.1f s" % (k, v) for k, v in timings.items()]
    lines += ["", "Todas las medidas dentro de tolerancia: **%s**" % ("si" if ok_all else "NO")]
    with open(path_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(path_json, "w") as fh:
        json.dump({"version": version, "measurements": {k: v for k, v in M.items()},
                   "validation": VAL, "totals": tot, "groups": groups, "all_ok": ok_all}, fh, indent=2,
                  default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print("\n".join(lines))
    return ok_all


# ----------------------------------------------------------------------------
# Principal
# ----------------------------------------------------------------------------
def main():
    args = parse_args()
    with open(args.params) as fh:
        P = json.load(fh)
    version = args.version
    out_render = os.path.join(ROOT, "renders", version)
    os.makedirs(out_render, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "blend"), exist_ok=True)
    timings = {}
    log("Blender", bpy.app.version_string, "| params:", args.params, "| version:", version)
    with open(os.path.join(out_render, "params_used.json"), "w") as fh:
        json.dump(P, fh, indent=1)

    clear_scene()
    coll = bpy.data.collections.new("Pecari")
    bpy.context.scene.collection.children.link(coll)

    t = time.time()
    body, body_field = build_body(P, coll)
    timings["body"] = time.time() - t

    t = time.time()
    H = P["head"]
    R, T = head_transform(H)
    head, head_field, head_base, hinfo = build_head(P, coll)
    jaw, jaw_field = build_jaw(P, coll)
    timings["head+jaw"] = time.time() - t

    t = time.time()
    # ojos, orejas y caninos en marco canonico -> mundo
    EYE = P["eye"]
    EAR = P["ear"]
    CAN = P["canine"]
    objs = {"Pecari_Body": body, "Pecari_Head": head, "Pecari_LowerJaw": jaw}
    a = math.radians(EAR["ray_deg"])
    ear_base_can = surface_along(head_base, [0.0, EAR["u"], EAR["z0"]], [math.sin(a), 0.0, math.cos(a)])
    nrm_can = field_normal(head_base, ear_base_can)
    ear_root_can = ear_base_can - nrm_can * EAR["sink"]
    can_surf = surface_along(head_base, [0.0, CAN["u"], CAN["z"]], [1, 0, 0])
    can_nrm = field_normal(head_base, can_surf)
    can_root = can_surf - can_nrm * CAN["inset"]
    info = {"nuchal_world": np.array(H["nuchal_world"], float)}
    for side, sfx in ((1, "L"), (-1, "R")):
        m = np.array([side, 1, 1], float)
        ec = to_world(hinfo["eye_c"] * m, R, T)
        objs["Pecari_Eye" + sfx] = build_eye("Pecari_Eye" + sfx, ec, EYE["radius"], EYE["cube_cuts"], coll)
        eb = to_world(ear_root_can * m, R, T)
        ear, e3 = build_ear("Pecari_Ear" + sfx, side, eb, EAR, coll)
        objs["Pecari_Ear" + sfx] = ear
        cr = to_world(can_root * m, R, T)
        cdir = R @ (np.array(CAN["dir_can"], float) * m)
        can, cax = build_canine("Pecari_Canine" + sfx, side, cr, cdir, CAN, coll)
        objs["Pecari_Canine" + sfx] = can
        if side == 1:
            info["ear_axis"] = e3
            info["ear_base"] = to_world(ear_base_can, R, T)
            info["canine_axis"] = cax
    # cabeza y mandibula al mundo
    set_V(head, to_world(get_V(head), R, T))
    set_V(jaw, to_world(get_V(jaw), R, T))
    timings["parts"] = time.time() - t

    # grupos de vertices (marco de diseno)
    t = time.time()
    groups = compute_groups(P, objs, body_field, R, T)
    timings["groups"] = time.time() - t

    # escala global + recentrado del origen entre las pezunas
    S = P["meta"]["global_scale"]
    Vb = get_V(body)
    soles = Vb[Vb[:, 2] < 0.0015]
    yf = soles[soles[:, 1] < 0][:, 1].mean()
    yh = soles[soles[:, 1] > 0][:, 1].mean()
    shift = -0.5 * (yf + yh) * S
    zshift = -float(Vb[:, 2].min()) * S       # suelas exactamente en Z = 0
    for o in objs.values():
        V = get_V(o) * S
        V[:, 1] += shift
        V[:, 2] += zshift
        set_V(o, V)
        shade_smooth(o)
        o.data.update()
    log("recentrado: pezunas delanteras y=%.3f traseras y=%.3f -> desplazamiento Y %.4f, Z %.4f"
        % (yf, yh, shift, zshift))
    off = np.array([0.0, shift, zshift])
    R_s, T_s = R, (T * S + off)
    info["ear_base"] = info["ear_base"] * S + off

    # validacion
    t = time.time()
    VAL = {}
    for n, o in objs.items():
        fix_normals(o)
        VAL[n] = validate(o)
        validate_cache[n] = VAL[n]
    timings["validate"] = time.time() - t
    t = time.time()
    M = measure(P, objs, info, R_s, T_s, off)
    timings["measure"] = time.time() - t
    export_arrays(P, objs, os.path.join(out_render, "mesh_arrays.npz"), M["_points"])

    # guardar
    blend_path = os.path.join(ROOT, "blend", "pecari_%s.blend" % version)
    glb_path = os.path.join(ROOT, "blend", "pecari_%s.glb" % version)
    for o in objs.values():
        o.select_set(True)
    bpy.context.view_layer.objects.active = body
    try:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True)
        log("GLB:", glb_path)
    except Exception as e:
        log("aviso: no se pudo exportar GLB:", e)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log("blend:", blend_path)

    engine = "sin render"
    if not args.no_render:
        t = time.time()
        import render_views
        engine = render_views.render_all(objs, out_render, P["render"], args, info={
            "head_center": (0.5 * (np.array(M["_points"]["snout_tip"]) + np.array(M["_points"]["nuchal"]))
                            + np.array([0.0, 0.0, -0.025])).tolist()})
        timings["render"] = time.time() - t
    with open(os.path.join(out_render, "points.json"), "w") as fh:
        json.dump(M["_points"], fh, indent=1)
    M.pop("_points")
    ok = write_report(os.path.join(out_render, "report.md"), os.path.join(out_render, "report.json"),
                      version, P, M, VAL, groups, timings, engine)
    log("TERMINADO", version, "| medidas ok:", ok)


if __name__ == "__main__":
    main()
