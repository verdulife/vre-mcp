# Descomposición de referencia — «Improve, all ways.»

- **Referencia guardada**: `ref_bd57832e6b` (elegida por el usuario) · candidato `cand_59e7499ad06f`
- **Origen**: https://www.blushpublishing.co.uk/blog/3800-embossed-business-cards
- **Imagen analizada**: `https://images.squarespace-cdn.com/content/615afc37a1a29b0da532c7c7/1726587410831-S44RD9AL3XZLXSDBOA6K/20240913-IMG_0793.jpg?format=1500w&content-type=image%2Fjpeg`
- **Archivo local**: `data/references/tarjetas-visita-mcp/04-blind-embossed-letterpress-printed-busin.jpg`
- **Destino**: reconstrucción en FigCraft (aproximación en pantalla; el relieve real es de imprenta)

Etiquetas usadas: **[OBS]** visto en la imagen · **[INF]** inferencia mía · **[FALTA]** dato que la imagen no puede dar.

---

## 1. Qué es la pieza

Tarjeta de visita impresa en cartulina clara, **sin tinta**: todo el mensaje es una sola frase en
relieve (*blind emboss*). No hay logotipo, ni nombre, ni datos de contacto visibles en esta cara.
**[OBS]**

## 2. Artefacto vs. contexto

| Se conserva (artefacto) | Se descarta (contexto del mockup) |
| --- | --- |
| Tarjeta rectangular clara, proporción horizontal | Papel naranja sobre el que está apoyada |
| Una línea de texto en relieve, centrada | Superficie gris-azul del fondo |
| Textura de cartulina sin estucar | Sombra dura diagonal y dirección de la luz |
| Ausencia total de tinta | Ángulo de cámara y perspectiva |
| Espacio negativo dominante | Grano, motas de polvo y fibras del entorno |

La luz lateral solo se usa como **evidencia del relieve**; no forma parte del diseño. **[OBS]**

## 3. Geometría

- Proporción observada ≈ **1,5:1 horizontal**, compatible con el estándar 85 × 55 mm; no se puede
  medir con exactitud por la perspectiva. **[OBS]/[INF]**
- Bordes rectos, esquinas vivas, sin radio visible. **[OBS]**
- Un solo elemento gráfico: la línea de texto. Sin filetes, marcos ni fondos parciales. **[OBS]**

## 4. Composición

- Una única línea, **centrada horizontalmente**, situada ligeramente por debajo del centro óptico. **[OBS]**
- La línea ocupa aproximadamente **el 45–55 % del ancho** de la tarjeta. **[INF]** (medido a ojo sobre la foto)
- Márgenes laterales amplios y muy similares entre sí; el aire es el elemento compositivo principal. **[OBS]**
- Sin ningún otro nivel de jerarquía: no hay titular + apoyo, solo una frase. **[OBS]**

## 5. Tipografía

- **Clase**: serif de transición/old-style, contraste medio, remates finos; no es una didona ni una slab. **[OBS]**
- **Caja**: mayúscula inicial + minúsculas («Improve, all ways.»), con coma y **punto final**. **[OBS]**
- **Peso**: regular; la fuerza viene del relieve, no del grosor. **[OBS]**
- **Tracking**: normal o ligeramente cerrado; sin espaciado de versalitas. **[OBS]**
- **Interlineado**: una sola línea, no aplica. **[OBS]**
- **Cuerpo**: pequeño respecto a la tarjeta (la frase es legible, no protagonista por tamaño). **[OBS]**
- **Familia exacta**: no identificable con certeza a esta resolución. **[FALTA]**
  Candidatas libres para reconstruir: *Source Serif 4*, *Spectral*, *EB Garamond*. **[INF]**

## 6. Color

- Cartulina: crema cálido, aprox. **#F2EEE3** en la zona iluminada; **#DCD5C5** en la zona en sombra. **[INF]**
  Son valores de la **foto**, no del material: la luz cálida altera el valor real. No usar como color de marca.
- Texto: **mismo color que el soporte** (sin tinta). La legibilidad viene del relieve y su sombra. **[OBS]**
- Paleta funcional: un solo color + su sombra. Nada más. **[OBS]**

## 7. Acabado

- **Blind emboss**: hueco/relieve sin tinta ni foil, con borde suave y sombra en el lado opuesto a la luz. **[OBS]**
- Papel sin estucar, con fibra visible; gramaje alto (la pieza no se comba). **[OBS]/[INF]**
- Sin barniz, sin foil, sin troquel. **[OBS]**

## 8. Lo que la imagen no dice

- Reverso de la tarjeta. **[FALTA]**
- Medidas exactas, gramaje, profundidad del relieve, imprenta. **[FALTA]**
- Si la frase es el mensaje principal o un complemento de una marca en el reverso. **[FALTA]**

## 9. Reconstrucción en FigCraft

FigCraft trabaja con frames, auto layout, componentes, variables y sombras; el relieve se aproxima,
no se reproduce. Plan concreto:

1. **Frame** `card/front` de 85 × 55 mm a escala de impresión: 1004 × 650 px a 300 ppp
   (1 mm ≈ 11,811 px). Fondo `color/stock-01` = `#F2EEE3`.
2. **Texto**: una capa, fuente serif candidata, `tracking` 0, color = `color/stock-01` (idéntico al fondo),
   centrada con auto layout (padding lateral ≈ 22 % del ancho, vertical ≈ 46 % de la altura).
3. **Relieve simulado**: duplicar la capa de texto sobre el original. A la copia: sombra interior
   (`inner shadow`) desplazada 0,5 px hacia abajo-derecha, desenfoque 1 px, color `#C9C1AE` al 55 %;
   y una segunda sombra clara 0,5 px arriba-izquierda `#FFFFFF` al 40 %. Esto imita el hueco; en
   impresión real no existe.
4. **Estilos y variables**: `type/statement` (familia, cuerpo, tracking, color), `color/stock-01`,
   `color/emboss-shadow`, `color/emboss-light`. Un componente `card/front` con la variante `text` para
   poder sustituir la frase por tu logotipo o tu claim.
5. **Frame** `card/back` (opcional, a decidir): nombre y doble oficio, misma retícula y márgenes,
   sin añadir acabados nuevos.
6. **Export**: el frame es una **aproximación de pantalla**. Para imprimir hay que llevar medidas,
   color y relieve al archivo del impresor; FigCraft no gestiona CMYK ni hendido.

## 10. Checklist de fidelidad

- [ ] Proporción 85 × 55 mm exacta en el frame.
- [ ] Una sola línea, centrada, al 45–55 % del ancho.
- [ ] Texto del mismo color que el fondo (sin tinta).
- [ ] Margen lateral amplio y simétrico; nada más en la cara.
- [ ] Ausencia de cualquier elemento del mockup (papel naranja, fondo gris, sombra, polvo).
- [ ] El relieve es un efecto de pantalla: no confundirlo con el acabado real.
