# Informe v01

Generado por src/build_pecari.py (2026-11-05 02:57). Render: Cycles CPU.

## Medidas calculadas desde la malla

| medida | objetivo | malla | error | tol | fuente | ok |
|---|---:|---:|---:|---:|---|:-:|
| hb_length | 0.900 m | 0.916 m | +1.8 % | ±5 % | lit | si |
| withers_height | 0.420 m | 0.419 m | -0.2 % | ±5 % | lit | si |
| head_length | 0.230 m | 0.238 m | +3.3 % | ±5 % | lit | si |
| head_hb_ratio | 0.255  | 0.259  | +1.7 % | ±5 % | user | si |
| ear_length | 0.075 m | 0.074 m | -0.8 % | ±5 % | user | si |
| hind_foot | 0.210 m | 0.175 m | -16.6 % | ±5 % | lit | NO |
| croup_height | 0.415 m | 0.421 m | +1.5 % | ±5 % | design | si |
| chest_depth | 0.225 m | 0.226 m | +0.6 % | ±5 % | design | si |
| belly_clearance | 0.190 m | 0.188 m | -1.0 % | ±5 % | design | si |
| body_width | 0.215 m | 0.227 m | +5.7 % | ±5 % | design | NO |
| head_width | 0.115 m | 0.117 m | +1.6 % | ±5 % | lit | si |
| disc_width | 0.046 m | 0.043 m | -7.3 % | ±5 % | design | NO |
| eye_diameter | 0.017 m | 0.017 m | -0.0 % | ±5 % | design | si |
| canine_exposed | 0.013 m | 0.022 m | +72.3 % | ±10 % | design | NO |
| mass_kg | 22.000 kg | 25.121 kg | +14.2 % | ±25 % | lit | si |

Volumen union = 0.02512 m3 (suma de piezas 0.02584 m3; la diferencia es el solape cabeza/cuello/mandibula).

## Validacion de malla

| objeto | verts | quads | tris | ngons | no-manifold | bordes | sueltos | normales incons. | autointers. | volumen m3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pecari_Body | 4482 | 4480 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.02405 |
| Pecari_Head | 1890 | 1888 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00109 |
| Pecari_LowerJaw | 930 | 928 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00069 |
| Pecari_EyeL | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarL | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_CanineL | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EyeR | 98 | 96 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_EarR | 354 | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| Pecari_CanineR | 50 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00000 |
| **total** | 8306 | 8288 | 0 | 0 | | | | | | |

## Grupos de vertices (vertices con peso > 0.5)

- fur_mane: Body=239, Head=98
- fur_collar: Body=139
- fur_belly: Body=344
- fur_legs: Body=1252
- bare_hooves: Body=292
- fur_face: Head=1701, LowerJaw=930, EarL=354, EarR=354
- bare_snout: Head=189

## Tiempos

- body: 3.1 s
- head+jaw: 1.6 s
- parts: 0.0 s
- groups: 0.0 s
- validate: 0.1 s
- measure: 0.2 s
- render: 116.8 s

Todas las medidas dentro de tolerancia: **NO**
