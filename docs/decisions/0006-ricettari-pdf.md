# 0006 — Ricettari PDF letti a pezzi, fuori dal ricettario

Un PDF non passa più dalla revisione ricetta per ricetta: diventa un
`RecipeBook`, un ricettario da sfogliare. Si legge a pezzi di
`BOOK_PAGES_PER_CHUNK` pagine (4), ognuno con la pagina dopo come contesto: a
Gemini va un PDF ridotto (`pypdf`) e la richiesta di trascrivere solo le
ricette che *iniziano* nel pezzo, così una ricetta a cavallo si legge intera
una volta sola (i titoli già letti si scartano). Ogni pezzo è un task Celery
sulla coda `ai` (`recipes.tasks.read_book_chunk`) che salva le sue ricette,
aggiorna `pages_done` e mette in coda il pezzo dopo; un errore ferma la
lettura e "Riprendi" riparte da `pages_done`.

Le ricette lette sono `Recipe` vere legate al libro (`book`), con
`in_cookbook=False` e `status=draft`: si cercano, hanno allergeni e avvisi dal
profilo e la loro pagina, ma non stanno nel ricettario dell'utente. "Salva nel
mio ricettario" (`POST /api/recipes/{id}/save`) le porta dentro come
confermate. Eliminare il ricettario toglie il PDF e le ricette non salvate.
Le foto restano com'erano (ADR 0005): revisione e conferma.

**Perché:** il primo PDF vero (un ricettario di 50 pagine) mandato intero ha
dato una sola ricetta: il modello si ferma presto su un documento lungo. E un
ricettario intero è materiale da consultare (e da cui il piano potrà pescare),
non decine di ricette da rivedere una a una prima di poterle vedere.

**Costo accettato:** una chiamata a Gemini ogni 4 pagine (un ricettario di 50
pagine sono 13 chiamate) e una pagina letta due volte per pezzo. Le ricette dei
PDF entrano nel database prima di essere riviste: valgono come bozza e i
controlli di sicurezza (allergeni dagli ingredienti) restano nel codice.

**Quando rivederla:** se i PDF hanno ricette lunghe più di 5 pagine, o se i
costi crescono, pezzi più grandi o un primo passaggio che trova l'indice.
