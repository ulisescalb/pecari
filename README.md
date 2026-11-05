# Pecarí de collar (*Pecari tajacu*) — malla base procedural

Malla base para juegos de estrategia (Unity y three.js vía GLB). La generan scripts de Blender a
partir de `src/params.json`. Las decisiones y las críticas de cada versión están en
`iteration_log.md`, y las medidas con sus fuentes en `reference/medidas.md`.

## Regenerar

```bash
blender -b -P src/build_pecari.py -- --version v12          # Blender 4.x/5.x instalado
python src/build_pecari.py --version v12                    # o bpy de PyPI (venv, ver abajo)
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
python src/silhouette.py --version v12        # IoU de la malla de una versión + superposiciones
python src/fit_silhouette.py --evals 1500 --write   # CMA-ES de los parámetros del SDF contra las fotos
```

Métrica desde la etapa 2b: IoU de **tronco y cabeza** (z > 0,22 m). La lateral se mide contra la
foto real `reference/real_side_walking.jpg` y la frontal contra la imagen IA, escalada por la
altura del modelo. Las patas, al paso en todas las fotos, no se ajustan. Las proporciones salen de
las fotos reales (`reference/medidas.md`); las imágenes IA solo dan el aspecto general.

## Estructura

| ruta | contenido |
|---|---|
| `src/params.json` | todas las proporciones: esqueleto, tronco, cabeza, mandíbula, orejas, pelaje, grupos de vértices y objetivos |
| `src/pecari_sdf.py` | modelo numérico (SDF, proyección, relajación, esqueleto, `AnatomyModel`); sin bpy |
| `src/build_pecari.py` | construye, valida, mide, exporta (`.blend`, `.glb`, landmarks) y renderiza |
| `src/render_views.py` | renders de arcilla, silueta, grupos de pelaje, alambre y hoja de contacto |
| `src/silhouette.py`, `src/fit_silhouette.py` | métrica IoU contra fotos y optimizador |
| `src/compare_sheet.py` | hoja comparativa por vista (lateral IA, lateral real, frontal, 3/4, cabeza) |
| `reference/` | fotos de referencia, máscaras, hitos de píxel y `medidas.md` |
| `export/landmarks.json` | puntos anatómicos y huesos para el rig |
| `blend/` | `pecari_vNN.blend` / `.glb` (y `_lod1`/`_lod2` si se piden) |
| `renders/vNN/` | vistas, `contact_sheet.png`, `comparativa.png` (referencia a la izquierda, render a la derecha), `iou_*.png`, `report.md`, `params_used.json` |
| `fit/` | registro y resumen del optimizador |

Convenciones: metros, Z arriba, el animal mira hacia −Y y el origen está en el suelo, centrado
entre las pezuñas. Las 9 piezas se llaman `Pecari_Body`, `Pecari_Head`, `Pecari_LowerJaw`,
`Pecari_EarL/R`, `Pecari_EyeL/R` y `Pecari_CanineL/R`. Grupos de vértices: `fur_mane`,
`fur_collar`, `fur_face`, `fur_belly`, `fur_legs`, `bare_snout` y `bare_hooves`.
