"""
Extrae mascaras de silueta de las fotos de referencia (fondo blanco).

Uso:  python src/reference_masks.py            (venv con opencv)

Metodo: umbral sobre "no-blanco" (min de canales y saturacion) -> semilla de GrabCut
(OpenCV) -> mayor componente conexo -> relleno de huecos (la banda clara del collar
no debe agujerear la silueta) -> recorte por debajo de la linea de suelo (la sombra
gris bajo las pezunas no es animal). Guarda reference/masks/<vista>.png y una
superposicion de control reference/masks/<vista>_check.jpg.
"""
import os
import json
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")
OUT = os.path.join(REF, "masks")


def extract(path, ground_y=None, thr=212):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    mn = img.min(axis=2).astype(np.int16)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.int16)
    fg = (mn < thr) | (sat > 60)
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # GrabCut sembrado con el umbral
    gc = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    gc[cv2.erode(fg, np.ones((9, 9), np.uint8)) > 0] = cv2.GC_FGD
    gc[(fg > 0) & (gc != cv2.GC_FGD)] = cv2.GC_PR_FGD
    gc[mn > 245] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    m = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    # suelo: ultima fila con pixeles oscuros de pezuna; la sombra (gris claro) cerca
    # del suelo no es animal
    if ground_y is None:
        dark = (mn < 110) & (m > 0)
        rows = np.nonzero(dark.any(axis=1))[0]
        ground_y = int(rows.max())
    m[ground_y + 1:, :] = 0
    low = np.zeros_like(m, bool)
    low[ground_y - 90:, :] = True
    m[low & (mn > 150) & (sat < 60)] = 0
    # mayor componente
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = (lab == k).astype(np.uint8)
    # huecos: se rellenan los no blancos (banda del collar, reflejos); los blancos
    # (espacio entre patas) se dejan abiertos
    inv = (1 - m).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if x == 0 or y == 0 or x + ww >= w or y + hh >= h:
            continue
        hole = lab == i
        if area < 1500 or mn[hole].mean() < 228:
            m[hole] = 1
    return img, m * 255, ground_y


def extract_rect(path, rect, iters=6):
    """Foto con fondo natural: GrabCut inicializado con un rectangulo + mayor componente."""
    img = cv2.imread(path)
    gc = np.zeros(img.shape[:2], np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, tuple(rect), bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    m = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = (lab == k).astype(np.uint8)
    inv = (1 - m).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < 3000 and x > 0 and y > 0:
            m[lab == i] = 1
    return img, m * 255


def main():
    os.makedirs(OUT, exist_ok=True)
    meta_path = os.path.join(REF, "ref_landmarks.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    for view in ("side", "front", "three_quarter"):
        src = os.path.join(REF, "ref_%s.jpg" % view)
        if not os.path.exists(src):
            continue
        img, mask, gy = extract(src)
        cv2.imwrite(os.path.join(OUT, view + ".png"), mask)
        over = img.copy()
        edge = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)) > 0
        over[edge] = (0, 0, 255)
        tint = over.copy()
        tint[mask == 0] = (tint[mask == 0] * 0.5 + np.array([255, 200, 120]) * 0.5).astype(np.uint8)
        cv2.imwrite(os.path.join(OUT, view + "_check.jpg"), cv2.resize(tint, (1000, 558)))
        ys, xs = np.nonzero(mask)
        info = {"ground_y_auto": int(gy), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "area_px": int((mask > 0).sum())}
        meta.setdefault(view, {}).update(info)
        print(view, info)
    # foto real lateral (fondo natural): GrabCut con rectangulo
    for view, rect in (("real_side_walking", (62, 165, 860, 495)),):
        src = os.path.join(REF, view + ".jpg")
        if not os.path.exists(src):
            continue
        img, mask = extract_rect(src, rect)
        cv2.imwrite(os.path.join(OUT, view + ".png"), mask)
        over = img.copy()
        edge = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        over[edge] = (0, 0, 255)
        over[mask == 0] = (over[mask == 0] * 0.4 + np.array([255, 200, 120]) * 0.6).astype(np.uint8)
        cv2.imwrite(os.path.join(OUT, view + "_check.jpg"), over)
        ys, xs = np.nonzero(mask)
        meta.setdefault(view, {}).update({"bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]})
        print(view, meta[view]["bbox"])
    json.dump(meta, open(meta_path, "w"), indent=1)


if __name__ == "__main__":
    main()
