# 0023 — Piano alimentare e preparazione: prima gli ingredienti, poi le ricette

Il piano si divide in due:

- **Piano alimentare**, cioè cosa dovresti mangiare: il piano del
  nutrizionista letto da PDF o foto (ADR 0010) oppure uno scritto dall'AI
  dalle Linee guida per una sana alimentazione del CREA (2018) e dalle
  raccomandazioni dell'OMS, adattate al profilo. Il modello resta
  `NutritionistPlan` con il campo `source` (`nutritionist` | `guidelines`) e
  le stesse regole (`NutritionistRules`: opzioni per pasto con grammature,
  frequenze a settimana, sostituzioni, alimenti liberi e da evitare). Quello
  dalle linee guida nasce dal job `guidelines_plan` (`plans/guidelines.py`,
  funzione AI piccola `diet_guidelines`), con le porzioni standard CREA
  scritte nel prompt. Si rivede e si conferma nella stessa pagina dell'altro.
- **Preparazione** (`MealPlan`, "Nuova preparazione"): mette il piano nei
  giorni, con settimane, meal prep, cena che fa anche il pranzo dopo.
  `nutritionist_plan` ora è obbligatorio. Ogni pasto (`PlannedMeal`) è fatto
  di **alimenti a persona** (`components`: nome, quantità, unità `g`/`ml`/`pz`,
  quantità nulla = a volontà). Sotto ci sono fino a due **ricette suggerite**
  (`suggestions`). Una suggerita è una ricetta delle fonti scelte
  (ricettario, ricettari PDF) che cucina quegli alimenti, oppure un'idea
  (titolo e una frase). L'idea si scrive per intero solo quando l'utente la
  apre (job `meal_recipe`, funzione piccola, modello veloce,
  `plans/suggestions.py`), con le quantità del pasto. `recipe` è la ricetta
  **approvata** dall'utente e vale per tutto il piatto: stesso giorno di
  cottura e stessi alimenti, cioè la cena e il suo pranzo-avanzo o la
  sessione di prep.

La generazione della settimana (`plans/generation.py`) fa una chiamata
(`plan_week`). Per ogni pasto l'LLM restituisce alimenti e grammature presi
dalle opzioni del piano, gli alimenti delle frequenze che il pasto contiene e
i suggerimenti. Il codice poi:

- toglie gli alimenti delle allergie, delle intolleranze e da evitare
  (`Guard`, sui nomi e sul catalogo, come per le ricette);
- riempie i pasti saltati con un pasto dello stesso tipo;
- copia nel pranzo-avanzo la cena della sera prima;
- **conta le frequenze sui pasti**, con l'avanzo che conta come la sua cena.
  Se non tornano, fa una seconda chiamata che cambia solo i pasti che servono.
  Quello che resta fuori diventa una nota sul pasto, e la pagina mostra
  "legumi 3/3 · pesce 1/2".

La spesa (`shopping/aggregate.py`) parte dagli alimenti del piano moltiplicati
per le porzioni. Aggiunge gli ingredienti della ricetta solo se è approvata, e
solo quelli che non sono già fra gli alimenti del pasto: la pasta la decide il
piano, la cipolla la ricetta. Chat (ADR 0016), "Cosa cucini", home e piano
condiviso leggono gli stessi alimenti.

**Perché:** chi ha un piano del nutrizionista deve rispettarlo per alimenti e
quantità, non per ricette. Prima ogni pasto era una ricetta e le dosi della
dieta ci stavano sopra come testo (`diet_portion`). Le frequenze le contava
l'LLM sui piatti, e la spesa seguiva le quantità della ricetta invece di
quelle del piano. Una ricetta scritta per ogni pasto rendeva la generazione
lenta e costosa: circa 9 chiamate a settimana. Scartata l'alternativa di
lasciare le ricette al centro e aggiungere solo un controllo delle dosi:
il piano resterebbe secondo rispetto al piatto. Senza nutrizionista le linee
guida danno lo stesso schema; un piano libero, solo "dal profilo", non
avrebbe grammature da rispettare.

**Costo accettato:**

- Una preparazione richiede un piano alimentare confermato: un passo in più
  per chi parte da zero.
- Il pasto mostra alimenti e grammature prima del piatto: meno "menu" e più
  "dieta".
- Le idee non scritte non hanno ingredienti extra né passi finché non si
  aprono.
- Il piano dalle linee guida è indicativo e lo dice: non sostituisce medico o
  nutrizionista.
- I piani nati prima restano fatti di ricette (`components` vuoto) e si
  vedono come prima.
- `new_share` ("quante ricette nuove") non si usa più.

**Quando rivederla:** se gli utenti preferiscono scegliere i piatti e adattare
le dosi; se serve modificare a mano gli alimenti di un pasto (oggi si cambiano
solo ricetta, porzioni e giorno di cottura); se le frequenze fuori anche dopo
la correzione restano tante, e conviene farle rispettare dal codice invece che
da una seconda chiamata.
