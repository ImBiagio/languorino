# Languorino — specifica

Prima stesura dalla chiacchierata del 2026-11-10. Descrive cosa deve fare
l'app, non come: il come sta in [progettazione.md](progettazione.md) e le
scelte confermate negli ADR in `docs/decisions/`.

Languorino aiuta a decidere cosa mangiare e a organizzarsi: un profilo con
gusti e vincoli, un piano alimentare generato (o caricato dal nutrizionista),
un ricettario personale, la spesa calcolata dal piano. L'LLM fa il lavoro
pesante, ma ogni cosa che entra nei dati dell'utente passa da una sua conferma
(*human in the loop*).

Utenti previsti: poche persone (noi due e qualche amico), quindi il costo delle
chiamate all'LLM e alla generazione di immagini resta gestibile.

---

## 1. Profilo e onboarding

Dopo la registrazione un **wizard iniziale** (passi in sequenza, niente swipe)
raccoglie tutto quello che serve a generare il piano:

- **dati personali**: nome, cognome, data di nascita (da cui l'età), sesso,
  altezza, peso;
- **intolleranze e allergie**;
- **patologie**;
- **obiettivi** (es. perdere peso, mangiare più proteine, migliorare in
  generale);
- **stile di vita**: lavoro, sport sì/no e quante volte a settimana;
- **cosa piace e cosa non piace**, a livello di cibi e ingredienti;
- **seguito da un nutrizionista**: sì/no (decide il ramo del piano, sezione 2).

Tutto resta modificabile dopo, dal profilo.

**Intervista con l'agente.** In alternativa al wizard, o insieme, una
conversazione uno a uno con un agente AI che fa le stesse domande, anche a
voce. Riempie gli stessi campi del wizard e alla fine li mostra per conferma.

## 2. Piano alimentare

Il piano dice, giorno per giorno, cosa mangiare a ogni pasto.

**Da dove nasce:**

- **seguito da un nutrizionista**: si carica il piano del nutrizionista (di
  solito un PDF, o una foto); l'LLM lo legge e lo trasforma in dati, l'utente
  lo rivede e conferma;
- **non seguito**: l'app chiede cosa si vuole ottenere e propone un piano
  coerente con i principi nutrizionali e con le abitudini dichiarate.

**Generazione.** Si sceglie la durata (una, due, tre settimane, un mese) e
l'LLM compone i giorni variando i piatti, rispettando profilo, allergie e
gusti, e dando la precedenza ai cibi freschi nei primi giorni dopo la spesa.

- **Ricette**: pesca prima dal ricettario dell'utente. Si possono includere o
  escludere ricette per **tag** (es. la "pasta zucca e pancetta" del cuore
  resta nel ricettario ma fuori dal piano).
- **Ricette nuove**: se nel ricettario manca qualcosa di adatto, l'LLM ne
  scrive una (anche prendendo spunto dal web). Nel piano si vede come le
  altre, con un bottone **Salva nel ricettario**.

**Meal prep.** Opzioni di preparazione anticipata:

- tutto nel weekend per la settimana;
- un anticipo di 1, 2 o 3 giorni (il caso più comune: la sera si cucina anche
  per il pranzo del giorno dopo);
- per ogni sessione di preparazione, quanto tempo si ha e la difficoltà
  accettata (facile, media, difficile).

Il piano mostra quindi due viste: **cosa mangi** giorno per giorno e **cosa
prepari** in ogni sessione di prep.

**Condivisione.** Il piano è personale e non si condivide. Al massimo si
condivide il prep.

## 3. Ricettario

Le ricette dell'utente, consultabili, filtrabili e con **tag** liberi.

**Modello della ricetta**, pensato per il meal prep: titolo, ingredienti con
quantità, porzioni, preparazione a passi, tempi (preparazione e cottura),
difficoltà, tag, immagine.

**Aggiungere una ricetta:**

- a mano;
- **da foto o PDF** (OCR + LLM): le ricette scritte a mano della mamma, il
  PDF del ricettario del nutrizionista; più ricette in un colpo solo;
- **a voce**: qualcuno la racconta (la nonna al telefono) e l'LLM la
  trascrive in ricetta;
- **dal piano**: "Salva nel ricettario" su una ricetta proposta dall'LLM.

In ogni import l'LLM riempie i campi del modello, **deduce quelli mancanti**
(porzioni, tempi, difficoltà) e propone i tag. L'utente rivede, corregge e
conferma: niente entra nel ricettario senza conferma.

**Immagini.** Ogni ricetta ha un'immagine. Se non ce l'ha, prima
un'immagine di default, poi una **generata dall'AI** a partire dalla ricetta.

**Condivisione.** Una ricetta si condivide con un link: chi lo apre la vede e,
con un account, se la copia nel suo ricettario. Una ricetta può anche essere
resa pubblica.

## 4. Cosa cuciniamo oggi?

Per chi non segue un piano, o vuole improvvisare: si descrive cosa c'è in
casa, o si fa **una foto al frigo**, e l'app propone cosa cucinare, dal
ricettario o con una ricetta nuova ispirata a quegli ingredienti (salvabile).

## 5. Spesa

- Una lista della spesa normale, con le voci da spuntare.
- **Generata dal piano**: si sceglie il periodo (es. i 7 giorni del piano) e
  l'app calcola le quantità esatte che servono, sommando gli ingredienti.
- **Invia a Spesino**: in futuro la lista passa a Spesino, un'app separata
  solo per la spesa.

Le **scadenze** dei prodotti sono state scartate per ora: costringerebbero a
inserire ogni prodotto con la data. Basta che il piano faccia consumare prima i
cibi freschi.

---

## Domande aperte

- Allergie, intolleranze e gusti stanno nel profilo o nella configurazione del
  piano? Oggi sono nel profilo, compilati dal wizard: da confermare.
- Pasti del giorno: quali e quanti (colazione, pranzo, cena, spuntini) e se si
  configurano.
- Calorie e macronutrienti: si calcolano e si mostrano, o il piano resta
  qualitativo?
- Piano del nutrizionista: lo si segue così com'è o l'LLM può variarlo
  rispettando le stesse grammature?
- Agente vocale: quale servizio per voce e conversazione (Gemini Live, altro),
  e se serve già nella prima versione.
- Generazione delle immagini: quale modello e quanto costa a ricetta.
- Condivisione pubblica delle ricette: una pagina pubblica senza login come i
  link di regalino, o solo fra account?
- Avvertenze: con patologie e obiettivi di peso il piano generato non
  sostituisce un medico. Va scritto in modo chiaro nell'app.

## Ordine di sviluppo proposto

1. **Profilo e wizard**: modello del profilo e onboarding a passi.
2. **Ricettario**: modello della ricetta, CRUD, tag, ricerca.
3. **Import delle ricette**: foto/PDF con OCR + LLM e revisione.
4. **Piano alimentare**: generazione con durata, tag, meal prep e le due viste.
5. **Spesa**: lista con spunte e generazione dal piano.
6. **Cosa cuciniamo oggi**: da testo e da foto del frigo.
7. **Piano del nutrizionista**: import del PDF.
8. **Immagini generate** e **condivisione** delle ricette.
9. **Intervista con l'agente**, anche vocale.
10. **Invia a Spesino**.
