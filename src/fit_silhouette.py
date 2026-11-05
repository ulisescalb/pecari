"""
Ajuste automatico de los parametros del SDF contra las siluetas de referencia (CMA-ES).

Uso:  python src/fit_silhouette.py [--evals 600] [--workers 4] [--write]
      (venv con numpy, scipy, opencv y cma; NO necesita Blender)

Objetivo: maximizar 0.6 * IoU_lateral + 0.4 * IoU_frontal (piel + pelaje, rejilla de
ocupacion del SDF) con restricciones:
  * medidas globales dentro de +-8 % de los objetivos de params.targets (penalizacion
    lineal fuerte fuera de +-7 %; masa +-25 %),
  * landmarks dentro de +-12 % de su posicion anatomica: se garantiza con los limites de
    cada parametro (desplazamientos de patas <= 0.04 m = 9.5 % de la cruz; cabeza <= 0.025 m
    = 11 % de su longitud; inclinacion <= 6 grados).
Cada evaluacion tarda ~3 s (rejilla de 6 mm, mascaras a 1/4 de resolucion); con 4 procesos
se hacen cientos de evaluaciones en minutos. Escribe fit/fit_log.csv, fit/fit_summary.json,
superposiciones del mejor y, con --write, el mejor conjunto en src/params.json (copia del
anterior en fit/params_before_fit.json).
"""
import os
import sys
import json
import copy
import time
import math
import argparse

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import silhouette as SIL          # noqa: E402
from pecari_sdf import AnatomyModel, to_world, to_can, surface_along   # noqa: E402
import jsonfmt                    # noqa: E402

OUT = os.path.join(ROOT, "fit")
H_GRID = 0.006
SCALE = 0.25
W_SIDE, W_FRONT = 0.6, 0.4
UPPER_ONLY = True      # etapa 2b: solo tronco y cabeza (z > 0.22 m); las patas siguen la anatomia
SIDE_REF = "real_side_walking"   # etapa 2b: la lateral de referencia es la FOTO REAL
EAR_FACTOR = 0.9125     # oreja medida en la malla / parametro length (CC nivel 1), medido en v06
FRONT_JOINTS = ["scapula", "shoulder", "elbow", "olecranon", "carpus", "fetlock_f", "coronet_f",
                "hoof_back_f", "toe_f", "heel_f", "sole_f"]
HIND_JOINTS = ["hip", "stifle", "hock", "calcaneus", "fetlock_h", "coronet_h", "hoof_back_h",
               "toe_h", "heel_h", "sole_h", "hamstring_top", "gaskin_ring"]


# ----------------------------------------------------------------------------
# Espacio de parametros
# ----------------------------------------------------------------------------
def param_space(P):
    """Lista de (nombre, tipo, lo, hi). tipo 'add' suma, 'mul' multiplica (base 1)."""
    sp = []
    n = len(P["body"]["stations"])
    for i in range(1, n):
        sp.append(("st%d.ztop" % i, "add", -0.03, 0.03))
        sp.append(("st%d.zbot" % i, "add", -0.03, 0.03))
    sp += [("w.neck", "mul", 0.85, 1.15), ("w.trunk", "mul", 0.88, 1.12), ("w.rump", "mul", 0.85, 1.15),
           ("rump.cy", "add", -0.03, 0.03), ("rump.cz", "add", -0.03, 0.03), ("rump.rz", "add", -0.02, 0.02),
           ("shoulder.rx", "mul", 0.7, 1.2),
           ("head.pitch", "add", -3.0, 6.0), ("head.ny", "add", -0.025, 0.025), ("head.nz", "add", -0.025, 0.025),
           ("head.su", "mul", 0.92, 1.05), ("head.sz", "mul", 0.90, 1.10), ("head.sw", "mul", 0.88, 1.08),
           ("jaw.sz", "mul", 0.80, 1.10),
           ("ear.length", "add", -0.008, 0.006), ("ear.dx", "add", -0.15, 0.15), ("ear.dy", "add", -0.12, 0.15),
           ("ear.u", "add", -0.015, 0.012),
           ("front.dy", "add", -0.03, 0.03), ("hind.dy", "add", -0.02, 0.02)]
    if UPPER_ONLY:     # las patas no se ajustan a una foto al paso
        sp = [s for s in sp if s[0] not in ("front.dy", "hind.dy")]
    return sp


def apply(P0, sp, x):
    P = copy.deepcopy(P0)
    v = dict(zip([s[0] for s in sp], x))
    st = P["body"]["stations"]
    n = len(st)
    for i in range(1, n):
        st[i][1] += v["st%d.ztop" % i]
        st[i][2] += v["st%d.zbot" % i]
        st[i][1] = max(st[i][1], st[i][2] + 0.03)
    for i in range(n):
        g = "w.neck" if i <= 3 else ("w.trunk" if i <= 8 else "w.rump")
        st[i][3] *= v[g]
    ell = P["body"]["ellipsoids"]
    ell[2]["c"][1] += v["rump.cy"]
    ell[2]["c"][2] += v["rump.cz"]
    ell[2]["r"][2] += v["rump.rz"]
    ell[1]["r"][0] *= v["shoulder.rx"]
    H = P["head"]
    H["pitch_deg"] += v["head.pitch"]
    H["nuchal_world"][1] += v["head.ny"]
    H["nuchal_world"][2] += v["head.nz"]
    su, sz, sw = v["head.su"], v["head.sz"], v["head.sw"]
    for s in H["stations"]:
        s[0] *= su
        s[1] *= sz
        s[2] *= sz
        s[3] *= sw
    for e in H["ellipsoids"]:
        e["c"] = [e["c"][0] * sw, e["c"][1] * su, e["c"][2] * sz]
        e["r"] = [e["r"][0] * sw, e["r"][1] * su, e["r"][2] * sz]
    H["nuchal_can"] = [0.0, H["nuchal_can"][1] * su, H["nuchal_can"][2] * sz]
    H["cage"]["rings_u"] = [u * su for u in H["cage"]["rings_u"]]
    H["mouth_corner"]["u"] *= su
    H["mouth_corner"]["z"] *= sz
    J = P["jaw"]
    for s in J["stations"]:
        s[0] *= su
        s[1] *= sz
        s[2] *= sz * v["jaw.sz"]
        s[3] *= sw
    for e in J["ellipsoids"]:
        e["c"] = [e["c"][0] * sw, e["c"][1] * su, e["c"][2] * sz * v["jaw.sz"]]
    J["cage"]["rings_u"] = [u * su for u in J["cage"]["rings_u"]]
    for k in ("eye", "canine"):
        P[k]["u"] *= su
        P[k]["z"] *= sz
    A = P["ear"]
    A["length"] += v["ear.length"]
    A["dir_world"][0] += v["ear.dx"]
    A["dir_world"][1] += v["ear.dy"]
    A["u"] = A["u"] * su + v["ear.u"]
    S = P["skeleton"]
    for j in FRONT_JOINTS:
        S[j][1] += v.get("front.dy", 0.0)
    for j in HIND_JOINTS:
        S[j][1] += v.get("hind.dy", 0.0)
    for key, j in (("front_leg_y", "front.dy"), ("hind_leg_y", "hind.dy")):
        P["landmarks"][key] += v.get(j, 0.0)
    return P


# ----------------------------------------------------------------------------
# Medidas aproximadas desde el SDF (mismas definiciones que build_pecari.measure)
# ----------------------------------------------------------------------------
def sdf_measures(P, m, occ, axes, h):
    xs, ys, zs = axes
    LM = P["landmarks"]
    M = {}
    disc = to_world(np.array([0.0, P["head"]["disc_u"], 0.0]), m.R, m.T)
    nuc = np.array(P["head"]["nuchal_world"], float)
    tb = np.array(LM["tail_base"], float)
    M["head_length"] = float(np.linalg.norm(disc - nuc))
    M["hb_length"] = M["head_length"] + float(np.linalg.norm(nuc - tb))
    M["head_hb_ratio"] = M["head_length"] / M["hb_length"]
    side = occ.any(axis=0)                       # (y, z)
    mid = occ[0]                                 # x = 0
    ztop = np.where(side.any(1), zs[np.argmax(side * (np.arange(len(zs)) + 1), axis=1)], 0.0)

    def top_at(y, half=0.02):
        sel = np.abs(ys - y) <= half
        return float(ztop[sel].max())
    M["withers_height"] = top_at(LM["withers_y"])
    M["croup_height"] = top_at(LM["croup_y"])
    j = np.argmin(np.abs(ys - LM["withers_y"]))
    col = np.nonzero(mid[j])[0]
    M["chest_depth"] = float(zs[col.max()] - zs[col.min()]) if len(col) else 0.0
    y0, y1 = LM["front_leg_y"] + 0.05, LM["hind_leg_y"] - 0.05
    bots = []
    for j in np.nonzero((ys > y0) & (ys < y1))[0]:
        col = np.nonzero(mid[j])[0]
        if len(col):
            bots.append(zs[col.min()])
    M["belly_clearance"] = float(min(bots)) if bots else 0.0
    body_only = occ.copy()
    # ancho del cuerpo: |x| maximo por encima de body_width_zmin y detras de la cabeza
    zsel = zs > LM["body_width_zmin"]
    ysel = ys > nuc[1] + 0.03
    sub = body_only[:, ysel][:, :, zsel]
    xi = np.nonzero(sub.any(axis=(1, 2)))[0]
    M["body_width"] = float(2 * xs[xi.max()]) if len(xi) else 0.0
    # ancho de cabeza: barrido lateral de cabeza + mandibula en el marco canonico
    us = np.linspace(0.08, 0.26, 19)
    zc = np.linspace(-0.09, 0.10, 39)
    U, Z = np.meshgrid(us, zc, indexing="ij")
    xr = np.linspace(0.0, 0.09, 91)
    best = 0.0
    for xv in xr[::-1]:
        Q = np.stack([np.full(U.size, xv), U.ravel(), Z.ravel()], 1)
        if (np.minimum(m.head(Q), m.jaw(Q)) <= 0).any():
            best = xv
            break
    M["head_width"] = 2 * best
    M["ear_length"] = P["ear"]["length"] * EAR_FACTOR
    M["mass_kg"] = float(occ.sum()) * h ** 3 * 2.0 * 1000.0
    st0 = P["head"]["stations"][1]
    M["disc_width"] = 2 * st0[3] * 0.94
    return M


W_SMOOTH = 2.0     # diseno a mano: ~0.005; perfil ondulado del ajuste 1: ~0.33


def smooth_penalty(P):
    """Suavidad de los perfiles dorsal y ventral: suma de (segunda diferencia)^2 por
    estacion, con la nuca de la cabeza como primer punto del perfil dorsal (une cuello y
    cabeza sin escalon)."""
    st = np.array(P["body"]["stations"], float)
    nuc = P["head"]["nuchal_world"]
    y = np.concatenate([[nuc[1]], st[1:, 0]])
    zt = np.concatenate([[nuc[2]], st[1:, 1]])
    pen = 0.0
    for z in (zt, np.concatenate([[st[1, 2]], st[1:, 2]])):
        # segunda derivada discreta con paso no uniforme
        d1 = np.diff(z) / np.diff(y)
        d2 = np.diff(d1) / (0.5 * (y[2:] - y[:-2]))
        pen += float(np.sum((d2 * 0.05 ** 2) ** 2))   # curvatura en escala de 5 cm
    return W_SMOOTH * pen


def penalty(P, M):
    pen = smooth_penalty(P)
    det = {"smooth": round(pen, 4)} if pen > 0.01 else {}
    for k, val in M.items():
        t = P["targets"].get(k)
        if not t:
            continue
        margin = 0.20 if k == "mass_kg" else 0.07
        e = abs(val / t["value"] - 1.0)
        if e > margin:
            pen += 4.0 * (e - margin)
            det[k] = round(e, 3)
    return pen, det


# ----------------------------------------------------------------------------
# Evaluacion (en procesos hijos)
# ----------------------------------------------------------------------------
_REFS = None
_P0 = None
_SP = None


def _init(P0, sp):
    global _REFS, _P0, _SP
    _P0, _SP = P0, sp
    _REFS = {v: SIL.Reference(v, SCALE) for v in (SIDE_REF, "front")}


def evaluate(x):
    t = time.time()
    try:
        P = apply(_P0, _SP, x)
        m = AnatomyModel(P)
        lo, hi = m.bbox()
        occ_skin, axes = SIL.occupancy_grid(m.skin, lo, hi, H_GRID)
        occs = {1.0: SIL.add_fur(occ_skin, axes, m.fur_t, H_GRID)}
        hm = float(axes[2][np.nonzero(occs[1.0].any(axis=(0, 1)))[0].max()])
        nose, tail = m.nose_y(), float(P["landmarks"]["tail_base"][1])
        iou = {}
        for view, ref in _REFS.items():
            fs = ref.fur_scale
            if fs not in occs:
                occs[fs] = SIL.add_fur(occ_skin, axes, lambda Q: m.fur_t(Q) * fs, H_GRID)
            proj = SIL.project_grid(occs[fs], axes)
            al = SIL.Alignment(ref, nose, tail, hm)
            sil = SIL.grid_silhouette(proj, al, ref, polys=m.ears_furred())
            if UPPER_ONLY:
                cut = al.upper_cut()
                iou[view] = SIL.iou(sil[:cut], ref.mask[:cut])
            else:
                iou[view] = SIL.iou(sil, ref.mask)
        M = sdf_measures(P, m, occ_skin, axes, H_GRID)
        pen, det = penalty(P, M)
        score = W_SIDE * iou[SIDE_REF] + W_FRONT * iou["front"]
        return {"f": -score + pen, "score": score, "iou": iou, "pen": pen, "viol": det,
                "M": M, "t": time.time() - t}
    except Exception as e:   # parametros degenerados
        return {"f": 10.0, "score": 0.0, "iou": {}, "pen": 10.0, "viol": {"error": str(e)[:80]},
                "M": {}, "t": time.time() - t}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evals", type=int, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sigma", type=float, default=0.3)
    ap.add_argument("--tag", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--params", default=os.path.join(SRC, "params.json"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    import cma
    import multiprocessing as mp
    os.makedirs(OUT, exist_ok=True)
    P0 = json.load(open(a.params))
    sp = param_space(P0)
    lo = np.array([s[2] for s in sp])
    hi = np.array([s[3] for s in sp])
    base = np.array([1.0 if s[1] == "mul" else 0.0 for s in sp])
    # CMA trabaja en [0,1]^n normalizado
    x0n = (base - lo) / (hi - lo)
    to_x = lambda z: lo + np.clip(z, 0, 1) * (hi - lo)
    _init(P0, sp)
    r0 = evaluate(base)
    print("inicio: score %.4f IoU %s pen %.3f %s" % (r0["score"], {k: round(v, 4) for k, v in r0["iou"].items()},
                                                    r0["pen"], r0["viol"]), flush=True)
    es = cma.CMAEvolutionStrategy(x0n, a.sigma, {"bounds": [0, 1], "seed": a.seed, "maxfevals": a.evals,
                                                 "verb_disp": 0, "popsize": 16})
    log = open(os.path.join(OUT, "fit_log%s.csv" % a.tag), "w")
    log.write("eval,gen,f,score,iou_side,iou_front,penalty,violations\n")
    best = (r0["f"], base, r0)
    ne = 0
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers, initializer=_init, initargs=(P0, sp)) as pool:
        while not es.stop():
            Z = es.ask()
            X = [to_x(z) for z in Z]
            R = pool.map(evaluate, X)
            es.tell(Z, [r["f"] for r in R])
            for x, r in zip(X, R):
                ne += 1
                log.write("%d,%d,%.5f,%.5f,%.5f,%.5f,%.4f,\"%s\"\n" % (
                    ne, es.countiter, r["f"], r["score"], r["iou"].get(SIDE_REF, 0), r["iou"].get("front", 0),
                    r["pen"], r["viol"]))
                if r["f"] < best[0]:
                    best = (r["f"], x, r)
            log.flush()
            print("gen %3d evals %4d  mejor f %.4f score %.4f (lat %.4f fr %.4f) pen %.3f  %.0fs" % (
                es.countiter, ne, best[0], best[2]["score"], best[2]["iou"].get(SIDE_REF, 0),
                best[2]["iou"].get("front", 0), best[2]["pen"], time.time() - t0), flush=True)
    log.close()
    f, xb, rb = best
    Pb = apply(P0, sp, xb)
    summary = {"evals": ne, "seconds": time.time() - t0, "start": {"score": r0["score"], "iou": r0["iou"],
               "penalty": r0["pen"], "violations": r0["viol"]},
               "best": {"score": rb["score"], "iou": rb["iou"], "penalty": rb["pen"], "violations": rb["viol"],
                        "measures_sdf": rb["M"]},
               "params": {s[0]: float(v) for s, v in zip(sp, xb)}}
    json.dump(summary, open(os.path.join(OUT, "fit_summary%s.json" % a.tag), "w"), indent=1)
    # superposiciones del mejor (resolucion de informe)
    res, _, _ = SIL.evaluate_model(Pb, h=0.004, scale=0.5, out_dir=OUT)
    print("mejor (rejilla 4 mm): %s" % {k: round(v, 4) for k, v in res.items() if k.endswith("upper_z022")})
    if a.write:
        jsonfmt.dump(P0, os.path.join(OUT, "params_before_fit%s.json" % a.tag))
        jsonfmt.dump(Pb, a.params)
        print("params.json actualizado")


if __name__ == "__main__":
    main()
