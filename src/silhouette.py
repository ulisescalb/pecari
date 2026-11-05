"""
Metrica de silueta: compara el modelo con las mascaras de reference/masks/.

Dos fuentes de silueta del modelo, sin renderizar:
  * malla  : triangulos de renders/vNN/mesh_arrays.npz (exportado por build_pecari.py),
             desplazados por el grosor de pelaje de cada vertice (params.fur) y rellenados.
  * SDF    : rejilla de ocupacion 3D del campo (piel - pelaje) proyectada sobre cada eje.
             Es lo que usa el optimizador (cientos de evaluaciones sin Blender).

Alineacion: vista lateral -> suelo (ground_y) y distancia horizontal nariz-base de la
cola (nose_px, tail_base_px de reference/ref_landmarks.json). Vista frontal -> suelo,
linea media y la misma altura total en metros que la lateral ya alineada.

IoU = |modelo ∩ referencia| / |modelo ∪ referencia| a la resolucion de trabajo.
Superposicion: gris = coincide, rojo = sobra (modelo fuera de la foto),
azul = falta (foto fuera del modelo).

Uso:  python src/silhouette.py --version v05        (venv con numpy + opencv)
"""
import os
import sys
import json
import argparse

import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")
VIEWS = ("side", "front")
SIDE_VIEWS = ("side", "real_side_walking")      # vistas laterales (IA y foto real)
ALL_VIEWS = ("side", "real_side_walking", "front")


# ----------------------------------------------------------------------------
# Referencias
# ----------------------------------------------------------------------------
class Reference:
    def __init__(self, view, scale):
        meta = json.load(open(os.path.join(REF, "ref_landmarks.json")))
        self.view = view
        self.lm = meta[view]
        full = cv2.imread(os.path.join(REF, "masks", view + ".png"), cv2.IMREAD_GRAYSCALE) > 0
        self.full_shape = full.shape
        self.scale = scale
        h, w = full.shape
        self.shape = (int(round(h * scale)), int(round(w * scale)))
        small = cv2.resize(full.astype(np.float32), (self.shape[1], self.shape[0]), interpolation=cv2.INTER_AREA)
        self.mask = small >= 0.5
        ys, xs = np.nonzero(full)
        self.top_px = int(ys.min())
        self.faces = self.lm.get("faces", "right")
        self.fur_scale = self.lm.get("fur_scale", 1.0)
        self.is_side = view in SIDE_VIEWS
        fn = "ref_%s.jpg" % view
        if not os.path.exists(os.path.join(REF, fn)):
            fn = view + ".jpg"
        self.image_path = os.path.join(REF, fn)


class Alignment:
    """Transformacion modelo (metros, marco del asset) -> pixeles de una foto (resolucion completa).

    Vistas laterales: suelo + distancia horizontal nariz-base de la cola (la foto puede mirar a
    la derecha o a la izquierda). Vista frontal: suelo + linea media + altura total del modelo
    (con pelaje) igual a la altura de la silueta de la foto: compara forma y anchos, no la
    proporcion alto/largo de una imagen generada."""

    def __init__(self, ref, nose_y, tail_y, model_height=None):
        self.ref = ref
        L = ref.lm
        self.view = ref.view
        if ref.is_side:
            nx, _ = L["nose_px"]
            tx, _ = L["tail_base_px"]
            self.s = (tail_y - nose_y) / float(abs(nx - tx))
            self.sign = -1.0 if ref.faces == "right" else 1.0
            self.nose_y = nose_y
            self.nose_x = nx
        else:
            self.s = model_height / float(L["ground_y"] - ref.top_px)
            self.mid = L["midline_x"]
        self.ground = L["ground_y"]
        self.height_m = (L["ground_y"] - ref.top_px) * self.s

    def to_px(self, P):
        P = np.asarray(P, float)
        if self.ref.is_side:
            u = self.nose_x + self.sign * (P[..., 1] - self.nose_y) / self.s
        else:
            u = self.mid + P[..., 0] / self.s
        v = self.ground - P[..., 2] / self.s
        return u, v

    def from_px(self, u, v):
        if self.ref.is_side:
            return self.nose_y + (u - self.nose_x) * self.s / self.sign, (self.ground - v) * self.s
        return (u - self.mid) * self.s, (self.ground - v) * self.s

    def upper_cut(self, z=0.22):
        return int((self.ground - z / self.s) * self.ref.scale)


# ----------------------------------------------------------------------------
# Silueta desde malla
# ----------------------------------------------------------------------------
def load_mesh_arrays(path):
    z = np.load(path, allow_pickle=False)
    objs = {}
    for k in z.files:
        if "/" not in k:
            continue
        name, key = k.split("/")
        objs.setdefault(name, {})[key] = z[k]
    lm = json.loads(str(z["landmarks_json"]))
    return objs, lm


def mesh_silhouette(objs, align, ref, fur=True, zscale=1.0):
    out = np.zeros(ref.shape, np.uint8)
    sh = 4
    for name, d in objs.items():
        V = d["V"] + (d["N"] * (d["T"] * ref.fur_scale)[:, None] if fur else 0.0)
        if zscale != 1.0:
            V = V * np.array([1.0, 1.0, zscale])
        u, v = align.to_px(V)
        pts = np.stack([u, v], 1) * ref.scale
        tri = np.round(pts[d["F"]] * (1 << sh)).astype(np.int32)
        for t in tri:                      # cada triangulo por separado (fillPoly multiple = par-impar)
            cv2.fillConvexPoly(out, t, 1, lineType=cv2.LINE_8, shift=sh)
    return out > 0


# ----------------------------------------------------------------------------
# Silueta desde el SDF (rejilla de ocupacion)
# ----------------------------------------------------------------------------
def occupancy_grid(field, bbox_min, bbox_max, h, chunk=400000):
    """Evalua field (callable P(N,3)->d) en una rejilla regular; solo x>=0 (simetria)."""
    lo = np.array(bbox_min, float)
    hi = np.array(bbox_max, float)
    lo[0] = 0.0
    xs = np.arange(lo[0], hi[0] + h, h)
    ys = np.arange(lo[1], hi[1] + h, h)
    zs = np.arange(lo[2], hi[2] + h, h)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    occ = np.empty(len(P), bool)
    for i in range(0, len(P), chunk):
        occ[i:i + chunk] = field(P[i:i + chunk]) <= 0
    return occ.reshape(X.shape), (xs, ys, zs)


def add_fur(occ, axes, fur_t, h, tmax=0.09):
    """Engrosa la ocupacion de piel con el grosor de pelaje fur_t(p): un voxel exterior se
    ocupa si su distancia euclidea a la piel es <= fur_t(p) (transformada de distancia exacta,
    incluyendo el lado reflejado x<0)."""
    from scipy.ndimage import distance_transform_edt
    full = np.concatenate([occ[:0:-1], occ], 0)          # x de -max a +max
    dist = distance_transform_edt(~full) * h
    dist = dist[occ.shape[0] - 1:]                           # mitad x>=0
    xs, ys, zs = axes
    cand = (~occ) & (dist <= tmax)
    idx = np.argwhere(cand)
    out = occ.copy()
    if len(idx):
        P = np.stack([xs[idx[:, 0]], ys[idx[:, 1]], zs[idx[:, 2]]], 1)
        t = fur_t(P)
        ok = dist[cand] <= t
        out[tuple(idx[ok].T)] = True
    return out


def project_grid(occ, axes):
    xs, ys, zs = axes
    side = occ.any(axis=0)                 # (y, z)
    front_half = occ.any(axis=1)           # (x>=0, z)
    front = np.concatenate([front_half[:0:-1], front_half], 0)
    fx = np.concatenate([-xs[:0:-1], xs])
    return {"side": (side, ys, zs), "front": (front, fx, zs)}


def grid_silhouette(proj, align, ref, polys=()):
    """Muestrea la proyeccion 2D del modelo en cada pixel de la referencia (vecino mas cercano)."""
    m2, a1, a2 = proj["side" if ref.is_side else "front"]
    hh, ww = ref.shape
    v, u = np.mgrid[0:hh, 0:ww]
    c1, c2 = align.from_px((u + 0.5) / ref.scale, (v + 0.5) / ref.scale)
    h1 = a1[1] - a1[0]
    h2 = a2[1] - a2[0]
    i1 = np.round((c1 - a1[0]) / h1).astype(int)
    i2 = np.round((c2 - a2[0]) / h2).astype(int)
    ok = (i1 >= 0) & (i1 < len(a1)) & (i2 >= 0) & (i2 < len(a2))
    out = np.zeros(ref.shape, bool)
    out[ok] = m2[i1[ok], i2[ok]]
    if polys:
        extra = np.zeros(ref.shape, np.uint8)
        for P in polys:
            uu, vv = align.to_px(P)
            pts = np.stack([uu, vv], 1) * ref.scale
            hull = cv2.convexHull(np.round(pts * 16).astype(np.int32))
            cv2.fillPoly(extra, [hull], 1, shift=4)
        out |= extra > 0
    return out


# ----------------------------------------------------------------------------
# Metrica y superposicion
# ----------------------------------------------------------------------------
def iou(a, b):
    inter = np.logical_and(a, b).sum()
    uni = np.logical_or(a, b).sum()
    return float(inter) / max(float(uni), 1.0)


def overlay(ref, model_mask, path, title="", cut=None):
    img = cv2.imread(ref.image_path)
    img = cv2.resize(img, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    out = (gray * 0.35 + 255 * 0.65).astype(np.uint8)
    both = model_mask & ref.mask
    extra = model_mask & ~ref.mask
    miss = ref.mask & ~model_mask
    out[both] = (out[both] * 0.45 + np.array([90, 90, 90]) * 0.55).astype(np.uint8)
    out[extra] = (40, 40, 230)
    out[miss] = (230, 120, 30)
    edge = cv2.morphologyEx(ref.mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    out[edge] = (0, 0, 0)
    if cut is not None and 0 < cut < out.shape[0]:
        out[cut, ::6] = (0, 140, 0)
    if title:
        cv2.putText(out, title, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(out, "gris=coincide  rojo=sobra  azul=falta", (12, 58), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(path, out)


def evaluate_mesh(npz_path, out_dir=None, scale=0.5, fur=True, refs=None):
    """IoU de la malla (piel + pelaje) contra cada referencia; total y por encima de 0.22 m."""
    objs, lm = load_mesh_arrays(npz_path)
    refs = refs or {v: Reference(v, scale) for v in ALL_VIEWS}
    nose_y = float(objs["Pecari_Head"]["V"][:, 1].min())
    tail_y = float(lm["tail_base"][1])
    hm = max(float((d["V"] + d["N"] * d["T"][:, None])[:, 2].max()) for d in objs.values())
    res = {"model_height_m": hm}
    for view, ref in refs.items():
        al = Alignment(ref, nose_y, tail_y, hm)
        m = mesh_silhouette(objs, al, ref, fur=fur)
        cut = al.upper_cut()
        res[view] = iou(m, ref.mask)
        res[view + "_upper_z022"] = iou(m[:cut], ref.mask[:cut])
        res[view + "_scale_m_per_px"] = al.s
        if out_dir:
            overlay(ref, m, os.path.join(out_dir, "iou_%s.png" % view),
                    "%s  tronco+cabeza (z>0.22 m) IoU=%.3f   total=%.3f" % (view, res[view + "_upper_z022"], res[view]),
                    cut=cut)
    return res


def evaluate_model(P, refs=None, h=0.005, scale=0.25, fur=True, out_dir=None, model=None):
    """IoU desde el SDF (sin malla ni Blender): rejilla de ocupacion -> proyecciones."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from pecari_sdf import AnatomyModel
    m = model or AnatomyModel(P)
    refs = refs or {v: Reference(v, scale) for v in ALL_VIEWS}
    lo, hi = m.bbox()
    occ, axes = occupancy_grid(m.skin, lo, hi, h)
    res = {"volume_m3_grid": float(occ.sum()) * h ** 3 * 2.0}
    tail_y = float(P["landmarks"]["tail_base"][1])
    nose = m.nose_y()
    cache = {}
    masks = {}
    for view, ref in refs.items():
        fs = ref.fur_scale if fur else 0.0
        if fs not in cache:
            o = add_fur(occ, axes, lambda Q: m.fur_t(Q) * fs, h) if fs > 0 else occ
            cache[fs] = (project_grid(o, axes), float(axes[2][np.nonzero(o.any(axis=(0, 1)))[0].max()]))
        proj, hm = cache[fs]
        if "model_height" not in res:
            res["model_height"] = hm
        al = Alignment(ref, nose, tail_y, cache.get(1.0, (None, hm))[1])
        sil = grid_silhouette(proj, al, ref, polys=m.ears_furred())
        cut = al.upper_cut()
        res[view] = iou(sil, ref.mask)
        res[view + "_upper_z022"] = iou(sil[:cut], ref.mask[:cut])
        masks[view] = sil
        if out_dir:
            overlay(ref, sil, os.path.join(out_dir, "iou_sdf_%s.png" % view),
                    "%s SDF tronco+cabeza=%.3f total=%.3f" % (view, res[view + "_upper_z022"], res[view]), cut=cut)
    return res, masks, (occ, axes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--scale", type=float, default=0.5)
    a = ap.parse_args()
    d = os.path.join(ROOT, "renders", a.version)
    res = evaluate_mesh(os.path.join(d, "mesh_arrays.npz"), d, a.scale)
    json.dump(res, open(os.path.join(d, "iou.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
