# 0010 — Piano del nutrizionista: regole lette dall'LLM, confermate, usate nella generazione

Il piano del nutrizionista (`NutritionistPlan` in `apps/plans`) si carica in
PDF o in foto, fino a 8 file. La lettura è un job `nutritionist_plan` sulla
coda `ai` (ADR 0005). Gemini restituisce le **regole** in una forma fissa
(`nutritionist.NutritionistRules`):

- per ogni pasto le opzioni come sono scritte, con le grammature;
- le frequenze a settimana;
- gli alimenti liberi e quelli da evitare;
- le note.

Il codice pulisce il risultato: pasti nell'ordine della giornata, niente
doppioni, niente pasti vuoti. Nomi e dati di paziente e professionista non si
chiedono e non si salvano. Ne nasce una **bozza** da rivedere in una pagina
con gli stessi campi. Si usa solo dopo "Conferma il piano". I file originali
restano finché resta il piano: la pulizia dei job li salta.

Nella procedura "Nuovo piano" si sceglie un piano del nutrizionista
confermato. In quel caso:

- I pasti diventano i suoi.
- Le sue regole sostituiscono "cosa vuoi ottenere" nel prompt della
  settimana.
- **Alla lettera** (`strict`, di default) l'LLM sceglie per ogni pasto una
  delle opzioni. Usa una candidata solo se corrisponde all'opzione, altrimenti
  scrive una ricetta nuova che la realizza. Il tetto di ricette nuove sale al
  massimo settimanale.
  I pasti rimasti vuoti (ricetta scartata o saltata) li riempie il codice solo
  con le ricette che l'LLM ha già scelto quella settimana, mai con altre del
  ricettario. Nella prima prova vera una torta del ricettario era finita a
  colazione quattro volte.
- Senza `strict` può proporre piatti equivalenti con le stesse grammature e
  frequenze.
- Le ricette nuove ricevono le opzioni del pasto come grammature da
  rispettare.
- Gli **alimenti da evitare** sono controllati nel codice come le allergie
  (ADR 0007). Escono dai candidati e fanno scartare le ricette nuove che li
  contengono negli ingredienti veri. Il pasto lo riempie il codice.

**Perché:**
- Il piano del nutrizionista è un documento libero. Leggerlo è da modello,
  ma il risultato va controllato da chi lo conosce, come per le ricette.
- Le grammature restano testo, come le scrive il professionista. Strutturarle
  in quantità per ingrediente servirebbe solo con calorie e macro, che non ci
  sono ancora.
- Gli alimenti da evitare sono l'unica regola verificabile sugli ingredienti.
  Per questo sta nel codice e non solo nel prompt.

**Costo accettato:**
- Frequenze e grammature le rispetta l'LLM e il codice non le verifica.
- Il confronto degli alimenti da evitare è per nome. "Salumi" non riconosce
  "prosciutto", se il catalogo non li lega.
- Un piano diviso per giorni ("lunedì: …") diventa un elenco di opzioni per
  pasto. Si perde l'ordine dei giorni.

**Quando rivederla:**
- Se arrivano calorie e macro: grammature strutturate e controllo nel codice.
- Se i nutrizionisti usano spesso piani giorno per giorno da seguire così come
  sono.
