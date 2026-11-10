# 0009 — Cosa cucino oggi: frigo letto dall'LLM, ricette scelte dal codice, idee nuove ricontrollate

"Cosa cucino oggi?" (`apps/kitchen`) ha tre passi, ognuno affidato a chi lo fa
meglio:

1. **Cosa c'è in casa.** Si scrive a mano o si fotografa il frigo o la
   dispensa (fino a 3 foto). La foto va a Gemini in un job `fridge_scan` sulla
   coda `ai` (ADR 0005), che restituisce solo i **nomi** degli alimenti. I nomi
   diventano chip che l'utente corregge prima di andare avanti: l'LLM propone,
   l'utente conferma.
2. **Dal ricettario.** Lo sceglie il **codice**, in modo sincrono
   (`match_recipes`). Si guardano il ricettario e, a scelta, i ricettari PDF
   (ADR 0006). Si filtrano pasto e tempo massimo. Si scartano le ricette che
   toccano un'allergia o un'intolleranza, con lo stesso controllo del
   ricettario. Restano solo gli ingredienti principali, cioè non i facoltativi
   e non i basilari come sale e olio. Ognuno è "ce l'hai" se coincide con un
   ingrediente del catalogo o se il nome scritto lo contiene, al singolare o al
   plurale. L'ordine è: prima chi non manca di niente, poi le più complete,
   poi le più veloci. Al massimo 12.
3. **Idee nuove.** Due ricette scritte da Gemini in un job `cook_ideas` con
   quegli ingredienti, il pasto, il tempo, le porzioni e il profilo ridotto
   (senza nome né email). Si salvano come le ricette scritte per il piano
   (`recipes/generated.py`, condiviso con ADR 0007): fuori dal ricettario,
   `source=fridge`. Si scartano se gli ingredienti veri toccano una
   restrizione. Si aprono con il banner "Salva nel mio ricettario". Quelle mai
   salvate e non finite in un piano si cancellano dopo 7 giorni
   (`kitchen.tasks.clean_ideas`, beat alle 4:45).

`POST /api/jobs` accetta solo `import_recipes`. I job del frigo e delle idee
nascono dagli endpoint di `cook-today`, che controllano i loro file e
parametri.

**Perché:** riconoscere alimenti in una foto è lavoro da modello. Decidere cosa
si può cucinare e cosa è sicuro è un confronto esatto tra liste, e deve dare
sempre lo stesso risultato. Le ricette proprie arrivano subito, senza
aspettare l'LLM. Le idee arrivano dopo, in parallelo.

**Costo accettato:**
- Il confronto per nome è grezzo: "pomodoro" vale anche per "pomodorini".
  Gli alimenti che il catalogo non conosce contano solo se il nome coincide.
- Le quantità in casa non si guardano: "uova" basta anche se ne serve una
  dozzina.
- Un'idea non salvata sparisce dopo una settimana: chi riapre un vecchio
  risultato trova la ricetta non più disponibile.

**Quando rivederla:**
- Se servono le quantità (dispensa tracciata, scadenze).
- Se una settimana risulta poca per ritrovare le idee.
