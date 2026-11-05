# Informe v09

Generado por src/build_pecari.py (2026-11-05 05:01). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.890 m | -1.1 % | ±8 % | lit | si |
| withers_height | 0.420 m | 0.440 m | +4.7 % | ±8 % | lit | si |
| head_length | 0.230 m | 0.232 m | +1.1 % | ±8 % | lit | si |
| head_hb_ratio | 0.255  | 0.261  | +2.4 % | ±8 % | user | si |
| ear_length | 0.075 m | 0.076 m | +1.0 % | ±8 % | user | si |
| hind_foot | 0.210 m | 0.196 m | -6.7 % | ±8 % | lit | si |
| croup_height | 0.430 m | 0.423 m | -1.7 % | ±8 % | design-photo | si |
| chest_depth | 0.225 m | 0.227 m | +1.1 % | ±8 % | design | si |
| belly_clearance | 0.225 m | 0.214 m | -4.8 % | ±8 % | design-photo | si |
| body_width | 0.215 m | 0.229 m | +6.3 % | ±8 % | design | si |
| head_width | 0.115 m | 0.118 m | +2.3 % | ±8 % | lit | si |
| disc_width | 0.046 m | 0.045 m | -1.1 % | ±8 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | +0.0 % | ±8 % | design | si |
| canine_exposed | 0.013 m | 0.013 m | -2.9 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 22.744 kg | +3.4 % | ±25 % | lit | si |

GLB reimportado: **identico** (Body ok, Head ok, LowerJaw ok, EyeL ok, EarL ok, CanineL ok, EyeR ok, EarR ok, CanineR ok).

IoU de silueta (piel + pelaje) contra las fotos: **lateral 0.850**, **frontal 0.809** (superposiciones iou_side.png / iou_front.png).

Volumen union = 0.02274 m3 (suma de piezas 0.02369 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4098 | 4096 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02121 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00204 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00043 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 88 | 0.00000 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 86 | 0.00000 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 7922 | 7904 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=248, Head=50
- fur_collar: Body=129
- fur_belly: Body=273
- fur_legs: Body=1170
- bare_hooves: Body=316
- fur_face: Head=1689, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=201

## Tiempos

- body: 7.2 s
- head+jaw: 1.9 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.0 s
- measure: 0.2 s
- render: 169.2 s
- iou: 0.2 s

Todas las medidas dentro de tolerancia: **si**
