# 0015 — Immagini dei ricettari PDF: foto ritagliate dal PDF, poi illustrazioni AI

Le ricette lette da un ricettario PDF (ADR 0006) prendono un'immagine in due
passi, che partono da soli a fine lettura. Per i ricettari già letti si
avviano dal bottone "Cerca le foto e disegna le altre", con `POST
/api/recipe-books/{id}/images`.

1. **Foto dal PDF** (`book_images.find_photos`). Si rimandano a Gemini le
   pagine a gruppi di 4 (task `find_book_images`, un gruppo per task come la
   lettura). Con le pagine va l'elenco di **tutti** i titoli del ricettario.
   - Gemini risponde solo per le foto o illustrazioni del piatto pronto: pagina
     e riquadro `[ymin, xmin, ymax, xmax]` in millesimi.
   - Il codice disegna la pagina con `pypdfium2`, quindi PDF scansionati e
     digitali allo stesso modo. Poi ritaglia il riquadro e lo salva come
     immagine (`image_source=book`).
   - Si scartano i riquadri non plausibili: sotto il 2% della pagina (icone) o
     sopra l'80% (pagina intera, sfondo).
   - Lo stesso riquadro vale per una sola ricetta.
2. **Illustrazione AI** (task `draw_book_image`, una per task). Le ricette
   rimaste senza immagine si fanno disegnare in stile semplice e illustrativo
   (flat, colori tenui), nel tetto `AI_IMAGES_PER_DAY`. Finito il tetto si
   aspetta: `resume_book_images` riparte ogni mattina alle 5:15. Se la chiave
   non ha quota per le immagini ci si ferma con quel messaggio e "Riprova".

Lo stato sta sul ricettario (`images_status`, `images_pages_done`,
`images_found`, `images_error`). Si aggiorna con `update()` mirati, perché un
`save()` intero riscriverebbe il titolo cambiato nel frattempo (bug del
2026-11-11 sulla lettura).

**Prove del 2026-11-11:**
- Il ricettario vero di 50 pagine è una scansione: ogni pagina è
  un'immagine intera e ha la stessa testata di legumi disegnati. Le immagini
  incorporate nel PDF non servono, va ritagliata la pagina. La testata non
  deve diventare la foto di ogni ricetta.
- Su un PDF di prova con una ricetta illustrata e una no, Gemini ha dato il
  riquadro del piatto e il ritaglio è preciso. Testata e ricetta senza figura
  sono restate fuori.
- Dando a Gemini solo i titoli ancora senza immagine, assegnava la sola foto
  della pagina all'unico titolo rimasto. Per questo si danno sempre tutti i
  titoli.

**Perché:** una foto vera del ricettario vale più di qualsiasi disegno, e un
ricettario intero senza immagini è triste da sfogliare. Le illustrazioni
costano, quindi vanno a rate.

**Costo accettato:**
- Una chiamata a Gemini ogni 4 pagine: circa 13 per un ricettario di 50 pagine.
- Il riquadro dipende dal modello e a volte è stretto o largo.
- Con la chiave sul piano gratuito le illustrazioni non partono.

**Quando rivederla:**
- Se i ritagli sbagliano spesso: mostrarli da confermare.
- Con la fatturazione attiva: misurare tempi e costi delle illustrazioni.

**Aggiornamento 2026-11-11, in produzione:** ogni tanto il modello risponde
senza immagine, in mezzo secondo e senza errore. Ricapitato a 17 ricette su
99, e prima fermava l'intero ricettario. Ora quella ricetta si riprova due
volte dopo 30 s e, se ancora niente, si salta (`images_skipped`); il
ricettario va avanti con le altre. "Riprova" la rimette in coda. Quota e
chiave rifiutata invece fermano tutto, perché aspettare non serve.
