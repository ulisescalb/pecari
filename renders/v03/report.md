# Informe v03

Generado por src/build_pecari.py (2026-11-05 03:06). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.919 m | +2.1 % | ±5 % | lit | si |
| withers_height | 0.420 m | 0.420 m | +0.0 % | ±5 % | lit | si |
| head_length | 0.230 m | 0.238 m | +3.5 % | ±5 % | lit | si |
| head_hb_ratio | 0.255  | 0.259  | +1.6 % | ±5 % | user | si |
| ear_length | 0.075 m | 0.067 m | -10.3 % | ±5 % | user | NO |
| hind_foot | 0.210 m | 0.175 m | -16.5 % | ±5 % | lit | NO |
| croup_height | 0.405 m | 0.408 m | +0.6 % | ±5 % | design | si |
| chest_depth | 0.225 m | 0.230 m | +2.3 % | ±5 % | design | si |
| belly_clearance | 0.190 m | 0.185 m | -2.6 % | ±5 % | design | si |
| body_width | 0.215 m | 0.224 m | +4.3 % | ±5 % | design | si |
| head_width | 0.115 m | 0.124 m | +7.7 % | ±5 % | lit | NO |
| disc_width | 0.046 m | 0.045 m | -1.8 % | ±5 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | +0.0 % | ±5 % | design | si |
| canine_exposed | 0.013 m | 0.013 m | +2.5 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 23.053 kg | +4.8 % | ±25 % | lit | si |

Volumen union = 0.02305 m3 (suma de piezas 0.02400 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4482 | 4480 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02190 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00158 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00051 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 8306 | 8288 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=290, Head=81
- fur_collar: Body=130
- fur_belly: Body=346
- fur_legs: Body=1246
- bare_hooves: Body=292
- fur_face: Head=1701, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=189

## Tiempos

- body: 3.2 s
- head+jaw: 1.5 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.1 s
- measure: 0.2 s
- render: 116.0 s

Todas las medidas dentro de tolerancia: **NO**
