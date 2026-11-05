"""
Modelo numerico del pecari (sin bpy): utilidades, primitivas SDF, barridos, campos de
cada pieza, proyeccion/relajacion de mallas y transformaciones de la cabeza.

Lo usan build_pecari.py (dentro de Blender), silhouette.py y fit_silhouette.py (Python
puro con numpy), de modo que la silueta se puede evaluar cientos de veces sin Blender.
"""
import math

import numpy as np

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



# ----------------------------------------------------------------------------
# Esqueleto: patas definidas por articulaciones con nombre
# ----------------------------------------------------------------------------
def skel_point(P, ref):
    """Resuelve un punto: nombre del esqueleto, [x,y,z] literal o {"lerp": [a, b, t]}."""
    S = P["skeleton"]
    if isinstance(ref, str):
        return np.array(S[ref], float)
    if isinstance(ref, dict) and "lerp" in ref:
        a, b, t = ref["lerp"]
        pa, pb = skel_point(P, a), skel_point(P, b)
        return pa + (pb - pa) * float(t)
    return np.array(ref, float)


def resolve_legs(P):
    """Convierte params.legs (por articulaciones) al formato numerico de BodyField:
    segments [ax,ay,az,bx,by,bz,ra,rb,k], ellipsoids [cx,cy,cz,rx,ry,rz,k],
    cage [cx,cy,cz,hx,hy] y root_ring (indice del anillo de jaula del cuerpo)."""
    rings_y = P["body"]["cage"]["rings_y"]
    out = []
    for key in ("front", "hind"):
        L = P["legs"][key]
        seg = []
        for a, b, ra, rb, k in L["segments"]:
            seg.append(list(skel_point(P, a)) + list(skel_point(P, b)) + [ra, rb, k])
        ell = []
        for c, r, k in L["ellipsoids"]:
            ell.append(list(skel_point(P, c)) + list(r) + [k])
        cage = []
        for c, hx, hy in L["cage"]:
            cage.append(list(skel_point(P, c)) + [hx, hy])
        root = L.get("root_ring", "auto")
        if root == "auto":
            y0 = cage[0][1]
            root = int(np.clip(np.searchsorted(rings_y, y0) - 1, 0, len(rings_y) - 2))
        out.append({"segments": seg, "ellipsoids": ell, "cage": cage, "root_ring": root,
                    "k_body": L["k_body"], "name": key})
    return out
