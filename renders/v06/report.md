# Informe v06

Generado por src/build_pecari.py (2026-11-05 04:11). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.844 m | -6.2 % | ±8 % | lit | si |
| withers_height | 0.420 m | 0.451 m | +7.5 % | ±8 % | lit | si |
| head_length | 0.230 m | 0.246 m | +6.8 % | ±8 % | lit | si |
| head_hb_ratio | 0.255  | 0.291  | +14.1 % | ±8 % | user | NO |
| ear_length | 0.075 m | 0.074 m | -1.9 % | ±8 % | user | si |
| hind_foot | 0.210 m | 0.212 m | +1.0 % | ±8 % | lit | si |
| croup_height | 0.430 m | 0.425 m | -1.1 % | ±8 % | design-photo | si |
| chest_depth | 0.225 m | 0.225 m | +0.1 % | ±8 % | design | si |
| belly_clearance | 0.225 m | 0.225 m | +0.2 % | ±8 % | design-photo | si |
| body_width | 0.215 m | 0.229 m | +6.4 % | ±8 % | design | si |
| head_width | 0.115 m | 0.118 m | +2.9 % | ±8 % | lit | si |
| disc_width | 0.046 m | 0.046 m | +0.2 % | ±8 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | -0.0 % | ±8 % | design | si |
| canine_exposed | 0.013 m | 0.013 m | -1.0 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 21.866 kg | -0.6 % | ±25 % | lit | si |

IoU de silueta (piel + pelaje) contra las fotos: **lateral 0.831**, **frontal 0.797** (superposiciones iou_side.png / iou_front.png).

Volumen union = 0.02187 m3 (suma de piezas 0.02354 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4290 | 4288 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0.02100 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00211 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00040 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 8114 | 8096 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=240, Head=100
- fur_collar: Body=151
- fur_belly: Body=239
- fur_legs: Body=1216
- bare_hooves: Body=316
- fur_face: Head=1697, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=193

## Tiempos

- body: 7.1 s
- head+jaw: 1.9 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.0 s
- measure: 0.2 s
- render: 167.5 s
- iou: 0.2 s

Todas las medidas dentro de tolerancia: **NO**
