# 0011 — Immagini delle ricette: foto vera che vince, disegno di Gemini su richiesta

Una ricetta ha un campo `image`, sempre WebP, e un `image_source` che vale
`photo` o `ai`. Senza immagine si vede il disegno della sua categoria, come
prima (ADR 0003). Ci sono due modi di avere un'immagine:

- **Foto vera.** Si carica dal dettaglio della ricetta (`POST
  /api/recipes/{id}/image`): JPEG, PNG o WebP, riconosciuti dai primi byte.
  Si ruota come nel telefono, si riduce a 1600 px, perde l'EXIF e diventa
  WebP. Vince sempre: con una foto vera il disegno dell'AI non si può
  chiedere finché non la si toglie.
- **Disegno di Gemini.** Si chiede a mano, mai in automatico (`POST
  …/image/draw`). Gira in un job `recipe_image` sulla coda `ai` e usa un
  modello a parte (`GEMINI_MODEL_IMAGE`, di default `gemini-2.5-flash-image`)
  da `ai.client.generate_image`. Il prompt ha solo titolo, descrizione e
  ingredienti principali, niente del profilo. C'è un tetto al giorno per
  utente (`AI_IMAGES_PER_DAY`, 20), contato su `AiCall`.

Ogni immagine nuova ha un nome nuovo: `/media` in produzione ha cache lunga e
immutabile. La vecchia si cancella subito. Il file sparisce anche quando la
ricetta si cancella davvero. Il soft delete lo lascia.

**Perché:** una foto del piatto vero vale più di qualsiasi disegno. Le
immagini generate costano e il ricettario senza immagini non ha buchi grazie
ai disegni per categoria, quindi si fanno solo su richiesta e con un tetto.

**Costo accettato:**
- Il piano gratuito di Gemini ha quota zero per i modelli di immagini: risponde
  429 con "limit: 0". Finché la chiave non ha la fatturazione attiva, il
  disegno fallisce con un messaggio che lo dice.
- Le foto HEIC dell'iPhone non si caricano: Pillow non le apre senza una
  libreria in più. Il selettore del telefono di solito le converte in JPEG.

**Quando rivederla:**
- Con la fatturazione attiva: misurare costo e tempi in `AiCall`, poi valutare
  un disegno automatico per le ricette nuove.
- Se le HEIC arrivano davvero: aggiungere `pillow-heif`.
