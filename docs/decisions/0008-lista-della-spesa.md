# 0008 — Lista della spesa calcolata nel codice dal piano

La spesa (`apps/shopping`) è tutta codice, senza LLM: per i pasti del piano in
un intervallo di giorni si prendono gli ingredienti delle ricette, scalati alle
porzioni del pasto, e si sommano per ingrediente nell'unità di default del
catalogo (`aggregate.py`): g/kg → g; ml/l/cucchiai/cucchiaini/tazze → ml
(ml ≈ g per gli ingredienti che si pesano); pezzi ↔ grammi coi grammi per
pezzo del catalogo; quello che non si converte (scatole, mazzetti) resta su una
voce a parte; "q.b." è una voce senza quantità. Le voci facoltative non si
comprano, i basilari partono come "ce l'ho già", le quantità si arrotondano
per eccesso (1, 5 o 10 g; pezzi interi). Ogni voce ricorda da quali pasti
viene. Le voci sono in ordine di reparto (l'ordine di `Category`).

Il ricalcolo dal piano (dopo un cambio di pasti) rifà solo le voci che non
sono state scritte o modificate a mano e tiene la spunta di quelle che
restano. Spuntare non conta come modifica. Le voci a mano prendono il reparto
dal catalogo se il nome corrisponde.

**Perché:** sommare e convertire è aritmetica: deve essere esatta e
ripetibile, e il catalogo (ADR 0004) ha già unità, grammi per pezzo, reparti e
basilari pensati per questo.

**Costo accettato:** ml ≈ g è un'approssimazione; gli ingredienti scritti in
modo che il catalogo non riconosce finiscono in "Altro" con l'unità della
ricetta (si riducono ampliando sinonimi e parole descrittive, es. "perlato");
l'intervallo è per giorno in cui si mangia, non in cui si cucina.

**Quando rivederla:** quando arriva Spesino (app separata), la lista va
esportata in un formato stabile; se serve la densità vera (farina, zucchero),
un campo nel catalogo.
