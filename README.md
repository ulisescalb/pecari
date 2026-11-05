# Pecarí de collar (*Pecari tajacu*) — malla base procedural

Malla base para juegos de estrategia (Unity y three.js vía GLB). La generan scripts de Blender a
partir de `src/params.json`. Las decisiones y las críticas de cada versión están en
`iteration_log.md`, y las medidas con sus fuentes en `reference/medidas.md`.

## Regenerar

```bash
blender -b -P src/build_pecari.py -- --version v08          # Blender 4.x/5.x instalado
python src/build_pecari.py --version v08                    # o bpy de PyPI (venv, ver abajo)
```

Opciones: `--no-render`, `--lods` (LOD1/LOD2 por decimación), `--samples N`,
`--engine auto|cycles_gpu|cycles_cpu|eevee` y `--params otro.json` (por ejemplo, una variante
con `meta.global_scale`).

Entorno con bpy de PyPI (Python 3.11):

```bash
python3.11 -m venv ~/.venvs/pecari && ~/.venvs/pecari/bin/pip install -r requirements.txt
```

## Herramientas de silueta (sin Blender)

```bash
python src/reference_masks.py                 # máscaras de reference/ref_*.jpg -> reference/masks/
python src/silhouette.py --version v08        # IoU de la malla de una versión + superposiciones
python src/fit_silhouette.py --evals 1500 --write   # CMA-ES de los parámetros del SDF contra las fotos
```

## Estructura

| ruta | contenido |
|---|---|
| `src/params.json` | todas las proporciones: esqueleto, tronco, cabeza, mandíbula, orejas, pelaje, grupos de vértices y objetivos |
| `src/pecari_sdf.py` | modelo numérico (SDF, proyección, relajación, esqueleto, `AnatomyModel`); sin bpy |
| `src/build_pecari.py` | construye, valida, mide, exporta (`.blend`, `.glb`, landmarks) y renderiza |
| `src/render_views.py` | renders de arcilla, silueta, grupos de pelaje, alambre y hoja de contacto |
| `src/silhouette.py`, `src/fit_silhouette.py` | métrica IoU contra fotos y optimizador |
| `reference/` | fotos de referencia, máscaras, hitos de píxel y `medidas.md` |
| `export/landmarks.json` | puntos anatómicos y huesos para el rig |
| `blend/` | `pecari_vNN.blend` / `.glb` (y `_lod1`/`_lod2` si se piden) |
| `renders/vNN/` | vistas, `contact_sheet.png`, `iou_*.png`, `report.md`, `params_used.json` |
| `fit/` | registro y resumen del optimizador |

Convenciones: metros, Z arriba, el animal mira hacia −Y y el origen está en el suelo, centrado
entre las pezuñas. Las 9 piezas se llaman `Pecari_Body`, `Pecari_Head`, `Pecari_LowerJaw`,
`Pecari_EarL/R`, `Pecari_EyeL/R` y `Pecari_CanineL/R`. Grupos de vértices: `fur_mane`,
`fur_collar`, `fur_face`, `fur_belly`, `fur_legs`, `bare_snout` y `bare_hooves`.
