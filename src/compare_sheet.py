"""
Hoja comparativa: para cada vista, foto de referencia a la izquierda y render a la derecha,
recortados a su caja y escalados a la misma altura.

Uso:  python src/compare_sheet.py --version v10      (venv con opencv)
Lee renders/vNN/cmp_*.png (fondo transparente, generados por render_views.py) y las fotos de
reference/. Escribe renders/vNN/comparativa.png.
"""
import os
import json
import argparse

import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")
ROW_H = 360
BG = (96, 96, 102)

# vista -> (foto, recorte de la foto: "mask:<vista>" o [x0,y0,x1,y1], etiqueta)
ROWS = [
    ("lateral_ia", "ref_side.jpg", "mask:side", "Lateral - imagen IA (aspecto general; patas al paso)"),
    ("lateral_real", "real_side_walking.jpg", [70, 160, 920, 668], "Lateral - FOTO REAL (al paso)"),
    ("frontal_ia", "ref_front.jpg", "mask:front", "Frontal - imagen IA"),
    ("tres_cuartos_ia", "ref_three_quarter.jpg", "mask:three_quarter", "3/4 - imagen IA"),
    ("cabeza_real", "real_side_walking.jpg", [60, 195, 345, 480], "Cabeza - FOTO REAL"),
]


def crop_ref(img, spec):
    if isinstance(spec, str) and spec.startswith("mask:"):
        m = cv2.imread(os.path.join(REF, "masks", spec[5:] + ".png"), cv2.IMREAD_GRAYSCALE) > 0
        ys, xs = np.nonzero(m)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
        pad = int(0.04 * max(x1 - x0, y1 - y0))
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(img.shape[1] - 1, x1 + pad), min(img.shape[0] - 1, y1 + pad)
        return img[y0:y1, x0:x1]
    x0, y0, x1, y1 = spec
    return img[y0:y1, x0:x1]


def crop_render(path):
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    a = rgba[:, :, 3]
    ys, xs = np.nonzero(a > 8)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    pad = int(0.04 * max(x1 - x0, y1 - y0))
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(rgba.shape[1] - 1, x1 + pad), min(rgba.shape[0] - 1, y1 + pad)
    c = rgba[y0:y1, x0:x1].astype(np.float32)
    al = c[:, :, 3:4] / 255.0
    out = c[:, :, :3] * al + np.array(BG, np.float32) * (1 - al)
    return out.astype(np.uint8)


def fit_h(img, h):
    return cv2.resize(img, (max(1, int(round(img.shape[1] * h / img.shape[0]))), h), interpolation=cv2.INTER_AREA)


def build(version):
    d = os.path.join(ROOT, "renders", version)
    rows = []
    for name, ref, spec, label in ROWS:
        rp = os.path.join(d, "cmp_%s.png" % name)
        if not os.path.exists(rp):
            continue
        a = fit_h(crop_ref(cv2.imread(os.path.join(REF, ref)), spec), ROW_H)
        b = fit_h(crop_render(rp), ROW_H)
        gap = np.full((ROW_H, 12, 3), 255, np.uint8)
        row = np.hstack([a, gap, b])
        bar = np.full((34, row.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%s   |   render %s" % (label, version), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (20, 20, 20), 1, cv2.LINE_AA)
        rows.append(np.vstack([bar, row]))
    W = max(r.shape[1] for r in rows)
    rows = [np.hstack([r, np.full((r.shape[0], W - r.shape[1], 3), 255, np.uint8)]) for r in rows]
    sheet = np.vstack(rows)
    out = os.path.join(d, "comparativa.png")
    cv2.imwrite(out, sheet)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    print(build(ap.parse_args().version))
