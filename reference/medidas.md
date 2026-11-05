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

Desde la etapa 2 la tolerancia es de **±8 %** (masa ±25 %). Los objetivos de origen bibliográfico
(HB, cruz, cabeza, oreja, pie trasero y masa) **no se cambiaron**. Solo se revisaron dos objetivos
de diseño que en la etapa 1 eran estimaciones propias sin fuente, a partir de la foto lateral que
proporcionó el usuario.

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
| `croup_height` | 0,430 m | ±8 % | Diseño. Etapa 1: 0,405 (masa adelante). **Etapa 2: 0,430**: en la foto lateral la grupa queda casi a la altura del lomo y cae redondeada hacia la cola. |
| `chest_depth` | 0,225 m | ±5 % | Diseño. Cruz − esternón; con eso la altura libre bajo el pecho queda en ~45 % de la cruz (patas cortas). |
| `belly_clearance` | 0,225 m | ±8 % | Diseño. Etapa 1: 0,190 (~45 % de la cruz, sin fuente). **Etapa 2: 0,225**: en la foto lateral, a la escala alineada, los flecos del vientre llegan a ~0,20 m y con 3,5 cm de pelo la piel queda en ~0,23 m. |
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

## Etapa 2b — Proporciones a partir de fotos reales

El usuario aportó dos fotos **reales** (`reference/real_side_walking.jpg` y
`reference/real_side_walking_head_low.jpg`). Las dos muestran al animal al paso, de perfil. Las
tres vistas de la etapa 2 (lateral, frontal, 3/4) y el esqueleto son **generadas por IA**: sirven
para el aspecto general y los rasgos cualitativos, no para proporciones ni tamaños.

**Método**:
- Puntos anotados a mano (`reference/ref_landmarks.json`): centro del disco nasal, punto nucal
  (dorso de la cabeza detrás de las orejas), base de la cola, tope de la capa densa en la cruz
  (sin contar las cerdas erizadas de la crin), borde inferior del vientre, corvejón y suelo.
- A todo lo medido sobre el pelo se le restan 1,5 cm de pelaje.
- La escala sale de suponer HB = 0,90 m; los cocientes no dependen de ese valor.
- Cálculo en `reference/real_photo_proportions.json`.

| cociente (a nivel de piel) | foto real 1 (cabeza alta) | foto real 2 (cabeza baja) | media | imágenes IA | bibliografía |
|---|---:|---:|---:|---:|---:|
| HB / cruz | 2,07 | 2,13 | **2,10** | ~1,55 | ~2,1 (HB 75–100 cm, cruz 30–51 cm) |
| largo total horizontal / cruz | 1,94 | 1,69 (cabeza baja) | — | — | — |
| cabeza / HB | 0,335 | 0,329 | **0,33** | ~0,39 | 0,24–0,27 (brief) |
| vientre / cruz | 0,37 | 0,44 | **0,41** | 0,39 | — |
| corvejón / cruz | 0,28 | 0,31 | **0,29** | — | — |
| lomo medio / cruz | 0,99 | 1,08 | 1,04 (lomo arqueado) | — | — |

**Conclusiones** (las fotos reales mandan sobre las proporciones; la bibliografía, sobre los
tamaños):
1. **Largo/alto**: las fotos reales confirman la bibliografía (HB/cruz ≈ 2,1). El 1,55 de las
   imágenes IA es un artefacto del generador (cuerpo demasiado alto y compacto), y la regla del
   "punto medio" entre 1,55 y 2,1 (≈ 1,83) queda **sustituida** por la medida real.
   - Con HB = 0,90 m (centro del rango bibliográfico), cruz = 0,90 / 2,1 = **0,43 m**, dentro de
     30–51 cm.
   - Masa: el volumen debe dar 22 kg ±25 % (16,5–27,5 kg), dentro del rango real de 15–30 kg.
2. **Cabeza/cuerpo**: las fotos reales dan 0,33. Es mayor que el 24–27 % del brief porque la cabeza
   externa incluye el disco nasal (~2 cm por delante de los incisivos) y el tejido nucal detrás
   del cráneo de 211–237 mm. Esa suma anatómica da ~0,25–0,27 m (0,28–0,30 de HB). Se adopta
   **cabeza/HB = 0,32** (las fotos, algo moderadas porque el punto nucal se marca sobre la crin)
   → **largo de cabeza = 0,285 m**.
   - Las imágenes IA exageran aún más la cabeza (0,39); no se siguen.
3. **Altura libre bajo el vientre**: el 0,225 m de la etapa 2 venía de calibrar la escala sobre
   una imagen IA. Con las fotos reales (vientre/cruz 0,37–0,44) y la indicación del usuario
   (40–44 %), se adopta **0,41 × 0,43 = 0,178 m**. Patas más cortas.
4. **Corvejón**: en las fotos reales queda a ~0,29 de la cruz; en la v09 estaba a ~0,40 (patas de
   ciervo). Se baja a 0,155 m (0,36 de la cruz). No baja más porque el pie estirado de 210 mm
   (punto 5) necesita esa longitud entre el talón y la punta de la pezuña: con el corvejón a
   0,29 de la cruz el pie mediría ~170 mm (−19 %).
5. **Pie trasero**: los 210 mm de la fuente 2 son una medida de mastozoología tomada con el pie
   **estirado** (del talón a la punta de la pezuña). Con el corvejón bajo y el metatarso casi
   vertical, la cuerda talón–punta en pose de pie no puede compararse con esa cifra.
   - Desde la etapa 2b se mide como **longitud del pie estirado**: talón (malla) → centro del
     menudillo → punta de la pezuña (malla).
6. **Grupa**: ~0,965 de la cruz → **0,415 m**. **Pecho**: cruz − esternón ≈ **0,25 m**.
7. **Ancho de cabeza**: con una cabeza mayor y "cráneo y mejillas más anchos", se adopta
   **0,13 m** (arco cigomático de 105 mm + ~12 mm de masetero y piel por lado). Disco nasal
   "grande": **0,050 m**.

Objetivos vigentes desde la etapa 2b (tolerancia ±8 %; masa ±25 %):

| clave | etapa 2 | **etapa 2b** | origen |
|---|---:|---:|---|
| `hb_length` | 0,900 | 0,900 | bibliografía |
| `withers_height` | 0,420 | **0,430** | HB/cruz = 2,1 (fotos reales = bibliografía) |
| `head_length` | 0,230 | **0,285** | cabeza/HB = 0,32 (fotos reales) |
| `head_hb_ratio` | 0,255 | **0,320** | fotos reales |
| `belly_clearance` | 0,225 | **0,178** | vientre/cruz = 0,41 (fotos reales; 40–44 % pedido) |
| `chest_depth` | 0,225 | **0,250** | cruz − esternón |
| `croup_height` | 0,430 | **0,415** | grupa/cruz ≈ 0,965 (fotos reales) |
| `head_width` | 0,115 | **0,130** | cigomático + tejidos blandos |
| `disc_width` | 0,046 | **0,050** | disco grande |
| `hind_foot` | 0,210 (cuerda de pie) | 0,210 (**pie estirado**) | fuente 2 |
| `ear_length`, `body_width`, `eye_diameter`, `canine_exposed`, `mass_kg` | sin cambios | sin cambios | |

**Resultado v12** (malla, sin pelo): HB 0,914 m, cruz 0,426 m (HB/cruz 2,15), cabeza 0,301 m
(cabeza/HB 0,33), altura libre 0,167 m (39 % de la cruz), corvejón 0,155 m, masa 22,2 kg. Todo
dentro de ±8 % y dentro de los rangos de la bibliografía (HB 75–100 cm, cruz 30–51 cm, 15–30 kg).
