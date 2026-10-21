# Tarjeta de visita — especificación híbrida (dirección elegida)

- **Referencias**: `ref_bd57832e6b` (frase-manifiesto en relieve) + `cand_b177ae1b8628` (nombre en versales espaciadas)
- **Descomposiciones**: `01-polly-james-decomposition.md`, `02-improve-all-ways-decomposition.md`
- **Objetivo**: tarjeta de visita de dos caras para un diseñador gráfico y desarrollador frontend con logotipo propio
- **Herramienta de reconstrucción**: FigCraft (aproximación en pantalla) + archivo para imprenta
- **Estado**: lista para construir; bloqueada por los datos marcados `[FALTA]`

Etiquetas: **[DEC]** decisión tomada · **[OBS]** visto en las referencias · **[INF]** inferencia mía · **[FALTA]** dato que necesito de ti

---

## 1. Dirección

Híbrido de las dos referencias: la **disciplina del anverso de Polly James** (una sola cosa, relieve, aire)
y la **idea de manifiesto de «Improve, all ways.»** sin frases genéricas: el mensaje es el oficio. **[DEC]**

| Cara | Contenido | Carácter |
| --- | --- | --- |
| Anverso | Logotipo en *blind emboss*, centrado | Silencio, material, identidad |
| Reverso | Una línea en versales espaciadas: oficio · dominio · ciudad | Información mínima, misma tipografía |

Nada de tinta en el anverso. El reverso es la única concesión informativa. **[DEC]**

## 2. Geometría y producción

| Parámetro | Valor | Etiqueta |
| --- | --- | --- |
| Formato | 85 × 55 mm, horizontal, dos caras | [DEC] |
| Frame FigCraft | 1004 × 650 px (300 ppp, 1 mm ≈ 11,811 px) | [DEC] |
| Sangrado | 3 mm por lado (35 × 55 → 91 × 61 mm con sangrado) | [DEC] |
| Cartulina | Algodón sin estucar, 600 g/m² aprox., tono crema cálido | [DEC]/[INF] |
| Acabado | Blind emboss (relieve sin tinta ni foil) en anverso; reverso a decidir | [DEC] |
| Color de material | `#F2EEE3` referencia de pantalla (valor de foto, no de muestra física) | [INF] |
| Troquel de relieve | Sí, una plancha; profundidad a definir con imprenta | [DEC] |

## 3. Anverso

- **Único elemento**: logotipo, centrado en ambos ejes, sin texto añadido. **[DEC]**
- **Tamaño**: el logotipo debe ocupar el **40–50 % del ancho** de la tarjeta como máximo, con margen
  de seguridad mínimo de 10 mm por lado. **[DEC]/[INF]**
- **Relieve**: sin tinta; legibilidad por sombra del hueco, no por color. **[OBS]** (referencias 01 y 02)
- **Versión del logotipo**: debe funcionar en una tinta y en relieve — si el logotipo depende de dos
  colores o de detalles finos, esta dirección lo rompe. **[FALTA]** confirmar con el SVG.
- **Prohibido en el anverso**: nombre, cargo, teléfono, QR, filetes, marcos, fondo de color. **[DEC]**

## 4. Reverso

Una sola línea, dos niveles como máximo:

```
DISEÑO GRÁFICO + FRONTEND     ·     tudominio.dev     ·     Barcelona
```

- **Versales con tracking amplio**, mismo tono que el material (relieve) o una tinta muy baja. **[DEC]**
- Alineación centrada, misma retícula y márgenes que el anverso: la pieza se lee como un sistema. **[DEC]**
- Alternativa a decidir: sustituir «diseño gráfico + frontend» por dos líneas (oficio / disciplinas)
  si la versión de una línea queda demasiado larga. **[FALTA]** texto exacto.

## 5. Tipografía

- **Clase**: serif editorial de contraste medio, la misma familia en las dos caras. **[DEC]**
- **Familia**: no identificable en las referencias. **[FALTA]**
  Candidatas libres para FigCraft: *Source Serif 4* (eje variable), *Spectral*, *EB Garamond*. **[INF]**
- **Estilos**: `type/wordmark` (logotipo), `type/role-line` (versalitas, tracking +8 %), `type/data`
  (dominio y ciudad, mismo cuerpo que role-line). **[DEC]**
- **Nada de negritas**: el relieve ya da cuerpo. **[OBS]**

## 6. Reconstrucción en FigCraft

1. **Variables**: `color/stock-01` `#F2EEE3`, `color/emboss-shadow` `#C9C1AE`, `color/emboss-light` `#FFFFFF`.
2. **Frames**: `card/front` 1004×650, `card/back` 1004×650, más `print/front-bleed` 1075×720 (91×61 mm).
3. **Componente** `card/front`, variante `logo` con la instancia del SVG en relieve:
   - capa del logotipo con relleno = `color/stock-01`;
   - capa duplicada con `inner shadow` 0,5 px abajo-derecha (`color/emboss-shadow` 50 %) y
     highlight 0,5 px arriba-izquierda (`color/emboss-light` 35 %).
4. **Componente** `card/back`, auto layout vertical centrado, padding 10 mm, `role-line` + `data`.
5. **Nada de sombras de tarjeta ni fondos de escena**: el frame es la pieza, no un mockup. **[DEC]**
6. **Export**: PNG 300 ppp para revisión; para imprimir, entregar al impresor medidas, sangrado y
   especificación de relieve. FigCraft no gestiona CMYK ni hendido: el efecto de pantalla es solo
   una vista previa.

## 7. Datos que necesito para cerrar la pieza
- `[FALTA]` **SVG o PNG del logotipo** (idealmente monocromo, con versión simplificada).
- `[FALTA]` **texto exacto del reverso**: cómo nombras el doble oficio, dominio y ciudad.
- `[FALTA]` ¿Reverso también en relieve o impreso en una tinta?
- `[FALTA]` Presupuesto de impresión: ¿hay troquel de relieve y papel de algodón, o debe resolverse
  con impresión digital estándar?

## 8. Criterios de aceptación

- [ ] Anverso: solo el logotipo, centrado, en relieve, sin tinta.
- [ ] Reverso: una línea legible a 30 cm, sin más elementos que oficio, dominio y ciudad.
- [ ] Ambas caras comparten retícula, márgenes y familia tipográfica.
- [ ] El logotipo se reconoce a tamaño real (55 mm de ancho) y en una sola tinta.
- [ ] El archivo de imprenta incluye 3 mm de sangrado y la especificación de relieve.
- [ ] Nada del mockup original sobrevive en la pieza final: ni fondo, ni sombra, ni perspectiva.
