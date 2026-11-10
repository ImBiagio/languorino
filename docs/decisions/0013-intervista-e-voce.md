# 0013 — Intervista per il profilo e voce: turni in un job, proposte confermate, WAV dal browser

**Intervista.** Al posto del wizard, o per aggiornare il profilo, si
chiacchiera con l'assistente su `/intervista`, scrivendo o parlando.

- La conversazione vive nel browser. Ogni turno la manda intera a `POST
  /api/profile/interview`, con la registrazione dell'ultima risposta se si è
  parlato.
- Ogni turno è un job `interview` sulla coda `ai` (ADR 0005). Il frontend lo
  segue più spesso degli altri, ogni 0,8 s.
- Gemini ha la conversazione, il profilo già noto (senza nome e data di
  nascita) e gli argomenti in ordine. Risponde con una domanda e con quello
  che ha capito: campi del profilo e preferenze.
- Il codice passa ogni campo dal `ProfileSerializer` e ogni preferenza dal
  `FoodPreferenceSerializer`, e tiene solo i valori validi. Per esempio
  un'altezza di 900 cm viene scartata, mentre l'allergene si riconosce come
  nel wizard.
- **Il profilo non cambia da solo** (progettazione, principio 1). Le proposte
  si accumulano in un riepilogo "Ho capito" con chip da togliere e si salvano
  con "Salva nel profilo". Nell'onboarding il bottone è "Salva e inizia", che
  chiude anche il wizard.

**Voce.** Il browser registra in **WAV mono a 16 kHz, codificato in pagina**
(`lib/recorder.ts`), non con MediaRecorder.

- Il WebM/Opus di Chrome arrivava a Gemini, che però rispondeva "non ho
  sentito bene". Lo stesso audio in WAV era trascritto parola per parola.
- WAV funziona in tutti i browser, Safari compreso. A 16 kHz un minuto pesa
  circa 2 MB, e il limite è di 10 MB, circa 5 minuti.
- Il backend riconosce comunque dai primi byte WAV, WebM, Ogg, MP3 e MP4/M4A.
- La registrazione va a Gemini nella stessa chiamata del turno. La
  trascrizione torna in `heard` e prende il posto di "🎤 …" nella chat.
- Il file si cancella appena letto: la voce non resta sul disco.
- Con l'interruttore "Leggi le risposte ad alta voce", che si accende da solo
  quando si parla, le risposte si leggono con la sintesi vocale del browser.

**Ricette a voce.** La stessa registrazione serve per l'import (ADR 0005).

- Un solo file audio in `POST /api/jobs` è una ricetta raccontata.
- Il prompt chiede di riordinare i passi e di lasciare vuote le quantità non
  dette.
- Alla conferma la ricetta ha `source=voice`.

**Perché:**
- Turni brevi e conversazione a turni bastano per il profilo. Gemini Live, con
  audio in streaming, costerebbe di più per un'intervista di pochi minuti.
- Le proposte confermate mantengono la regola "l'LLM propone, l'utente
  conferma".

**Costo accettato:**
- Ogni turno attende un job, quindi la chat ha qualche secondo di ritardo e di
  più quando Gemini è sovraccarico.
- La sintesi vocale dipende dalle voci installate nel sistema.

**Quando rivederla:** se serve una conversazione vocale continua (Gemini Live)
o se la latenza dei turni diventa un problema.
