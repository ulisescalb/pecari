# Medidas de referencia — pecarí de collar (*Pecari tajacu*)

Este archivo documenta de dónde sale cada objetivo. **Los valores numéricos que usa el
script están en `src/params.json → targets`**; si cambias uno, cambia el otro.

Todas las medidas se refieren a la **superficie de la piel con el pelo aplastado** (la malla
base). El pelaje de la siguiente etapa sumará volumen. Lo más notable es la crin dorsal, que
erizada añade varios centímetros a la altura aparente de la cruz.

## Fuentes consultadas

La red de este entorno bloqueó la descarga directa de las páginas (solo hubo acceso al buscador).
Las cifras salen de los fragmentos que devolvió la búsqueda. Conviene comprobarlas en la fuente
antes de usarlas en otra especie.

| # | Fuente | Datos usados |
|---|---|---|
| 1 | Ultimate Ungulate, ficha *Pecari tajacu* — https://ultimateungulate.com/Artiodactyla/Pecari_tajacu.html | cabeza-cuerpo 80–105 cm; altura a la cruz 30–50 cm; cola 2,0–4,5 cm |
| 2 | Texas Tech NSRL, *Mammals of Texas (online)*, cuenta de *Pecari tajacu* — https://www.depts.ttu.edu/nsrl/mammals-of-texas-online-edition/Accounts_Artiodactyla/Pecari_tajacu.php | largo total 870–1016 mm; cola 12 mm; **pie trasero 210 mm**. (El mismo texto da "altura a la cruz 816 mm", que es incompatible con todo lo demás; lo tomo como errata.) |
| 3 | Wikipedia, *Collared peccary* — https://en.wikipedia.org/wiki/Collared_peccary | masa adulta habitual 14–31 kg (con máximos de ~40 kg); comparación cualitativa con suidos |
| 4 | Plazi, tratamiento taxonómico de *P. tajacu* (material Yavarí–Ucayali) — https://tb.plazi.org/GgServer/html/03E587ECFFF9FFE17729FC38820EF916 | longitud cóndilo-incisiva del cráneo 211,3 ± 6,0 mm (n = 7) |
| 5 | Skullsite, cráneo de pecarí de collar — https://www.skullsite.co.uk/Peccary/peccary.htm | un cráneo: largo 237 mm, ancho cigomático 105 mm |
| 6 | Brief del usuario | HB ≈ 0,90 m; cruz ≈ 0,42 m; 22 kg; cabeza 24–27 % de HB; oreja 7–8 cm |

Para la variante de labios blancos (*Tayassu pecari*), Ultimate Ungulate (que cita a Mayer y
Wetzel 1987, *Mammalian Species* 293) da: HB 90–139 cm, cruz ≈ 45–60 cm, masa 25–40 kg y
cola 3–6 cm.

## Objetivos (adulto, malla base)

| clave en params.json | objetivo | rango aceptado | origen y razonamiento |
|---|---:|---|---|
| `hb_length` | 0,900 m | ±5 % | Brief y fuentes 1–2: 0,80–1,05 m; 0,90 queda en el centro. |
| `withers_height` | 0,420 m | ±5 % | Brief y fuente 1: 0,30–0,50 m. A nivel de piel; con la crin, ~0,45 m aparentes. |
| `head_length` | 0,230 m | ±5 % | Cráneo de 211–237 mm (fuentes 4–5) más ~1 cm de disco nasal y piel nucal. Es el 25,5 % de HB, dentro del 24–27 % del brief. |
| `head_hb_ratio` | 0,255 | ±5 % | Brief: 24–27 %. |
| `ear_length` | 0,075 m | ±5 % | Brief: 7–8 cm (no encontré una medida publicada). |
| `hind_foot` | 0,210 m | ±5 % | Fuente 2. Se mide de la tuberosidad calcánea a la punta de la pezuña. Fija la altura del corvejón (~0,15–0,17 m). |
| `head_width` | 0,115 m | ±5 % | Ancho cigomático de 105 mm (fuente 5) más maseteros y piel. |
| `mass_kg` | 22 kg | ±25 % | Brief y fuente 3. Control: volumen de la unión de mallas × 1000 kg/m³. |
| `croup_height` | 0,405 m | ±5 % | Diseño. El pecarí carga la masa adelante: la grupa queda algo por debajo de la cruz y cae hacia la cola. |
| `chest_depth` | 0,225 m | ±5 % | Diseño. Cruz − esternón; con eso la altura libre bajo el pecho queda en ~45 % de la cruz (patas cortas). |
| `belly_clearance` | 0,190 m | ±5 % | Diseño. Punto más bajo de la línea ventral entre manos y patas. |
| `body_width` | 0,215 m | ±5 % | Diseño. El pecarí es más estrecho que un cerdo; el tronco es algo más alto que ancho. |
| `disc_width` | 0,046 m | ±5 % | Diseño, a partir de fotos: el rinario es un disco ancho, más ancho que alto. |
| `eye_diameter` | 0,017 m | ±5 % | Diseño. Ojo pequeño. |
| `canine_exposed` | 0,013 m | ±10 % | Diseño. Con la boca cerrada asoma solo la punta del canino superior, recta hacia abajo. |
| cola | — | — | Vestigial (12–45 mm) y oculta en el pelo: **no se modela**. |

## Cómo se mide cada valor sobre la malla (`build_pecari.py → measure()`)

- **Punta del hocico**: centroide de los vértices de la cara frontal del disco nasal (los más
  adelantados a lo largo del eje de la cabeza).
- **Punto nucal**: vértice de la línea media de `Pecari_Head` más cercano al hito `nuchal_world`
  (cresta occipital).
- **Base de la cola**: vértice de la línea media del cuerpo más cercano al hito `tail_base`.
- **HB** = |hocico − nucal| + |nucal − base de la cola|, que equivale a la medida con la cabeza
  extendida en línea con el cuerpo, como se toma en campo.
- **Largo de cabeza** = |hocico − nucal|.
- **Cruz** = Z máxima del cuerpo en una franja de ±2 cm alrededor de `withers_y`. **Grupa** =
  lo mismo en `croup_y`.
- **Profundidad del pecho** = Z máxima − Z mínima de la línea media a la altura de la cruz.
- **Altura libre** = Z mínima de la línea media ventral entre `front_leg_y` + 5 cm y
  `hind_leg_y` − 5 cm.
- **Ancho del cuerpo** = 2·|x| máximo del cuerpo por encima de Z = 0,26 m. Incluye los muslos.
- **Ancho de cabeza** = 2·|x| máximo de cabeza y mandíbula.
- **Oreja** = distancia de la punta de la oreja al punto donde su eje corta la superficie de la
  cabeza (rayo sobre `Pecari_Head`).
- **Pie trasero** = vértice más posterior del corvejón izquierdo (tuberosidad calcánea) → vértice
  más adelantado del casco trasero izquierdo (por debajo de 12 mm de altura).
- **Canino expuesto** = distancia de la punta del canino a la superficie del labio, a lo largo
  de su eje.
- **Masa** = volumen de la **unión** de todas las mallas (volumen exacto del cuerpo más un
  Monte Carlo de 40 000 puntos para las piezas que lo solapan) × 1000 kg/m³.
