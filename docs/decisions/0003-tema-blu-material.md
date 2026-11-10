# 0003 — Tema blu Material 3 e illustrazioni

Languorino ha un tema suo, diverso da regalino: palette Material 3 variante
**Vibrant** dal seed `#1E63E9` (primary `#0054d6`), generata con
`@material/material-color-utilities`, la libreria di Google usata dal
Material Theme Builder. I ruoli stanno come custom property in
`frontend/src/index.css` e Tailwind li mappa per nome. Fuori dallo schema
base ci sono tre colori custom armonizzati verso il seed come prevede
Material (`Blend.harmonize`): verde `success`, ambra `warning`, arancio
`accent` per il cibo. Logo nuovo (ciotola fumante), icone PWA rigenerate
dallo stesso SVG, mail nello stesso blu. Qualche elemento grafico, solo dove
aiuta: il motivo di doodle del cibo (`FoodPattern`) nelle testate di login,
wizard e home, e il piatto apparecchiato (`EmptyPlateIllustration`) quando non
c'è ancora un piano. Sono SVG nel codice con i toni delle palette
(`--illo-*`), non immagini.

**Perché:** l'app deve riconoscersi a colpo d'occhio rispetto a regalino
(rosso, carta da pacchi) pur restando Material. Generare la palette con la
libreria di Google dà ruoli e contrasti corretti senza sceglierli a occhio.
Gli SVG nel codice seguono il tema e pesano pochi byte.

**Costo accettato:** il secondary della variante Vibrant è lilla e sulle
superfici fredde quasi non si distingue: chip e card selezionati usano
`primary-container` invece del `secondary-container` previsto dalla specifica
(la barra di navigazione resta da specifica). Niente tema scuro.

**Quando rivederla:** se serve il tema scuro (stessa libreria, `isDark`),
o se il blu cambia: si rigenera tutto dal seed.

Per rigenerare: in un container `node:20-alpine` installare
`@material/material-color-utilities@0.3.0` e leggere i ruoli da
`MaterialDynamicColors` con `new SchemeVibrant(Hct.fromInt(argbFromHex(seed)), false, 0)`.
