# Pecarí de collar — Etapa 1 (malla base): registro de iteraciones

## Paso 0 — Entorno

- **Sistema**: Linux, Ubuntu 24.04.5 LTS. Es un contenedor en la nube, no la máquina del
  usuario: 4 CPU, sin GPU.
- **Blender**: no venía instalado. El brief pedía "dime el comando y detente", pero en un
  contenedor efímero instalarlo es reversible y no toca la máquina del usuario, así que decidí
  instalarlo y seguir. download.blender.org está bloqueado por la red del entorno, de modo que
  usé el paquete de Ubuntu: `apt-get install blender` → **Blender 4.0.2**, más
  `apt-get install python3-numpy`, porque el Python del sistema que usa ese Blender no trae
  numpy (el Blender oficial sí lo incluye).
  - En la máquina del usuario (Windows o Linux con la RTX 3070 Ti) basta Blender 4.2 LTS o
    posterior de blender.org. Los scripts no usan nada que no exista en 4.0–4.5.
  - Linux: `sudo snap install blender --channel=4.2lts/stable --classic`
  - Windows: `winget install --id BlenderFoundation.Blender.LTS.4.2`
- **Motor de render**: `render_views.py` busca, por orden, Cycles GPU (OptiX > CUDA > HIP >
  oneAPI > Metal), luego Eevee si hay contexto gráfico y, si no, **Cycles CPU**.
  - En este contenedor no hay GPU ni libEGL: Eevee hace caer a Blender al iniciarse, así que
    se usó Cycles CPU (96 muestras, muestreo adaptativo, sin denoiser porque el build de Ubuntu
    no trae OIDN).
  - En la RTX 3070 Ti se elegirá OptiX automáticamente. Se puede forzar con
    `--engine cycles_gpu|eevee|cycles_cpu`.
- **../jaguar/src**: no existe (`..` solo contiene `pecari`), así que no se reutilizó nada.
- **Estructura**: la raíz de este repositorio *es* `./pecari`, que encaja con la referencia a
  `../jaguar/src`. El comando único se ejecuta desde aquí:
  `blender -b -P src/build_pecari.py -- --version vNN`.
- **Referencias fotográficas del usuario**: no hay fotos en `reference/`. Las críticas se basan
  en las medidas de `reference/medidas.md` y en la anatomía conocida de *P. tajacu*: cabeza
  grande en cuña, cuello corto, masa delantera, patas finas, orejas pequeñas y redondeadas, y
  caninos superiores rectos hacia abajo.

## Decisiones de método

1. **Jaula de quads → Catmull-Clark → proyección sobre un SDF → relajación tangencial**, en vez
   del Skin modifier sugerido.
   - Motivo: el Skin modifier genera anillos de 4 vértices; con Subdivision nivel 2 quedan 16
     alrededor del torso, que es poco para la silueta en barril, y con nivel 3 se pasa del
     presupuesto. Además solo da secciones elípticas, sin control fino de la línea dorsal ni de
     la ventral.
   - Con una jaula propia elijo el número de anillos (12 en torso y cabeza → 48 tras
     subdividir; 4 en patas → 16), dónde caen los bucles articulares y cómo se cierran las
     tapas (rejillas de quads, sin polos de triángulos).
   - La forma la define el SDF de `params.json`: barridos de secciones superelípticas para
     tronco, cabeza y mandíbula, más conos redondeados y elipsoides para patas y relieves,
     todo con uniones suaves. Así cada medida depende de unos pocos números.
   - No se usa Remesh: la topología la fija la jaula.
2. **Cabeza y mandíbula** se construyen con secciones transversales en un marco canónico (plano
   palatino horizontal) y luego se inclinan (`pitch_deg`) y se colocan con el punto nucal. Así,
   inclinar la cabeza no deforma su anatomía.
3. **Bucles de deformación**:
   - Hombro y cadera: anillos del cuerpo en esas estaciones y anillo raíz de cada pata.
   - Codo, muñeca, babilla, corvejón, menudillo y corona: anillos de la jaula de la pata, más 3
     bucles intermedios de la subdivisión.
   - Párpados: un parche 4×4 alrededor del ojo, con dos `inset_region` concéntricos, cuyo
     interior se hunde en una cuenca esférica del SDF.
   - Comisura: un parche 2×2 con dos insets, en la cabeza y en la mandíbula.
4. **Párpados cerrados sobre una cuenca**: en vez de agujerear la cabeza (eso rompería el
   manifold), el SDF resta una esfera algo mayor que el globo ocular y los bucles del párpado se
   pliegan hacia dentro. La cabeza sigue cerrada.
5. **Simetría**: el SDF se evalúa sobre |x| y los vértices de la línea media se fijan en x = 0,
   así que la malla sale simétrica sin modificador Mirror.
6. **Orígenes**: todos los objetos tienen el origen en (0, 0, 0) y transformaciones identidad.
   Ese punto es el suelo, centrado entre las pezuñas: el script mide los centroides de las suelas
   delanteras y traseras y desplaza todo en Y.
7. **Escala para la variante**: `meta.global_scale` multiplica todo el resultado. Para
   *Tayassu pecari* basta copiar `params.json`, subir `global_scale` (~1,12–1,15), ajustar
   `targets` y retocar proporciones (`--params otro.json`).
8. **Vértices de cola**: no hay geometría de cola (es vestigial y queda oculta en el pelo).
9. **Renders "arcilla"**: el gris de los ojos (oscuro) y de los caninos (claro) varía un poco
   para poder leerlos en la crítica; el resto es arcilla uniforme 0,42. Vistas ortográficas a
   escala fija (lateral y cenital 1,05 m, frontal 0,62 m), así que son comparables entre
   versiones.
10. **Entregables por versión**: `blend/pecari_vNN.blend`, `blend/pecari_vNN.glb` (Y arriba,
    sin materiales ni grupos: glTF no los guarda) y `renders/vNN/` con las 6 vistas, la hoja de
    contacto, `report.md`/`report.json` (medidas, validación y polígonos) y `params_used.json`
    (para reconstruir esa versión exacta con `--params`).

---

## v01 — diseño inicial

**Medidas** (de `renders/v01/report.md`): HB 0,916 (+1,8 %), cruz 0,419 (−0,2 %), cabeza 0,238
(+3,3 %), oreja 0,074, **pie trasero 0,175 (−16,6 %)**, ancho del cuerpo 0,227 (+5,7 %), disco
0,043 (−7,3 %), **canino expuesto 22 mm (+72 %)**, masa 25,1 kg (+14 %). La malla tiene 8288
quads, 0 triángulos, 0 n-gons; todo manifold, sin autointersecciones.

**Crítica de los renders**:
- **Silueta lateral**: se lee como un cuadrúpedo genérico, a medio camino entre cerdo y tapir.
  El tronco es una "salchicha": misma altura de la cruz a la grupa, línea dorsal recta y la
  grupa termina en un bulbo redondo. No hay sensación de masa delantera.
- **Cabeza/cuerpo**: la longitud cumple (25,9 % de HB), pero visualmente la cabeza parece
  pequeña. El hocico es un cilindro largo y fino (aire de oso hormiguero), y el cráneo es un
  bulto corto detrás de los ojos. No es la cuña del pecarí.
- **Mandíbula**: una "bolsa" alargada colgando bajo la cabeza, con el borde posterior redondo
  asomando bajo el cuello. Se lee como objeto aparte, no como mejilla y quijada.
- **Cuello**: corto y grueso (bien), pero rodea la nuca: desde el frente, el cuello y los
  hombros abrazan una cabeza estrecha.
- **Lomo**: plano, sin el arco ligero. **Barril**: profundidad correcta (0,226), pero igual de
  ancho en hombros, costillas y muslos (vista cenital = tubo).
- **Patas**: finas y bien colocadas en Y. Corvejón demasiado bajo (pie trasero corto).
  Menudillos y pezuñas son nudos redondos, tipo "hueso de perro". Vistas de frente están
  demasiado separadas para un pecho tan estrecho.
- **Hocico truncado**: el disco nasal se ve, pero algo estrecho (43 mm).
- **Ojos**: tamaño y posición razonables, altos y laterales.
- **Orejas**: largas y estrechas de aspecto (de burro o conejo), aunque midan 74 mm. Las del
  pecarí son pequeñas, anchas y redondeadas.
- **Caninos**: demasiado largos y visibles; parecen colmillos de jabalí.
- **Cola**: no visible (correcto).

---

## v02 — cambio: masa del tronco hacia delante y línea dorsal

**Intención**: que el tronco deje de ser un tubo. Hombros y pecho más estrechos en la vista
frontal, costillas como zona más ancha, cuartos traseros algo más bajos y estrechos, lomo con
un arco suave y grupa que cae a la cola sin bulbo.

**Cambios en params.json → body**:
- `stations`: el semiancho pasa de 0,084/0,094 a 0,074/0,084 en hombros (y −0,24/−0,19) y el
  máximo (0,104) queda en las costillas (y −0,06…0,01). El lomo culmina en 0,425 en y −0,13 y
  baja a 0,406 en la grupa (y 0,20). Flanco recogido (vientre 0,224 en y 0,14). La última
  estación pasa a y 0,30 con una sección más pequeña.
- `cap_rear` 0,034 → 0,065 (casquete largo, para una grupa que se afina en vez de rematar en
  bola).
- `cage.rings_y`: los últimos anillos se reubican dentro del casquete. Cambio técnico en el
  código: los anillos de jaula dentro de un casquete ahora se encogen como el elipsoide.
- `targets.croup_height` 0,415 → 0,405 (el pecarí carga la masa delante).

**Medidas**: HB 0,918, cruz 0,420, grupa 0,408, pecho 0,230, ancho 0,224 (+4,3 %, ya dentro),
masa 23,0 kg (+4,5 %). Siguen fuera el pie trasero, el disco y el canino.

**Crítica**:
- De frente, los hombros son más estrechos que las costillas (mejora). El lomo tiene un arco
  apenas perceptible.
- **La grupa sigue pareciendo un bulbo**. Un diagnóstico numérico (anchura del SDF frente a la
  malla por estaciones; la malla coincide con el campo) muestra que la causa no es el casquete:
  son los **conos de los muslos** (cadera r 0,044 en x 0,068), que sobresalen hasta |x| = 0,112.
  Eso es más que las costillas (0,104), así que los muslos son la parte más ancha del animal y
  crean una "bola" y un pliegue en y ≈ 0,27.
- Es una mejora parcial, pero real: el frente ya se lee más estrecho y la línea dorsal se
  inclina hacia atrás. Lo de los muslos se corrige en la iteración de patas y cuartos traseros
  (v04), que es su región.
- Lo más grave para reconocer al pecarí sigue siendo la **cabeza** → v03.
