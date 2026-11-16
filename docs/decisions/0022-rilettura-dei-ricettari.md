# 0022 — Rilettura dei ricettari PDF senza rifare le immagini

Un ricettario già letto si può rileggere con `POST /api/recipe-books/{id}/reread`
(bottone "Rileggi le ricette" nella pagina del ricettario). La rilettura usa lo
stesso task a pezzi della prima lettura (`read_book_chunk`, flag
`RecipeBook.rereading`) e le regole di lettura di adesso, ma invece di saltare
le ricette che ci sono già le aggiorna:

- **mai salvate** nel ricettario dell'utente: si riscrivono ingredienti,
  quantità, porzioni, passaggi e tempi (e calorie se scritte nella ricetta),
  passando dal `RecipeSerializer` come un salvataggio dal form. Titolo, tag,
  foto e illustrazioni restano; l'id non cambia, quindi i piani che le usano
  restano collegati;
- **salvate** (`in_cookbook=True`, la stessa ricetta, non una copia): l'utente
  può averle corrette, quindi si riempiono solo le righe senza quantità,
  riportate alle porzioni della ricetta;
- **tolte** dall'utente (cancellate): non tornano;
- **nuove** (perse dalla prima lettura): si aggiungono senza immagine.

Le ricette si riconoscono dal titolo normalizzato, con una tolleranza
(`difflib`, 0,9) per un titolo letto con una lettera diversa. A fine
rilettura non parte la ricerca delle immagini. La rilettura costa come la
prima lettura (`book_read` su cornhub, funzione grande).

**Perché:** le prime letture perdevano molte quantità (nel ricettario di prova
322 righe su 518 senza quantità); ricaricare il PDF rifaceva anche foto e
illustrazioni (tempo e costo) e creava ricette nuove scollegate dai piani.
Scartato un "completa solo le quantità" per tutte: nelle ricette mai salvate
mancavano anche righe e passaggi, che vale la pena riprendere.

**Costo accettato:** una ricetta salvata e rinominata dall'utente non si
riconosce e torna come nuova; nelle ricette salvate righe mancanti e porzioni
sbagliate restano da correggere a mano. Il conteggio della rilettura
(`reread_done`, `reread_added`) vale solo per l'ultima.

**Quando rivederla:** se le ricette avranno una cronologia delle modifiche
dell'utente (si potrebbe riscrivere anche quelle salvate e mai toccate), o se
il titolo non basterà più a riconoscerle.
