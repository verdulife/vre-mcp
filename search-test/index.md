# Prueba desechable — recuperación de imágenes (23/10/26)

**Pregunta:** ¿se pueden traer 5 imágenes reales para un cartel de discoteca moderno con la
capa más barata (índice de buscador + `og:image` + descarga), sin navegador y sin instalar nada?

**Método:** búsqueda web (3 consultas) → páginas candidatas → imagen declarada por la página
(`og:image` / `twitter:image` / `image_src` / mayor `<img>`) → descarga de bytes → validación con
Pillow (lado corto ≥ 600 px, área ≥ 300k) → una imagen por proyecto. Python 3.14 + httpx + bs4 +
Pillow, ya instalados. Sin Playwright, sin API de imágenes, sin dependencias nuevas.

**Resultado:** 5 de 5 imágenes descargadas, de 5 proyectos distintos.

| Fichero | Dimensiones | Ratio | Fuente |
| --- | --- | --- | --- |
| 01-overmind-design-disco-futurista-1989.png | 1200×1698 | 0.71 (retrato, tipo A) | overmind.design |
| 02-fontsinuse-com-forms-at-fabric-…jpg | 1760×880 | 2.00 | fontsinuse.com |
| 03-vasa-works-….png | 1200×630 | 1.90 | vasa.works |
| 04-andrealiang-com-….png | 903×904 | 1.00 | andrealiang.com |
| 05-chkdesign-com-disco-freaks.jpg | 1925×1284 | 1.50 | chkdesign.com |

## Qué respondió cada capa

| Página | HTTP | Resultado |
| --- | --- | --- |
| overmind.design | 200 | usada |
| fontsinuse.com (fabric) | 200 | usada |
| vasa.works | 200 | usada |
| andrealiang.com | 200 | usada |
| chkdesign.com | 200 | usada |
| dribbble.com ×3 | **202** | bloqueada (muro anti-bot) |
| behance.net ×2 | **403** | bloqueada (muro anti-bot) |
| otaviosantiago.com | 200 | sin imagen usable (Wix sirvió recortes 2000×380 y 910×173) |

## Conclusiones

1. **La capa barata basta para conseguir imágenes, no para conseguir la obra.** Dos de las cinco
   son tarjetas sociales (ratios 1.90 y 2.00, medidas 1200×630 y 1760×880), no el cartel. `og:image`
   es lo que la página quiere mostrar en un enlace, no necesariamente el trabajo.
2. **El ratio es un discriminador gratis y potente.** 1.91:1 = tarjeta social; 0.71 = cartel real.
   Filtrar por ratio antes de gastar visión es una línea de código.
3. **Los muros anti-bot son reales y quirúrgicos:** Dribbble responde 202 (desafío) y Behance 403,
   justo las dos fuentes que más interesan para este brief. Confirma que para ellas hace falta la
   capa 2 (endpoint JSON) o la capa 3 (navegador), no más reintentos.
4. **Los CDN de terceros no rompen:** los 5 ficheros descargaron sin problemas de tamaño ni formato.

**Nada de esto se reutiliza:** `fetch.py` es desechable. Lo que vale es la tabla de arriba.
