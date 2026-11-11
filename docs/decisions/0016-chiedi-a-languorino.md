# 0016 — Chiedi a Languorino: chat in sola lettura su profilo e piano, grammature calcolate dal codice

Su `/chiedi` si fanno domande sui propri pasti ("quanta pasta mangio oggi tra
pranzo e cena?", "cosa ceno domani?", "cosa dice il nutrizionista sui
legumi?"). Ogni domanda è un job `ask` (`POST /api/ask`) sul modello veloce,
come un turno dell'intervista (ADR 0013, 0014). Il codice è in
`apps/plans/ask.py`.

- **Contesto nel prompt**, ricostruito a ogni domanda:
  - il profilo in forma ridotta, lo stesso dell'intervista (niente nome né data
    di nascita), con gusti e allergie;
  - i pasti del piano attivo (`current_plan`, lo stesso della home) da ieri a
    fra 7 giorni: ricetta, per quante persone, quando si cucina, se è già
    mangiato;
  - le regole del piano del nutrizionista scelto per il piano o, senza,
    dell'ultimo confermato.
- **Le grammature le calcola il codice**: per ogni pasto le righe "a persona"
  di `PlannedMealSerializer.get_portion` (le stesse della pagina del piano,
  con il peso dei pezzi e dei cucchiai) e il **totale del giorno** per
  ingrediente. All'LLM resta da sommare due o tre numeri già scritti; il
  prompt gli chiede di mostrare la somma.
- **Sola lettura**: la chat non cambia profilo, piano o ricette. Non dà
  consigli medici e rimanda al nutrizionista.
- La conversazione vive nel browser (in `sessionStorage`, così uscire per
  guardare il piano non la perde) e ogni domanda la rimanda intera, al massimo
  30 messaggi.

**Perché:**
- Dividere ricette per porzioni e convertire pezzi in grammi è aritmetica: il
  codice lo fa già per la pagina del piano, esatto. Il modello veloce invece
  sbaglia facilmente i conti lunghi.
- Una finestra di 9 giorni copre le domande di tutti i giorni senza mandare un
  piano di 28 giorni a ogni turno. Scartati gli strumenti (function calling)
  per leggere il piano a pezzi: un giro in più per domanda, per dati che
  stanno comodi nel prompt.
- Provato il 2026-11-11 con flash-lite: ~1 s a risposta, somme giuste fra
  pranzo e cena, "questo" risolto dalla conversazione, risposta in inglese,
  rifiuto gentile su "posso mangiare più carboidrati?".

**Costo accettato:**
- Domande su giorni fuori dalla finestra hanno come risposta "guarda la pagina
  del piano".
- Il modello confondeva le porzioni del pasto con "cucina per" del profilo:
  nel contesto si scrive "per 2 persone" e il prompt dice quale usare. Resta
  un punto da ricontrollare se si cambia modello.
- Solo testo: niente voce per ora.

**Quando rivederla:** se servono domande su tutto il piano o sulla spesa
(allargare il contesto o passare agli strumenti), o se la chat deve poter
cambiare qualcosa (allora proposte da confermare, come nell'intervista).
