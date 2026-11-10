# 0004 — Ricettario e catalogo degli ingredienti

Le ricette stanno nell'app `recipes`: `Recipe` (porzioni, tempi, difficoltà,
passi in JSON, pasti adatti, giorni in frigo, congelabile, tag),
`RecipeIngredient` (quantità decimale, unità a scelta chiusa, nota,
facoltativo) e `Tag` per utente. Ogni riga punta a un `Ingredient`: un
catalogo condiviso di 237 ingredienti (`recipes/catalog.py`, caricato dalla
migrazione `0002_catalog` e da `manage.py load_catalog`) con nome inglese,
reparto, allergeni UE, unità di default, grammi per pezzo, giorni da fresco e
"basilare". Un nome che non è nel catalogo crea un ingrediente dell'utente
(visibile solo a lui), con l'allergene riconosciuto dal testo come per le
allergie (ADR 0002).

Il riconoscimento dei nomi (`recipes/matching.py`) confronta chiavi
normalizzate (minuscole, senza accenti) e varianti singolare/plurale di ogni
parola ("Peperoni rossi" → "peperone rosso"). Gli allergeni di una ricetta si
ricavano dagli ingredienti; gli avvisi confrontano la ricetta con le
preferenze del profilo: allergie e intolleranze per allergene o per
ingrediente, le antipatie solo per ingrediente.

**Perché:** il piano (fase 4) deve scartare le ricette pericolose nel codice,
e la spesa (fase 5) deve sommare per ingrediente, unità e reparto. Con il
testo libero non si può fare né l'una né l'altra cosa in modo affidabile.

**Costo accettato:** il catalogo va curato a mano e copre la cucina di casa,
non tutto; gli ingredienti degli utenti finiscono in "Altro" senza grammi per
pezzo. Niente foto delle ricette per ora: una tessera illustrata per reparto
(`RecipeArt`) fino alle immagini della fase 8.

**Quando rivederla:** se gli ingredienti degli utenti diventano molti, servirà
un modo per promuoverli nel catalogo (o farli classificare all'LLM con
conferma).
