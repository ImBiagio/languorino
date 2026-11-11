# 0014 — Modello veloce per le funzioni interattive e intervista a voce in tempo reale

**Modello veloce.** Le funzioni che l'utente aspetta guardando lo schermo
(turno dell'intervista, foto del frigo, idee di "cosa cucino oggi") partono
dal modello veloce, `GEMINI_MODEL_FAST` (default `gemini-flash-lite-latest`).
`generate(..., fast=True)` lo mette in testa ai modelli; il principale e le
riserve restano dietro. Piano, ricettari PDF e piano del nutrizionista restano
sul principale, che ragiona di più e lavora comunque in background.

Misurato il 2026-11-11 su un turno dell'intervista, piano gratuito:

| Modello | Tempi |
|---|---|
| `gemini-flash-latest` | 15–75 s, con "thinking" di 350–800 token e spesso 503/504 |
| `gemini-flash-latest` senza thinking | stessi errori, 67 s quando risponde |
| `gemini-flash-lite-latest` | 2,6–3 s, sempre |

**Voce in tempo reale.** "Due chiacchiere" ha due modi: **Parliamo**, il
predefinito dove il browser lo permette, e **Chat** (ADR 0013).

- **Collegamento diretto.** In "Parliamo" il browser apre una sessione Gemini
  Live (`GEMINI_MODEL_LIVE`, default `gemini-3.1-flash-live-preview`) e scambia
  l'audio in streaming:
  - microfono in PCM 16 kHz, voce di ritorno in PCM 24 kHz (`lib/liveAudio.ts`);
  - trascrizioni delle due parti man mano;
  - interruzioni: parlando sopra, la voce si ferma.
- **Token dal backend.** La chiave non va mai al browser. `POST
  /api/profile/interview/live` crea un token monouso (da usare entro 1
  minuto, valido per la sessione di 15 minuti) con **vincolati** il modello,
  le istruzioni (profilo già noto, senza nome né data di nascita) e gli
  strumenti. Il browser non li può cambiare. Ogni sessione aperta è registrata
  in `AiCall` (`interview_live`) e ha il rate limit `ai`.
- **Strumenti.** Gemini chiama `segna_preferenza(tipo, alimento)`,
  `segna_profilo(campo, valore)` e `fine_intervista`. Il browser manda ogni
  chiamata a `POST /api/profile/interview/proposal`, che converte e valida con
  le regole della chat. Il risultato va nel riepilogo "Ho capito", condiviso
  con la chat. **Niente si salva da solo.**
- **Cosa ha deciso la forma degli strumenti** (prove del 2026-11-11):
  - Con un solo strumento grande (tutti i campi, liste, enum) e la regola in
    fondo alle istruzioni nessun modello Live lo chiamava. Diceva "ho segnato"
    senza farlo.
  - Con tre strumenti piccoli a stringhe e la regola in cima, il modello li
    chiama in 1,3 s.
  - `gemini-2.5-flash-native-audio-latest` è più lento (9 s) e segna meno.

**Perché:**
- La lentezza non era l'app: era il modello principale, che pensa prima di
  rispondere ed è spesso sovraccarico sul piano gratuito.
- Una conversazione vera non regge un giro di job per frase. Passare l'audio
  dal backend aggiungerebbe ritardo a ogni sillaba. Il collegamento diretto con
  token vincolato tiene la chiave e le regole sul server.

**Costo accettato:**
- La voce in tempo reale è l'unica chiamata a Gemini che non passa da
  `ai.client` e da Celery (eccezione al principio 3). `AiCall` conta le
  sessioni ma non i token audio.
- I modelli Live sono in anteprima e il nome può cambiare: è una variabile
  d'ambiente.
- Il riconoscimento di cosa segnare dipende dal modello. Per questo ogni dato
  passa dalla validazione e dalla conferma dell'utente.

**Quando rivederla:**
- Con la fatturazione attiva: rimisurare il modello principale, che sul piano
  a pagamento non dovrebbe dare 503.
- Se nasce un gateway LLM comune ai progetti: farci passare almeno le chiamate
  non in tempo reale.

**Aggiornamento 2026-11-11, fatturazione attiva:**

| Modello | Turno dell'intervista |
|---|---|
| `gemini-flash-latest` | 12–14 s, senza più errori di sovraccarico |
| `gemini-flash-lite-latest` | ~1 s |

Le immagini si generano (circa 6 s). La scelta resta: modello veloce per le
funzioni interattive, principale per il lavoro in background. La
**Priority inference** (`service_tier="priority"`, 75–100% più cara) è per i
progetti di livello 2 o 3. Sul livello 1 la richiesta è accettata ma servita
come standard (header `x-gemini-service-tier: standard`).

**Interruttore della priorità:**
- `GEMINI_PRIORITY=1` chiede la Priority inference solo per le chiamate
  `fast=True` (intervista, frigo, idee, cambio pasto). Di default è spento.
- `AiCall.service_tier` registra il livello con cui Google ha servito ogni
  richiesta, letto dall'header `x-gemini-service-tier`.
- Acceso su un progetto di livello 1, Google risponde "standard" e fa pagare il
  prezzo normale. Quando il progetto passa al livello 2 la priorità parte da
  sola e nell'admin si vede "priority".
