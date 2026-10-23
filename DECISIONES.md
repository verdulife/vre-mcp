# Registro de decisiones — VRE

Documento vivo. Cada decisión con su motivo y con qué la invalidaría. Fecha de arranque: 23/10/26.

## 0. Regla de trabajo

**No se construye nada —código, scaffolding, configuración, ficheros, commits— sin pedido
explícito en ese paso.** Diseño y discusión no son autorización.

Cadencia acordada: Verdu pide → propongo/diseño → aprueba → construyo → **él prueba** → él decide
el siguiente paso. Un hito no lo cierro yo.

## 1. Alcance

- Reconstrucción desde cero. La implementación anterior se borró del árbol de trabajo el 23/10/26;
  su historia vive en la rama `feature/vre` (commit `57a9bbb`) y se consulta con
  `git show feature/vre:<ruta>`, `git grep <patrón> feature/vre` o un `git worktree`.
- **Archivo congelado:** `feature/vre` está publicada en `origin`. No recibe cambios, el rebuild no
  la extiende y no es la rama por defecto (`from-zero` lo es). Existe para que "reconstruido desde
  cero" sea verificable y para conservar la especificación original
  (`visual-reference-engine-mvp.md`), las descomposiciones de referencias y los tests antiguos.
  Sus commits están firmados con `verdu@local`, así que no se vinculan a la cuenta de GitHub.
- Núcleo mínimo, en este orden: **buscar** referencias reales → **ver** la imagen → **guardar** lo
  elegido. Todo lo demás se añade cuando un hito lo necesite.

## 2. Flujo objetivo

1. **Brief** del usuario ("cartel moderno de discoteca basado en tipografía").
2. **Optimización de término.** No una query larga y pulida: una idea + 2–3 variantes de atributo
   (técnica, época/estilo, formato) lanzadas en paralelo. Cada fuente indexa distinto.
3. **Búsqueda en paralelo** en varias fuentes (lista a definir por pruebas reales, no por intuición).
4. **Extracción** a JSON: URL de imagen + `alt`/`title` + fuente + dimensiones.
5. **Filtros de nivel 0 (gratis, antes de gastar visión):** la imagen existe y es imagen; lado corto
   mínimo; ratio; dedupe por URL normalizada + hash perceptual; **una imagen por proyecto**.
6. **Subagente de visión:** selecciona, no describe. Devuelve ids + motivo por código.
7. **Fichas completas** solo de los supervivientes.

## 3. Decisiones tomadas

### 3.1 Capas de fuente, por orden de coste/estabilidad

1. **Buscador de imágenes (API)** — descubrimiento, cobertura amplia, cero fragilidad.
2. **Endpoint JSON interno** de la plataforma — profundidad; se descubre una vez con navegador.
3. **Navegador headless** — resolver tamaño completo de una página, fuentes sin API ni índice,
   captura puntual. **Usarlo para descubrir el endpoint, no para hacer el trabajo.**
4. **Scraping de HTML clásico** — último recurso.

*Motivo:* medido, ver §4. *Invalida esta decisión:* que las fuentes interesantes no estén indexadas.

### 3.2 El navegador headless no evita anti-bot

Cloudflare/PerimeterX/Datadome apuntan precisamente a él (`navigator.webdriver`, huella TLS, canvas,
entropía de ratón). Cambia "parseo roto" por "403/desafío", y con *stealth* entra una carrera de
mantenimiento semanal. Su valor real es ejecutar JS y **capturar las respuestas JSON** de la página.

### 3.3 Cuota como techo, nunca como objetivo

"Sobreviven como máximo 5. Si solo 2 superan el listón, devuelve 2." Una cuota obligatoria hace que
el modelo rellene con descartes. Se exige además `faltan: "<por qué devuelve menos>"`.

### 3.4 Rúbrica con puertas eliminatorias antes que puntuación

1. Puertas: ¿es un cartel/diseño real? ¿la tipografía es el sujeto? ¿se lee el texto principal?
2. Solo los que pasan compiten entre sí (jerarquía, contraste, coherencia de estilo).

Un criterio citado ("usa taste-skill") es un puntero, no una rúbrica: se aplica distinto en cada
ejecución. La rúbrica se versiona (`v1`, `v2`) para que dos pasadas sean comparables.

### 3.5 Comparar, no juzgar en aislado

Selección anclada en la mejor del lote; el resto se mide contra ella. Evaluar 25 imágenes por
separado aprueba casi todo. Regla extra: **si dos imágenes son variantes del mismo proyecto,
sobrevive una**.

### 3.6 El que selecciona no redacta fichas

Solo una línea de justificación por imagen (≤15 palabras) más el motivo de descarte por código
(`no-encaja`, `baja-resolucion`, `duplicado`, `no-es-imagen`, `marca-de-agua`).

*Motivo:* atención dividida (filtrar exige dureza, describir exige generosidad), sesgo de
compromiso (lo que acaba de elogiar no lo descarta), y las fichas completas solo tienen sentido
sobre los supervivientes.

### 3.7 Presupuesto de imagen: revelación progresiva

| Nivel | Qué ve el modelo | Coste |
| --- | --- | --- |
| 0 | Metadatos en texto: dimensiones, ratio, colores, procedencia | ~0 tokens de imagen |
| 1 | 25 candidatos individuales a ~768 px, **dentro de un subagente** | ~10k tokens, aislados del padre |
| 2 | 2–3 finalistas a ~1.500 px | ~1–1,5k cada uno |

- **No se reduce la resolución de los finalistas:** el brief es tipográfico y la señal está en el
  detalle (familia, jerarquía, tracking, legibilidad). Un thumbnail destruye justo lo que se busca.
- La hoja de contactos 3×3 queda descartada: su única ventaja era abaratar el triaje cuando el coste
  caía en el contexto del padre; con el triaje en un subagente, 25 imágenes individuales son mejores.
- El coste real no es el de una llamada: las imágenes en contexto se releen en cada turno posterior.

### 3.8 `alt`/`title` son pista, no criterio

Suelen estar vacíos o ser SEO repetido. Sirven para descartar obviedades sin coste; la decisión la
toma la visión.

### 3.9 El ratio es un discriminador gratis

1.91:1 / 2:1 = tarjeta social, no la obra. 0.71 = cartel real. Filtrar por ratio antes de la visión
es una línea de código.

### 3.10 Stack recomendado (pendiente de confirmación)

**TypeScript + Bun.** Motivo: el trabajo que no se acaba es el scraping, y es el stack que Verdu
mantiene a diario; `fetch` nativo, cheerio/linkedom, `sharp` para imagen, **`bun:sqlite` incluido**
(sin dependencia nativa de SQLite), `bun test` dentro, y `bun build --compile` como salida a binario
único si algún día viaja.

- **Cambia a Python** si el trabajo de imagen pesa más que el de scraping (numpy/OpenCV/Pillow).
- **Cambia a Go** si el binario debe correr en máquinas ajenas sin runtime (como engram).
- Rust solo si se volviera un servicio con rendimiento crítico: no es el caso.
- Dato no opinable: si entra el navegador headless, se entra por **Playwright**, que solo tiene
  bindings oficiales para TS/JS, Python, Java y .NET. Ni Go ni Rust.

### 3.11 Verificación por hito

Prueba real ejecutada y observada, no suite simulada. En esta máquina no hay pytest instalado.
El juicio final del hito es de Verdu.

## 4. Evidencia medida — 23/10/26

Prueba desechable de recuperación (carpeta `search-test/`, script `fetch.py`): búsqueda web →
`og:image` → descarga → validación con Pillow (lado corto ≥600 px, área ≥300k) → una imagen por
proyecto. Sin navegador, sin API de imágenes, sin dependencias nuevas.

| Página | HTTP | Resultado |
| --- | --- | --- |
| overmind.design | 200 | imagen usada (1200×1698, ratio 0.71) |
| fontsinuse.com | 200 | imagen usada (1760×880, ratio 2.00) |
| vasa.works | 200 | imagen usada (1200×630, ratio 1.90) |
| andrealiang.com | 200 | imagen usada (903×904, ratio 1.00) |
| chkdesign.com | 200 | imagen usada (1925×1284, ratio 1.50) |
| dribbble.com ×3 | **202** | muro anti-bot |
| behance.net ×2 | **403** | muro anti-bot |
| otaviosantiago.com (Wix) | 200 | sin imagen usable: sirvió recortes 2000×380 y 910×173 |

**Conclusiones:** (a) la capa barata consigue imágenes, no siempre la obra — dos de cinco eran
tarjetas sociales; (b) los muros anti-bot caen justo en las fuentes que más interesan para este
brief; (c) los CDN de imagen no dieron problema; (d) el ratio separa tarjeta social de cartel sin
coste.

## 5. Abierto

1. **Modelo de visión sin fijar** — bloquea la medición real de tokens (3 tamaños × modelo → `usage`).
2. **Pinterest** sin probar.
3. **Endpoints JSON** de Behance/Dribbble sin explorar.
4. **Cuota por fuente** (5 por fuente es un punto de partida arbitrario): se mide tras el dedupe.
5. **`taste-skill`**: en el registro de skills de la sesión no existe; hace falta su ruta para
   ajustar la rúbrica a lo que realmente define.
6. **Stack**: confirmación pendiente (§3.10).
7. **Repo sin remoto**: no hay destino de push configurado.
