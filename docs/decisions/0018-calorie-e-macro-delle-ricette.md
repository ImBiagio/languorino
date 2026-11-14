# 0018 — Calorie e macro delle ricette

Ogni ricetta ha calorie, proteine, carboidrati e grassi **a porzione**
(`Recipe.kcal`, `protein_g`, `carbs_g`, `fat_g`) e da dove vengono
(`nutrition_source`):

- **Dalla ricetta** (`recipe`). L'import da foto e PDF li legge se la
  ricetta li scrive. Se sono per tutta la ricetta, il codice li divide per le
  porzioni. Quelli per 100 g non si usano, perché il peso della porzione non
  si sa. Gemini non li deve inventare.
- **Stimati dall'AI** (`ai`). Con `POST /api/recipes/{id}/nutrition` parte
  un job `recipe_nutrition` sul modello principale (`apps/recipes/nutrition.py`).
  Gemini riceve titolo, porzioni e ingredienti con quantità, e il peso in
  grammi quando il codice lo sa (unità di peso o `grams_per_piece`). Per ogni
  ingrediente risponde grammi, kcal e macro **di tutta la ricetta**, più una
  nota sulle ipotesi (q.b., crudo/cotto). Somme e divisione per porzioni le
  fa il codice, arrotondando a mezzo all'insù. Il dettaglio resta in
  `nutrition_detail` e si mostra in "Come li ho stimati". Gli ingredienti
  facoltativi non contano.
- **Scritti a mano** (`manual`). Si scrivono nel form; cambiarli rende la
  fonte "scritti a mano". Il client non può dichiarare `ai`, può solo
  rimandarlo uguale.

Una stima dell'AI si toglie se cambiano ingredienti, quantità o porzioni,
perché non corrisponde più alla ricetta. I valori "dalla ricetta" e "a mano"
restano: sono di chi li ha scritti. La copia di una ricetta condivisa tiene
i valori. La pagina pubblica li mostra.

Nel dettaglio i valori si vedono a porzione e moltiplicati per le porzioni
scelte, con la quota di energia di ogni macro (4/4/9 kcal per grammo).

**Perché:** il catalogo degli ingredienti non ha i valori nutrizionali, e
riempirlo per 237 ingredienti più quelli degli utenti è un lavoro a parte.
Un modello conosce le tabelle di composizione abbastanza per una stima
casalinga. Chiedere i valori per ingrediente e fare le somme nel codice
rende i totali coerenti con il dettaglio mostrato.

**Costo accettato:**
- Sono stime, e l'interfaccia lo dice ("valori indicativi").
- Una chiamata al modello per ricetta, su richiesta: niente stima automatica
  al salvataggio.

**Quando rivederla:** se servono valori precisi (piano del nutrizionista con
calorie a pasto) o se il catalogo avrà i valori per 100 g: a quel punto il
codice può calcolare da solo e l'AI resta per gli ingredienti senza valori.
