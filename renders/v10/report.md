# Informe v10

Generado por src/build_pecari.py (2026-11-05 06:07). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.909 m | +1.0 % | ±8 % | lit | si |
| withers_height | 0.430 m | 0.426 m | -1.0 % | ±8 % | real-photo | si |
| head_length | 0.285 m | 0.293 m | +2.9 % | ±8 % | real-photo | si |
| head_hb_ratio | 0.320  | 0.322  | +0.7 % | ±8 % | real-photo | si |
| ear_length | 0.075 m | 0.076 m | +1.4 % | ±8 % | user | si |
| hind_foot | 0.210 m | 0.193 m | -8.0 % | ±8 % | lit | si |
| croup_height | 0.415 m | 0.397 m | -4.4 % | ±8 % | real-photo | si |
| chest_depth | 0.250 m | 0.259 m | +3.5 % | ±8 % | design | si |
| belly_clearance | 0.178 m | 0.167 m | -6.1 % | ±8 % | real-photo | si |
| body_width | 0.215 m | 0.219 m | +1.8 % | ±8 % | design | si |
| head_width | 0.130 m | 0.130 m | +0.2 % | ±8 % | design | si |
| disc_width | 0.050 m | 0.053 m | +6.4 % | ±8 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | +0.0 % | ±8 % | design | si |
| canine_exposed | 0.013 m | 0.012 m | -7.2 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 22.768 kg | +3.5 % | ±25 % | lit | si |

GLB reimportado: **identico** (Body ok, Head ok, LowerJaw ok, EyeL ok, EarL ok, CanineL ok, EyeR ok, EarR ok, CanineR ok).

IoU de silueta (piel + pelaje) **de tronco y cabeza (z > 0,22 m)**: lateral contra la FOTO REAL **0.930**, frontal (imagen IA, escalada por altura) **0.796**, lateral contra la imagen IA 0.722. Totales (incluyen patas al paso): 0.755 / 0.769 / 0.633. Superposiciones iou_*.png.

Volumen union = 0.02277 m3 (suma de piezas 0.02538 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4610 | 4608 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02167 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00325 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00044 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 8434 | 8416 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=245, Head=81
- fur_collar: Body=128
- fur_belly: Body=267
- fur_legs: Body=1338
- bare_hooves: Body=326
- fur_face: Head=1741, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=149

## Tiempos

- body: 13.1 s
- head+jaw: 1.8 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.0 s
- measure: 0.2 s
- render: 242.3 s
- iou: 0.2 s

Todas las medidas dentro de tolerancia: **si**
