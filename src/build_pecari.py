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

T0 = time.time()


def log(*a):
    print("[pecari %6.1fs]" % (time.time() - T0), *a, flush=True)


# ----------------------------------------------------------------------------
# Argumentos
# ----------------------------------------------------------------------------
def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_pecari.py")
    ap.add_argument("--version", default="v01")
    ap.add_argument("--params", default=os.path.join(SRC, "params.json"))
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--res", type=int, default=None)
    return ap.parse_args(argv)


# ----------------------------------------------------------------------------
# Utilidades numericas
# ----------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def pchip(x, y, xq):
    """Interpolacion cubica monotona (Fritsch-Carlson), sin sobreoscilaciones."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    h = np.diff(x)
    delta = np.diff(y) / h
    d = np.zeros(n)
    if n == 2:
        d[:] = delta[0]
    else:
        for k in range(1, n - 1):
            if delta[k - 1] * delta[k] <= 0:
                d[k] = 0.0
            else:
                w1 = 2 * h[k] + h[k - 1]
                w2 = h[k] + 2 * h[k - 1]
                d[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k])

        def endslope(h0, h1, d0, d1):
            s = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
            if np.sign(s) != np.sign(d0):
                s = 0.0
            elif np.sign(d0) != np.sign(d1) and abs(s) > abs(3 * d0):
                s = 3 * d0
            return s

        d[0] = endslope(h[0], h[1], delta[0], delta[1])
        d[-1] = endslope(h[-1], h[-2], delta[-1], delta[-2])
    xq = np.clip(np.asarray(xq, float), x[0], x[-1])
    k = np.clip(np.searchsorted(x, xq) - 1, 0, n - 2)
    t = (xq - x[k]) / h[k]
    t2 = t * t
    t3 = t2 * t
    return ((2 * t3 - 3 * t2 + 1) * y[k] + (t3 - 2 * t2 + t) * h[k] * d[k]
            + (-2 * t3 + 3 * t2) * y[k + 1] + (t3 - t2) * h[k] * d[k + 1])


def num_grad(f, P, h=1e-4):
    G = np.empty_like(P)
    for i in range(3):
        D = np.zeros(3)
        D[i] = h
        G[:, i] = (f(P + D) - f(P - D)) / (2.0 * h)
    return G


def normalize(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ----------------------------------------------------------------------------
# Primitivas SDF (vectorizadas, P: (N,3))
# ----------------------------------------------------------------------------
def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def sd_ellipsoid(P, c, r):
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    q = P - c
    k0 = np.linalg.norm(q / r, axis=1)
    k1 = np.linalg.norm(q / (r * r), axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-12)


def sd_round_cone(P, a, b, r1, r2):
    """Cono redondeado exacto (I. Quilez)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    q = pa * l2 - np.outer(y, ba)
    x2 = np.einsum("ij,ij->i", q, q)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d1 = np.sqrt(x2 + z2) * il2 - r2
    out = np.where(np.sign(y) * a2 * y2 < k, d2, d3)
    out = np.where(np.sign(z) * a2 * z2 > k, d1, out)
    return out


class Sweep:
    """Barrido de secciones superelipticas a lo largo del eje Y local.

    stations: [y, z_top, z_bot, half_width, height_frac, exponent]. Fuera del rango
    se cierra con casquetes elipsoidales de longitud cap0 (y<y0) y cap1 (y>y1).
    Se evalua sobre |x| (simetrico)."""

    def __init__(self, stations, cap0, cap1):
        st = np.asarray(stations, float)
        st = st[np.argsort(st[:, 0])]
        self.st = st
        self.y0 = st[0, 0]
        self.y1 = st[-1, 0]
        self.yd = np.linspace(self.y0, self.y1, 800)
        self.tab = np.stack([pchip(st[:, 0], st[:, j], self.yd) for j in range(1, 6)], 1)
        self.c0 = cap0
        self.c1 = cap1

    def profile(self, y):
        yc = np.clip(y, self.y0, self.y1)
        return [np.interp(yc, self.yd, self.tab[:, j]) for j in range(5)]

    def raw(self, P):
        x = np.abs(P[:, 0])
        y = P[:, 1]
        z = P[:, 2]
        ztop, zbot, w, hf, n = self.profile(y)
        zm = zbot + hf * (ztop - zbot)
        b = np.where(z >= zm, ztop - zm, zm - zbot)
        ax = x / w
        az = np.abs(z - zm) / b
        r = (ax ** n + az ** n) ** (1.0 / n)
        e = np.zeros_like(y)
        m1 = y > self.y1
        e[m1] = (y[m1] - self.y1) / self.c1
        m0 = y < self.y0
        e[m0] = (self.y0 - y[m0]) / self.c0
        return np.sqrt(r * r + e * e) - 1.0

    def sdf(self, P):
        f = self.raw(P)
        g = num_grad(self.raw, P, 1e-4)
        return f / np.maximum(np.linalg.norm(g, axis=1), 1e-3)

    def ring(self, y, nring, inflate=1.0):
        """Anillo de jaula: k=0 arriba (linea media), crece hacia +X."""
        ztop, zbot, w, hf, n = [float(v[0]) for v in self.profile(np.array([y], float))]
        zm = zbot + hf * (ztop - zbot)
        # dentro de los casquetes la seccion se encoge como un elipsoide
        e = (y - self.y1) / self.c1 if y > self.y1 else ((self.y0 - y) / self.c0 if y < self.y0 else 0.0)
        sc = math.sqrt(max(1.0 - e * e, 0.09)) * inflate
        bt = (ztop - zm) * sc
        bb = (zm - zbot) * sc
        w = w * sc
        ex = 2.0 / n
        pts = []
        for k in range(nring):
            th = 2 * math.pi * k / nring
            s, c = math.sin(th), math.cos(th)
            x = w * math.copysign(abs(s) ** ex, s) if abs(s) > 1e-12 else 0.0
            b = bt if c >= 0 else bb
            z = zm + b * math.copysign(abs(c) ** ex, c) if abs(c) > 1e-12 else zm
            pts.append([x, y, z])
        return pts


def absx(P):
    Q = P.copy()
    Q[:, 0] = np.abs(Q[:, 0])
    return Q


# ----------------------------------------------------------------------------
# Campos de cada pieza
# ----------------------------------------------------------------------------
class BodyField:
    def __init__(self, B, legs):
        self.sweep = Sweep(B["stations"], B["cap_front"], B["cap_rear"])
        self.ell = B.get("ellipsoids", [])
        self.legs = legs
        self.gk = B.get("ground_k", 0.0025)

    def torso(self, P):
        Q = absx(P)
        d = self.sweep.sdf(Q)
        for e in self.ell:
            d = smin(d, sd_ellipsoid(Q, e["c"], e["r"]), e["k"])
        return d

    @staticmethod
    def leg(P, L):
        Q = absx(P)
        d = None
        for s in L["segments"]:
            di = sd_round_cone(Q, s[0:3], s[3:6], s[6], s[7])
            d = di if d is None else smin(d, di, s[8])
        for e in L.get("ellipsoids", []):
            di = sd_ellipsoid(Q, e[0:3], e[3:6])
            d = smin(d, di, e[6])
        return d

    def components(self, P):
        dt = self.torso(P)
        dl = [self.leg(P, L) for L in self.legs]
        return dt, dl

    def __call__(self, P):
        d, dls = self.components(P)
        for L, dl in zip(self.legs, dls):
            d = smin(d, dl, L["k_body"])
        return smax(d, -P[:, 2], self.gk)


class HeadField:
    """Cabeza en marco canonico (disco en u=0, u=+Y hacia atras)."""

    def __init__(self, H, socket=None):
        self.H = H
        self.sweep = Sweep(H["stations"], H["cap_front"], H["cap_back"])
        self.socket = socket  # (center, radii, k)

    def __call__(self, P):
        H = self.H
        Q = absx(P)
        d = self.sweep.sdf(Q)
        for e in H.get("ellipsoids", []):
            d = smin(d, sd_ellipsoid(Q, e["c"], e["r"]), e["k"])
        d = smax(d, -(Q[:, 1] - H["disc_u"]), H["disc_round"])
        for e in H.get("subtract", []):
            d = smax(d, -sd_ellipsoid(Q, e["c"], e["r"]), e["k"])
        if self.socket is not None:
            c, r, k = self.socket
            d = smax(d, -sd_ellipsoid(Q, c, r), k)
        return d


class JawField:
    def __init__(self, J):
        self.J = J
        self.sweep = Sweep(J["stations"], J["cap_front"], J["cap_back"])

    def __call__(self, P):
        Q = absx(P)
        d = self.sweep.sdf(Q)
        for e in self.J.get("ellipsoids", []):
            d = smin(d, sd_ellipsoid(Q, e["c"], e["r"]), e["k"])
        return d


# ----------------------------------------------------------------------------
# Proyeccion y relajacion
# ----------------------------------------------------------------------------
def project(V, f, iters=6, max_step=0.02, mid=None):
    for _ in range(iters):
        d = f(V)
        g = num_grad(f, V)
        gn2 = np.maximum(np.einsum("ij,ij->i", g, g), 1e-10)
        step = (d / gn2)[:, None] * g
        sl = np.linalg.norm(step, axis=1)
        s = np.minimum(1.0, max_step / np.maximum(sl, 1e-12))
        V = V - step * s[:, None]
        if mid is not None:
            V[mid, 0] = 0.0
    return V


def project_normal(V, N, f, reach=0.03, steps=61, mid=None):
    """Proyeccion tipo shrinkwrap: cada vertice busca el cruce del campo a lo largo de
    su normal (el mas cercano dentro de +-reach). Asi los salientes del SDF (corvejon,
    pezuna, olecranon) reciben vertices aunque la superficie subdividida quede por
    dentro; si no hay cruce se usa la proyeccion al punto mas cercano."""
    N = N / np.maximum(np.linalg.norm(N, axis=1), 1e-9)[:, None]
    # solo donde la superficie subdividida queda DENTRO del campo (salientes);
    # en pliegues concavos (axilas) los rayos convergen: ahi, punto mas cercano.
    inside = f(V) < 0
    ts = np.linspace(-reach, reach, steps)
    nV = len(V)
    D = np.empty((nV, steps))
    for j, t in enumerate(ts):
        D[:, j] = f(V + t * N)
    s = np.sign(D)
    cross = (s[:, :-1] * s[:, 1:]) <= 0
    tc = np.full(nV, np.nan)
    tmid = 0.5 * (ts[:-1] + ts[1:])
    has = cross.any(1)
    if has.any():
        dist = np.where(cross, np.abs(tmid)[None, :], np.inf)
        j = np.argmin(dist, axis=1)
        idx = np.nonzero(has)[0]
        j = j[idx]
        d0 = D[idx, j]
        d1 = D[idx, j + 1]
        w = d0 / np.where(np.abs(d0 - d1) < 1e-12, 1e-12, (d0 - d1))
        tc[idx] = ts[j] + np.clip(w, 0, 1) * (ts[1] - ts[0])
    ok = ~np.isnan(tc) & inside
    V = V.copy()
    V[ok] = V[ok] + tc[ok, None] * N[ok]
    if mid is not None:
        V[mid, 0] = 0.0
    return project(V, f, 4, max_step=0.005, mid=mid)


def relax(V, E, f, iters=10, lam=0.45, mid=None, fixed=None, convex_damp=0.0, weight=None):
    n = len(V)
    deg = (np.bincount(E[:, 0], minlength=n) + np.bincount(E[:, 1], minlength=n)).astype(float)
    deg = np.maximum(deg, 1.0)
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, E[:, 0], V[E[:, 1]])
        np.add.at(acc, E[:, 1], V[E[:, 0]])
        avg = acc / deg[:, None]
        g = num_grad(f, V)
        nrm = g / np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]
        dl = avg - V
        # convexidad local: en salientes (vecinos por debajo del plano tangente) se
        # frena el deslizamiento para no "pelar" corvejon, pezunas u olecranon;
        # en pliegues concavos (axilas) se relaja del todo.
        elen = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
        el = np.zeros(n)
        np.add.at(el, E[:, 0], elen)
        np.add.at(el, E[:, 1], elen)
        el = np.maximum(el / deg, 1e-6)
        conv = -np.einsum("ij,ij->i", dl, nrm) / el
        damp = 1.0 - convex_damp * smoothstep(0.03, 0.15, conv)
        dl -= np.einsum("ij,ij->i", dl, nrm)[:, None] * nrm
        if fixed is not None:
            dl[fixed] = 0.0
        if weight is not None:
            damp = damp * weight
        V = V + lam * damp[:, None] * dl
        V = project(V, f, 2, mid=mid)
    return V


def field_laplacian(f, P, h=2e-3):
    """Laplaciano numerico del campo (~ 2 x curvatura media): >0 convexo, <0 concavo."""
    f0 = f(P)
    lap = np.zeros(len(P))
    for i in range(3):
        D = np.zeros(3)
        D[i] = h
        lap += f(P + D) + f(P - D) - 2.0 * f0
    return lap / (h * h)


def surface_along(f, origin, direction, tmax=0.25, n=500):
    """Primer cruce de dentro (f<0) a fuera (f>=0) a lo largo de un rayo."""
    origin = np.asarray(origin, float)
    direction = normalize(direction)
    ts = np.linspace(0, tmax, n)
    P = origin + ts[:, None] * direction
    d = f(P)
    idx = np.where((d[:-1] < 0) & (d[1:] >= 0))[0]
    if len(idx) == 0:
        raise RuntimeError("surface_along: sin cruce desde %s" % origin)
    a, b = ts[idx[0]], ts[idx[0] + 1]
    for _ in range(40):
        m = 0.5 * (a + b)
        if f((origin + m * direction)[None])[0] < 0:
            a = m
        else:
            b = m
    return origin + 0.5 * (a + b) * direction


def field_normal(f, p):
    g = num_grad(f, np.asarray(p, float)[None])[0]
    return g / np.linalg.norm(g)


# ----------------------------------------------------------------------------
# Construccion de jaulas
# ----------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []

    def add_verts(self, pts):
        i0 = len(self.verts)
        self.verts.extend([list(map(float, p)) for p in pts])
        return list(range(i0, i0 + len(pts)))

    def bridge(self, r0, r1, skip=()):
        n = len(r0)
        for k in range(n):
            if k in skip:
                continue
            self.faces.append([r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]])

    def cap(self, ring, a, b, axis_dir, dome):
        """Tapa en rejilla a x b (todo quads) para un anillo de 2(a+b) vertices.
        El lado 'superior' de la rejilla queda centrado en ring[0]."""
        N = len(ring)
        assert N == 2 * (a + b), "anillo %d no encaja con rejilla %dx%d" % (N, a, b)
        start = (-(a // 2)) % N
        seq = [ring[(start + t) % N] for t in range(N)]
        G = [[None] * (b + 1) for _ in range(a + 1)]
        for i in range(a + 1):
            G[i][0] = seq[i]
        for j in range(b + 1):
            G[a][j] = seq[a + j]
        for i in range(a + 1):
            G[a - i][b] = seq[(a + b + i) % N]
        for j in range(b + 1):
            G[0][b - j] = seq[(2 * a + b + j) % N]
        P = lambda idx: np.array(self.verts[idx])
        axis_dir = normalize(axis_dir)
        for i in range(1, a):
            for j in range(1, b):
                s, t = i / a, j / b
                L, R = P(G[0][j]), P(G[a][j])
                Bm, Tp = P(G[i][0]), P(G[i][b])
                p = ((1 - s) * L + s * R + (1 - t) * Bm + t * Tp
                     - ((1 - s) * (1 - t) * P(G[0][0]) + s * (1 - t) * P(G[a][0])
                        + (1 - s) * t * P(G[0][b]) + s * t * P(G[a][b])))
                bump = dome * (1 - (2 * s - 1) ** 2) * (1 - (2 * t - 1) ** 2)
                p = p + axis_dir * bump
                G[i][j] = self.add_verts([p])[0]
        for i in range(a):
            for j in range(b):
                self.faces.append([G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]])


def mirror_k(k, n):
    return (n - k) % n


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


# ----------------------------------------------------------------------------
# Piezas
# ----------------------------------------------------------------------------
def head_transform(H):
    phi = math.radians(H["pitch_deg"])
    c, s = math.cos(phi), math.sin(phi)
    R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)  # canonico -> mundo
    nc = np.array(H["nuchal_can"], float)
    nw = np.array(H["nuchal_world"], float)
    T = nw - R @ nc
    return R, T


def to_world(Pc, R, T):
    return np.asarray(Pc) @ R.T + T


def to_can(Pw, R, T):
    return (np.asarray(Pw) - T) @ R


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
