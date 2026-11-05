# Informe v12

Generado por src/build_pecari.py (2026-11-05 06:26). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.914 m | +1.5 % | ±8 % | lit | si |
| withers_height | 0.430 m | 0.426 m | -1.0 % | ±8 % | real-photo | si |
| head_length | 0.285 m | 0.301 m | +5.6 % | ±8 % | real-photo | si |
| head_hb_ratio | 0.320  | 0.329  | +3.0 % | ±8 % | real-photo | si |
| ear_length | 0.075 m | 0.071 m | -5.4 % | ±8 % | user | si |
| hind_foot | 0.210 m | 0.194 m | -7.4 % | ±8 % | lit | si |
| croup_height | 0.415 m | 0.396 m | -4.5 % | ±8 % | real-photo | si |
| chest_depth | 0.250 m | 0.259 m | +3.5 % | ±8 % | design | si |
| belly_clearance | 0.178 m | 0.167 m | -6.1 % | ±8 % | real-photo | si |
| body_width | 0.215 m | 0.219 m | +1.8 % | ±8 % | design | si |
| head_width | 0.130 m | 0.137 m | +5.1 % | ±8 % | design | si |
| disc_width | 0.050 m | 0.053 m | +6.4 % | ±8 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | +0.0 % | ±8 % | design | si |
| canine_exposed | 0.013 m | 0.014 m | +8.4 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 22.189 kg | +0.9 % | ±25 % | lit | si |

GLB reimportado: **identico** (Body ok, Head ok, LowerJaw ok, EyeL ok, EarL ok, CanineL ok, EyeR ok, EarR ok, CanineR ok).

IoU de silueta (piel + pelaje) **de tronco y cabeza (z > 0,22 m)**: lateral contra la FOTO REAL **0.934**, frontal (imagen IA, escalada por altura) **0.814**, lateral contra la imagen IA 0.746. Totales (incluyen patas al paso): 0.758 / 0.781 / 0.655. Superposiciones iou_*.png.

Volumen union = 0.02219 m3 (suma de piezas 0.02395 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4610 | 4608 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02110 |
| Pecari_Head | 1506 | 1504 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00247 |
| Pecari_LowerJaw | 802 | 800 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00033 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00002 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00002 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 7922 | 7904 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=250, Head=30
- fur_collar: Body=128
- fur_belly: Body=267
- fur_legs: Body=1348
- bare_hooves: Body=326
- fur_face: Head=1357, LowerJaw=802, EarL=354, EarR=354
- bare_snout: Head=149

## Tiempos

- body: 12.9 s
- head+jaw: 1.5 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.0 s
- measure: 0.2 s
- render: 231.1 s
- iou: 0.2 s

Todas las medidas dentro de tolerancia: **si**
