# Informe v05

Generado por src/build_pecari.py (2026-11-05 03:32). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.923 m | +2.5 % | ±5 % | lit | si |
| withers_height | 0.420 m | 0.419 m | -0.1 % | ±5 % | lit | si |
| head_length | 0.230 m | 0.238 m | +3.5 % | ±5 % | lit | si |
| head_hb_ratio | 0.255  | 0.258  | +1.2 % | ±5 % | user | si |
| ear_length | 0.075 m | 0.075 m | +0.1 % | ±5 % | user | si |
| hind_foot | 0.210 m | 0.203 m | -3.2 % | ±5 % | lit | si |
| croup_height | 0.405 m | 0.407 m | +0.5 % | ±5 % | design | si |
| chest_depth | 0.225 m | 0.230 m | +2.2 % | ±5 % | design | si |
| belly_clearance | 0.190 m | 0.184 m | -3.0 % | ±5 % | design | si |
| body_width | 0.215 m | 0.208 m | -3.3 % | ±5 % | design | si |
| head_width | 0.115 m | 0.120 m | +4.0 % | ±5 % | lit | si |
| disc_width | 0.046 m | 0.045 m | -1.9 % | ±5 % | design | si |
| eye_diameter | 0.017 m | 0.017 m | +0.0 % | ±5 % | design | si |
| canine_exposed | 0.013 m | 0.013 m | +2.8 % | ±10 % | design | si |
| mass_kg | 22.000 kg | 22.657 kg | +3.0 % | ±25 % | lit | si |

Volumen union = 0.02266 m3 (suma de piezas 0.02360 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4482 | 4480 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02150 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00157 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00051 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00001 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 8306 | 8288 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=286, Head=85
- fur_collar: Body=132
- fur_belly: Body=340
- fur_legs: Body=1240
- bare_hooves: Body=316
- fur_face: Head=1697, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=193

## Tiempos

- body: 4.8 s
- head+jaw: 1.7 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.1 s
- measure: 0.2 s
- render: 132.9 s

Todas las medidas dentro de tolerancia: **si**
