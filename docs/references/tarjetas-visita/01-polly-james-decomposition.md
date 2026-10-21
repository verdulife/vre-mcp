# Descomposición de referencia — «Polly James» (blind embossed)

- **Referencia**: no guardada · candidato `cand_b177ae1b8628`
- **Origen**: https://www.blushpublishing.co.uk/blog/blind-embossed-business-cards
- **Imagen analizada**: `https://images.squarespace-cdn.com/content/615afc37a1a29b0da532c7c7/fd49bb6a-f1ab-4760-8a82-2fbc8a9485a1/20240906-IMG_0702.jpg?format=1500w&content-type=image%2Fjpeg`
- **Archivo local**: `data/references/tarjetas-visita-mcp/01-polly-james-blind-embossed-business-card.jpg`
- **Destino**: comparación con `02-improve-all-ways-decomposition.md` antes de reconstruir
- **Dirección elegida**: híbrido con esta referencia como base del anverso → `00-hybrid-card-spec.md`

Etiquetas: **[OBS]** visto en la imagen · **[INF]** inferencia mía · **[FALTA]** dato que la imagen no puede dar.

---

## 1. Qué es la pieza

Tarjeta clara con un único nombre propio —«POLLY JAMES»— en relieve, sin tinta, sin logotipo y sin
ningún otro dato. La pieza identifica; no informa. **[OBS]**

## 2. Artefacto vs. contexto

| Se conserva (artefacto) | Se descarta (contexto del mockup) |
| --- | --- |
| Tarjeta rectangular, proporción horizontal | Fondo gris con degradado |
| Nombre en versales espaciadas, relieve sin tinta | Sombra suave proyectada |
| Cartulina sin estucar con fibra visible | Inclinación y perspectiva de la cámara |
| Una sola línea, aire muy amplio | Bruma y viñeteado del objetivo |

## 3. Geometría

- Proporción ≈ **1,5:1** horizontal, coherente con 85 × 55 mm; no medible con exactitud por el ángulo. **[OBS]/[INF]**
- Bordes rectos, esquinas vivas, sin radio ni filete. **[OBS]**
- Ningún otro elemento: ni línea, ni bloque de color, ni marca. **[OBS]**

## 4. Composición

- Línea única **centrada**, ligeramente por debajo del centro óptico (mismo recurso que en la referencia 02). **[OBS]**
- Ancho de la línea ≈ **55–65 %** del ancho de la tarjeta. **[INF]**
- Márgenes laterales amplios y equilibrados; el texto no llega a los tercios externos. **[OBS]**
- El nombre compite con nada: no hay jerarquía secundaria porque no hay segundo elemento. **[OBS]**

## 5. Tipografía

- **Clase**: serif con remates finos y contraste moderado; familia de vocación editorial, no didona. **[OBS]**
- **Caja**: **versalitas/versales** completas, sin puntuación. **[OBS]**
- **Tracking**: amplio, claramente espaciado; el aire entre letras forma parte del diseño. **[OBS]**
- **Peso**: regular; el relieve aporta el cuerpo visual. **[OBS]**
- **Cuerpo**: grande respecto a la tarjeta: la línea ocupa buena parte del ancho útil. **[OBS]**
- **Familia exacta**: no identificable. **[FALTA]**
  Candidatas libres: *Cormorant Garamond* (con tracking), *EB Garamond*, *Spectral* en versales. **[INF]**

## 6. Color

- Cartulina: gris cálido muy desaturado; en la zona iluminada ≈ **#C4C1B6**, en sombra ≈ **#9C9A90**. **[INF]**
  Valores de la **foto**; el material real puede ser más neutro.
- Texto: **sin tinta**, mismo color que el soporte; el relieve y su sombra lo hacen legible. **[OBS]**

## 7. Acabado

- **Blind emboss** (relieve sin tinta ni foil) sobre cartulina de algodón. **[OBS]**
- Fibra y textura visibles en la superficie; gramaje alto. **[OBS]/[INF]**

## 8. Lo que la imagen no dice

- Reverso y datos de contacto. **[FALTA]**
- Medidas, gramaje, profundidad del relieve, imprenta, autoría. **[FALTA]**
- Si «Polly James» es una persona, un estudio o una marca. **[FALTA]**

## 9. Reconstrucción en FigCraft

1. **Frame** `card/front` 85 × 55 mm → 1004 × 650 px a 300 ppp. Fondo `color/stock-01` = `#C4C1B6`.
2. **Texto**: versales, tracking ≈ +8 % del cuerpo (ajustar a ojo hasta reproducir el aire de la foto),
   color idéntico al fondo, centrado con auto layout (padding lateral ≈ 18 %).
3. **Relieve simulado**: capa duplicada con sombra interior 0,5 px abajo-derecha `#8F8D83` al 50 % y
   luz superior 0,5 px `#FFFFFF` al 35 %.
4. **Variables y estilos**: `type/name-caps`, `color/stock-01`, `color/emboss-shadow`, `color/emboss-light`.
5. **Reverso** (a decidir): oficio y contacto; este anverso, por sí solo, no comunica el doble perfil.

## 10. Comparación con la referencia 02

| | 01 · Polly James | 02 · «Improve, all ways.» |
| --- | --- | --- |
| Estrategia | **Identificación**: el nombre es la pieza | **Manifiesto**: una frase es la pieza |
| Riesgo | Puede quedarse muda sobre el oficio | La frase debe ser excelente o envejece mal |
| Uso real | Necesita reverso para contacto | Necesita reverso para contacto |
| Encaje con tu caso | Alto: sustituye el nombre por tu logotipo en relieve | Medio: la frase tendría que hablar por diseño y frontend |

**Recomendación mía [INF]**: híbrido de las dos. Anverso: tu logotipo en blind emboss, centrado, sin
nada más. Reverso: una línea en versales espaciadas con «diseño + frontend», dominio y ciudad. Conserva
la disciplina de 01 y toma de 02 la idea de que una sola línea bien puesta basta.

## 11. Checklist de fidelidad

- [ ] Proporción 85 × 55 mm exacta.
- [ ] Versales con tracking amplio, una sola línea, centrada.
- [ ] Texto del mismo color que el fondo.
- [ ] Nada del mockup: fondo gris, sombra, inclinación, degradado.
- [ ] Relieve tratado como efecto de pantalla, no como acabado real.
