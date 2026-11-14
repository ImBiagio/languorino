# 0017 — Ricette pubbliche, profili pubblici, voti e commenti

Una ricetta ha una visibilità (`Recipe.visibility`): **privata** (default),
**con il link** (chi ha `/r/<token>`, come nell'ADR 0012) o **pubblica**.
Una ricetta pubblica ha anche il link, che resta la sua pagina, e compare nel
**profilo pubblico** dell'autore, `/u/<handle>`.

- **Profilo pubblico** (`GET /api/public/profiles/{handle}`). Si apre senza
  login. Mostra il nome visibile, la data di iscrizione e le card delle
  ricette pubbliche con la media dei voti. Non mostra email, avvisi dal
  profilo alimentare o ricette non pubbliche. Il profilo esiste solo con
  almeno una ricetta pubblica: senza, la pagina risponde 404 anche se
  l'indirizzo c'è.
- **Indirizzo** (`User.handle`, slug unico). Nasce dal nome visibile alla
  prima ricetta pubblica (`apps/community/profiles.py`, `ensure_handle`). Si
  cambia dall'account. Alcuni nomi sono riservati.
- Si pubblicano solo le ricette **nel ricettario**. Quelle dei ricettari PDF
  e quelle scritte per il piano restano fuori finché non si salvano.
- **Voti** (`community.Rating`). Da 1 a 5 stelle, uno per utente e ricetta,
  si cambia o si toglie. Servono l'account e il link; l'autore non vota le
  sue ricette.
- **Commenti** (`community.Comment`, `CommentImage`). Testo fino a 2000
  caratteri e fino a 3 foto, ridotte in WebP senza EXIF come quelle delle
  ricette. Le risposte stanno su un solo livello: rispondere a una risposta
  la attacca allo stesso filo. Li leggono tutti quelli che hanno il link;
  scrivere richiede l'account. Accanto al nome si vedono le stelle che quella
  persona ha dato alla ricetta.
- **Chi cancella**: l'autore del commento e l'autore della ricetta, che
  modera la sua pagina. Testo e foto spariscono subito. Un commento con
  risposte resta come "Commento eliminato" per non spezzare il filo.
- Limiti: `public` per leggere e votare, `comments` (30 all'ora) per scrivere.
- Tornare "privata" spegne il link: voti e commenti restano nel database ma
  non si raggiungono più.

**Perché:** il link da solo serviva a passare una ricetta a qualcuno. Un
profilo pubblico permette di mostrare il proprio ricettario senza mandare un
link per ricetta. Voti e commenti si appoggiano al link, così una ricetta
privata non si può né votare né commentare. Scartato un elenco pubblico di
tutte le ricette: con pochi utenti non serve, e richiederebbe moderazione.

**Costo accettato:**
- Non c'è una ricerca fra i profili. Ci si arriva dal link di una ricetta o
  dall'indirizzo.
- Nessuna notifica di nuovi commenti: l'autore li vede aprendo la ricetta.
- La moderazione è solo dell'autore della ricetta, più l'admin.

**Quando rivederla:** se arrivano utenti che non si conoscono (serve la
segnalazione dei commenti) o se serve una pagina per scoprire ricette.
