# 0012 — Condivisione delle ricette: link pubblico e copia indipendente

Una ricetta si condivide con un link `/r/<token>`, come le liste di
regalino. Il token è casuale, di 16 caratteri, e sta in `Recipe.share_token`.
"Nuovo link" ne crea un altro e spegne il vecchio. "Spegni il link" lo
toglie. Senza token la ricetta non è raggiungibile.

- **Pagina pubblica** (`GET /api/shared/recipes/{token}`). Si apre senza
  login e ha un limite di richieste suo (`public`, 60 al minuto). Mostra la
  ricetta, gli allergeni che contiene e il nome visibile di chi la condivide.
  Non mostra gli avvisi dal profilo dell'autore, la sua email o altri dati.
  Chi la apre col proprio account vede se è sua.
- **Copia** (`POST …/copy`). Serve l'account. Crea una ricetta **nuova e
  indipendente** nel ricettario di chi copia, con `source=copy` e
  `copied_from`:
  - Gli ingredienti del catalogo restano gli stessi.
  - Gli ingredienti creati dall'autore si riconoscono di nuovo per nome tra
    quelli di chi copia, che così non vede quelli dell'altro.
  - Anche i tag sono di chi copia.
  - L'immagine diventa un file suo, quindi cancellare l'originale non la
    tocca.

`public` per ora vuol dire solo "chi ha il link". Non c'è una pagina di
ricerca o di scoperta.

**Perché:** il link è il modo più semplice di passare una ricetta a chi non ha
l'app. Una copia indipendente evita che le modifiche dell'autore cambino il
ricettario degli altri, e che si condividano dati del catalogo personale.

**Costo accettato:**
- Chi ha il link può passarlo ad altri: è il motivo del "nuovo link".
- Le modifiche successive dell'autore non arrivano a chi ha già copiato.

**Quando rivederla:** se serve una raccolta pubblica di ricette o la
condivisione fra account con aggiornamenti.
