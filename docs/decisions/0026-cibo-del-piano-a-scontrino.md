# 0026 — Il cibo del piano va nella lista di Scontrino

Dal dialog **Fai la spesa** del piano, **Manda a Scontrino** mette tutto il
cibo della preparazione nella lista della casa su Scontrino
(`POST /api/plans/{id}/scontrino`, `apps/shopping/scontrino.py`). Le voci
sono quelle di `build_items` per tutti i giorni del piano, **senza
ricorrenti** (in Scontrino sono della casa) e **senza basilari** (sale, olio:
si danno per già in casa), con i reparti di Languorino, che hanno già le
chiavi di Scontrino. Si manda sempre tutto insieme con lo stesso riferimento
`plan:<id>` e l'etichetta "Piano dal 16 al 22 novembre": Scontrino sostituisce
solo quelle righe e non tocca quelle scritte o cambiate a mano (ADR 0004 di
Scontrino).

- **Dove va**: dove c'è già quel piano, se la lista è aperta; altrimenti
  nell'ultima lista aperta della casa o in una nuova. Lo decide Scontrino;
  qui si ricordano solo titolo e link dell'ultimo invio
  (`MealPlan.scontrino_sent_at`, `scontrino_list_title`, `scontrino_list_url`),
  che il piano espone in `scontrino` insieme a `enabled` e `app_url`.
- **Si tiene aggiornato da solo**: dopo il primo invio ogni cambio di pasti
  (segnali su `PlannedMeal`, e la generazione che scrive con `bulk_create`)
  mette in coda `shopping.tasks.push_plan_to_scontrino` dopo 20 secondi, uno
  solo per una raffica di cambi (chiave in cache). "Mangiato" non conta.
- **Piano eliminato**: `remove_plan_from_scontrino` chiede a Scontrino di
  togliere le sue righe (restano quelle cambiate a mano).
- **Autenticazione**: niente segreti fra le app. Languorino chiede a cornhub
  un token d'app per il proprietario del piano (`cornhub.app_token`,
  `POST /internal/apps/token` su cornhub, 5 minuti, solo per la coppia
  languorino → scontrino con `shopping:food` e solo se l'utente ha aperto
  tutte e due le app) e lo manda a Scontrino sulla rete Docker "cornhub"
  (`SCONTRINO_INTERNAL_URL`, in produzione `http://scontrino-backend:8000`).
- Chi non ha mai aperto Scontrino riceve "Apri Scontrino una volta" con il
  link (`SCONTRINO_URL`); con Scontrino o cornhub giù il rinvio automatico
  riprova quattro volte, ogni due minuti.

**Perché:** la spesa vera ha cibo e cose per casa insieme, e due liste in due
app non si spuntano insieme. Mandare sempre tutto il piano con lo stesso
riferimento rende ogni invio idempotente: si può rimandare quante volte si
vuole. Un invio per date (come le liste di Languorino) avrebbe voluto un
riferimento per lista e la pulizia di quelle vecchie.

**Costo accettato:**

- Le liste e i ricorrenti di Languorino restano (ADR 0008, 0024, 0025) finché
  non si migrano nella casa di Scontrino: per ora le due strade convivono.
- Il piano va tutto in una lista: chi fa la spesa due volte a settimana
  spunta in Scontrino quello che ha già preso.
- Se cornhub o Scontrino sono giù, "Manda" dà errore e il rinvio aspetta.

**Quando rivederla:** quando le liste di Languorino si migrano a Scontrino
(allora la sezione Spesa rimanda lì e i ricorrenti di qui spariscono), o se
serve mandare solo una parte del piano.
